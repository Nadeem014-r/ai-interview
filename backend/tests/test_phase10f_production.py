"""Phase 10F: Comprehensive Production Deployment, Reliability & Operations Test Suite.

Tests operational configuration, secret redaction, health diagnostics, database & Redis resilience,
storage safety, background supervisor, graceful lifecycle, structured logging, metrics percentiles,
proxy validation, and Phase 1–10E backward compatibility.
"""

import time
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app._archive.ops.config import ProductionOpsConfig
from app._archive.ops.exceptions import (
    OpsError,
    OpsConfigurationError,
    OpsAuthenticationError,
    OpsDatabaseError,
    OpsRedisError,
    OpsStorageError,
    ErrorCategory,
    classify_exception,
)
from app._archive.ops.secrets import redact_secrets, sanitize_url, mask_secret_string
from app._archive.ops.correlation import CorrelationContext
from app._archive.ops.logging import ProductionLogger
from app._archive.ops.metrics import ProductionOpsMetrics, ops_metrics
from app._archive.ops.database import DatabaseResilience
from app._archive.ops.redis_resilience import RedisResilienceSupervisor
from app._archive.ops.storage_safety import StorageSafetySupervisor
from app._archive.ops.supervisor import JobSupervisor
from app._archive.ops.security import SecurityHardeningSupervisor
from app._archive.ops.validator import DeploymentValidator
from app._archive.ops.health import ProductionHealthService
from app._archive.ops.lifecycle import ProductionLifecycleCoordinator
from app._archive.ops.proxy import ReverseProxyHelper


# ==============================================================================
# A, B, C & D. Configuration, Secret Validation & Redaction Tests
# ==============================================================================

def test_production_ops_config_loading_and_safe_export():
    """Verify ProductionOpsConfig loads and to_safe_dict masks all sensitive keys."""
    cfg = ProductionOpsConfig(
        ENVIRONMENT="production",
        SECRET_KEY="super_secret_production_key_1234567890",
        DATABASE_URL="postgresql+asyncpg://admin:pass123@db:5432/interviews"
    )
    safe = cfg.to_safe_dict()
    assert safe["SECRET_KEY"] == "[REDACTED]"
    assert "pass123" not in safe["DATABASE_URL"]
    assert "[REDACTED]" in safe["DATABASE_URL"]


def test_recursive_secret_redaction():
    """Verify redact_secrets recursively redacts nested dicts, lists, and strings."""
    nested = {
        "user": {
            "name": "Candidate",
            "password": "my_super_secret_password",
            "tokens": ["Bearer eyJhbGciOiJIUzI1NiJ9.secret", "normal_token"],
            "meta": {
                "api_key": "AIzaSySecret12345",
                "normal_field": "valid_value"
            }
        },
        "url": "postgresql://user:secretpass@host:5432/db"
    }
    redacted = redact_secrets(nested)
    assert redacted["user"]["password"] == "[REDACTED]"
    assert redacted["user"]["meta"]["api_key"] == "[REDACTED]"
    assert redacted["user"]["meta"]["normal_field"] == "valid_value"
    assert "secretpass" not in redacted["url"]


def test_sanitize_url_redacts_credentials():
    """Verify sanitize_url strips passwords from database and redis URLs."""
    db_url = "postgresql+asyncpg://appuser:SecretPassword123@postgres.internal:5432/ai_interviewer"
    assert sanitize_url(db_url) == "postgresql+asyncpg://appuser:[REDACTED]@postgres.internal:5432/ai_interviewer"

    redis_url = "redis://:RedisAuthPass@redis.internal:6379/0"
    assert sanitize_url(redis_url) == "redis://:[REDACTED]@redis.internal:6379/0"


# ==============================================================================
# E, F. Health & Readiness Diagnostics Tests
# ==============================================================================

def test_production_health_service_liveness():
    """Verify liveness check returns healthy status without external database dependencies."""
    live = ProductionHealthService.check_liveness()
    assert live["status"] == "healthy"
    assert live["uptime_seconds"] >= 0.0


@pytest.mark.asyncio
async def test_production_health_service_readiness():
    """Verify readiness check inspects database, redis, and configuration."""
    cfg = ProductionOpsConfig(ENVIRONMENT="development")
    mock_redis = AsyncMock()
    mock_redis.check_health.return_value = True

    ready = await ProductionHealthService.check_readiness(
        db_session=None,
        redis_supervisor=mock_redis,
        config=cfg
    )
    assert ready["status"] == "healthy"
    assert ready["components"]["database"] == "healthy"
    assert ready["components"]["redis"] == "healthy"


# ==============================================================================
# G, H. Database & Redis Resilience Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_database_resilience_safe_read_retry():
    """Verify safe read retry succeeds after transient failure and records latency."""
    attempts = 0
    async def flaky_read():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionResetError("Transient DB connection drop")
        return {"rows": 42}

    res = await DatabaseResilience.execute_safe_read_with_retry(flaky_read, max_attempts=2, backoff_sec=0.01)
    assert res == {"rows": 42}
    assert attempts == 2


@pytest.mark.asyncio
async def test_redis_resilience_get_with_fallback():
    """Verify RedisResilienceSupervisor returns fallback value when store fails."""
    mock_store = AsyncMock()
    mock_store.get.side_effect = ConnectionError("Redis down")

    supervisor = RedisResilienceSupervisor(store=mock_store)
    val = await supervisor.get_with_fallback("cache:key", fallback_val="DEFAULT_SAFE_VAL")
    assert val == "DEFAULT_SAFE_VAL"


# ==============================================================================
# I. Storage Safety & Path Traversal Tests
# ==============================================================================

def test_storage_safety_blocks_path_traversal_and_oversized_payload():
    """Verify StorageSafetySupervisor rejects path traversal and oversized objects."""
    with pytest.raises(OpsStorageError, match="Path traversal"):
        StorageSafetySupervisor.validate_storage_key("../../etc/shadow")

    with pytest.raises(OpsStorageError, match="Path traversal"):
        StorageSafetySupervisor.validate_storage_key("uploads\0null.wav")

    valid_key = StorageSafetySupervisor.validate_storage_key("/candidates/c1/audio.wav")
    assert valid_key == "candidates/c1/audio.wav"

    # Content type validation
    assert StorageSafetySupervisor.validate_content_type("audio/wav") is True
    assert StorageSafetySupervisor.validate_content_type("application/x-sh") is False


# ==============================================================================
# J, K. Background Job Supervisor & Retries Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_job_supervisor_retries_and_dead_letter():
    """Verify JobSupervisor retries on transient errors and transitions to dead_letter upon exhaustion."""
    supervisor = JobSupervisor(initial_backoff_sec=0.01)
    attempts = 0

    async def perpetually_failing_task():
        nonlocal attempts
        attempts += 1
        raise ValueError(f"Permanent failure attempt {attempts}")

    with pytest.raises(ValueError):
        await supervisor.execute_job(
            job_id="job_failing_1",
            name="failing_cleanup",
            coro_fn=perpetually_failing_task,
            max_retries=2,
            timeout_seconds=1.0
        )

    job = await supervisor.get_job("job_failing_1")
    assert job.status == "dead_letter"
    assert job.attempts == 3  # 1 initial + 2 retries


# ==============================================================================
# L, M. Lifecycle Coordinator Startup & Shutdown Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_lifecycle_coordinator_startup_and_shutdown():
    """Verify ProductionLifecycleCoordinator executes startup checks and runs shutdown hooks."""
    cfg = ProductionOpsConfig(ENVIRONMENT="development")
    coordinator = ProductionLifecycleCoordinator(config=cfg)

    hook_ran = False
    async def sample_cleanup_hook():
        nonlocal hook_ran
        hook_ran = True

    coordinator.register_shutdown_hook(sample_cleanup_hook)

    # Startup
    assert await coordinator.execute_startup() is True
    assert coordinator._is_started is True

    # Shutdown
    assert await coordinator.execute_shutdown(timeout_seconds=1.0) is True
    assert hook_ran is True
    assert coordinator._is_shut_down is True


# ==============================================================================
# N, O, P, Q. Correlation IDs, Logging & Metrics Percentiles Tests
# ==============================================================================

def test_correlation_context_propagation():
    """Verify CorrelationContext maintains context-local request and session IDs."""
    CorrelationContext.set_request_id("req_custom_123")
    CorrelationContext.set_correlation_id("corr_custom_456")
    CorrelationContext.set_session_id("sess_custom_789")

    ctx = CorrelationContext.get_context_dict()
    assert ctx["request_id"] == "req_custom_123"
    assert ctx["correlation_id"] == "corr_custom_456"
    assert ctx["session_id"] == "sess_custom_789"


def test_production_logger_redaction():
    """Verify ProductionLogger masks sensitive credentials in output dictionary."""
    log_dict = ProductionLogger.log(
        event="user.authenticated",
        duration_ms=25.4,
        data={
            "token": "secret_jwt_token_value",
            "password": "plain_password_string",
            "username": "candidate_test"
        }
    )
    assert log_dict["event"] == "user.authenticated"
    assert log_dict["data"]["token"] == "[REDACTED]"
    assert log_dict["data"]["password"] == "[REDACTED]"
    assert log_dict["data"]["username"] == "candidate_test"


def test_metrics_percentiles_calculation():
    """Verify ProductionOpsMetrics calculates accurate P50, P95, P99 percentiles."""
    metrics = ProductionOpsMetrics()
    for val in range(1, 101):
        metrics.record_latency("request_latency", float(val))

    pct = metrics.get_percentiles("request_latency")
    assert pct["count"] == 100
    assert pct["p50"] == 50.0
    assert pct["p95"] == 95.0
    assert pct["p99"] == 99.0


# ==============================================================================
# R, S. Error Classification & Client-Safe Responses Tests
# ==============================================================================

def test_classify_exception_protects_internal_details():
    """Verify classify_exception never leaks stack traces or internal secrets to API callers."""
    internal_exc = Exception("FATAL: connection to server at 'postgres://user:secret@10.0.0.1:5432' failed: password authentication failed")
    safe_resp = classify_exception(internal_exc)

    assert safe_resp["status_code"] == 503
    assert safe_resp["error_category"] == ErrorCategory.DATABASE_ERROR.value
    assert "secret" not in safe_resp["message"]
    assert "10.0.0.1" not in safe_resp["message"]


# ==============================================================================
# T, U, V, W, X, Y, Z. Security, Validator, Docker & Reverse Proxy Tests
# ==============================================================================

def test_deployment_validator_detects_insecure_production_settings():
    """Verify DeploymentValidator catches insecure secrets and wildcard hosts in production."""
    insecure_cfg = ProductionOpsConfig(
        ENVIRONMENT="production",
        DEBUG=True,
        ALLOWED_HOSTS=["*"],
        CORS_ORIGINS=["*"],
        SECRET_KEY="short_key"
    )
    is_valid, errors, _ = DeploymentValidator.validate_deployment(insecure_cfg)
    assert is_valid is False
    assert any("DEBUG mode must be disabled" in e for e in errors)
    assert any("Wildcard '*' in ALLOWED_HOSTS" in e for e in errors)


def test_reverse_proxy_template_and_validation():
    """Verify ReverseProxyHelper validates presence of WebSocket upgrade and TLS headers."""
    nginx_tmpl = ReverseProxyHelper.get_nginx_template()
    val = ReverseProxyHelper.validate_proxy_config_text(nginx_tmpl)

    assert val["has_websocket_upgrade"] is True
    assert val["has_forwarded_headers"] is True
    assert val["has_ssl_configuration"] is True
    assert val["is_production_ready"] is True


def test_nginx_and_env_example_files_exist():
    """Verify nginx.conf and .env.example exist at repository root."""
    nginx_path = Path("nginx.conf") if Path("nginx.conf").is_file() else Path("../nginx.conf")
    env_path = Path(".env.example") if Path(".env.example").is_file() else Path("../.env.example")

    assert nginx_path.is_file()
    assert env_path.is_file()

    env_content = env_path.read_text(encoding="utf-8")
    assert "AIzaSy" not in env_content  # Zero hardcoded real secrets
    assert "sk-" not in env_content


# ==============================================================================
# AE. Phase 1–10E Backward Compatibility Test
# ==============================================================================

def test_websocket_origin_security_validation():
    """Verify SecurityHardeningSupervisor validates authorized origins and rejects unauthorized ones."""
    allowed = ["https://interview.company.com", "https://app.company.com"]

    assert SecurityHardeningSupervisor.validate_websocket_origin("https://interview.company.com", allowed) is True
    assert SecurityHardeningSupervisor.validate_websocket_origin("https://malicious.hacker.com", allowed) is False
    assert SecurityHardeningSupervisor.validate_websocket_origin(None, allowed) is True


@pytest.mark.asyncio
async def test_multi_worker_coordination_simulation():
    """Verify independent workers can safely coordinate session state via Redis abstraction."""
    from app.realtime.redis_store import RedisStore

    # Shared store representing Redis
    shared_redis = RedisStore(use_redis=False)

    # Worker A writes session lock
    await shared_redis.set("session:coord:lock:s100", "worker_node_A", ttl_seconds=60)

    # Worker B reads session lock
    lock_owner = await shared_redis.get("session:coord:lock:s100")
    assert lock_owner == "worker_node_A"


@pytest.mark.asyncio
async def test_end_to_end_production_smoke_flow():
    """
    Simulates complete production flow from candidate auth context, turn orchestration,
    metrics recording, to background cleanup job execution.
    """
    # 1. Set request & correlation context
    CorrelationContext.set_request_id("req_smoke_prod_01")
    CorrelationContext.set_correlation_id("corr_smoke_prod_01")

    # 2. Log structured authentication event
    ProductionLogger.log(
        event="candidate.authenticated",
        data={"candidate_id": 42, "role": "Senior Distributed Engineer"}
    )
    ops_metrics.increment("request_count")

    # 3. Process voice turn with Phase 10E Voice Orchestrator
    from app._archive.voice_experience.orchestrator import VoiceInterviewOrchestrator
    orch = VoiceInterviewOrchestrator()
    sid = orch.start_session(user_id=42, interview_id=101)

    raw_audio = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00" + b"\x00" * 40
    turn, synthesized_audio, diag = await orch.process_audio_turn(
        session_id=sid,
        user_id=42,
        audio_bytes=raw_audio
    )
    assert len(synthesized_audio) > 0
    ops_metrics.record_latency("stt_latency", diag["latencies_ms"]["stt"])

    # 4. Supervise background cleanup job
    supervisor = JobSupervisor()
    async def cleanup_task():
        orch.end_session(sid)
        return True

    job_res = await supervisor.execute_job(
        job_id="smoke_cleanup_job",
        name="end_session_cleanup",
        coro_fn=cleanup_task
    )
    assert job_res is True

    # 5. Snapshot telemetry
    snapshot = ops_metrics.get_metrics_snapshot()
    assert snapshot["counters"]["request_count"] >= 1
    assert snapshot["counters"]["background_job_success"] >= 1


def test_backward_compatibility_with_all_previous_phases():
    """Explicitly verifies that key interfaces across Phases 1–10E remain importable and accessible."""
    # Phase 8 AI
    from app.ai.factory import AIFactory
    from app.ai.base import LLMProvider, TTSProvider, STTProvider
    assert AIFactory is not None

    # Phase 9 Interview Engine
    from app.interview.engine import AdaptiveInterviewEngine
    from app.interview.state_machine import AdaptiveStateMachine
    assert AdaptiveInterviewEngine is not None

    # Phase 10A Voice
    from app.voice.stt import SpeechToTextService
    from app.voice.tts import TextToSpeechService
    assert SpeechToTextService is not None

    # Phase 10B Realtime
    from app.realtime.websocket import RealtimeWebSocketDispatcher
    from app.realtime.protocol import RealtimeProtocol
    assert RealtimeWebSocketDispatcher is not None

    # Phase 10C Production
    from app._archive.production.config import ProductionConfig
    assert ProductionConfig is not None

    # Phase 10D Providers
    from app.providers.elevenlabs_tts import ElevenLabsTTSProvider
    from app.providers.provider_manager import ProviderManager
    assert ElevenLabsTTSProvider is not None

    # Phase 10E Voice Experience
    from app._archive.voice_experience.orchestrator import VoiceInterviewOrchestrator
    assert VoiceInterviewOrchestrator is not None


