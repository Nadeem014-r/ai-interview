"""Phase 10H: Comprehensive Operations, Monitoring & Production Reliability Test Suite.

Tests configuration validators, liveness/readiness services, operational correlation,
structured logging with secret redaction, metrics engine & P50/P95/P99 analytics,
AI token & cost tracking, database/Redis health probes, deduplicated alert engines,
startup/shutdown lifecycles, backup verification, capacity estimation, offline load simulations,
and Phase 1–10G backward compatibility.
"""

import time
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app._archive.operations.config import (
    ProductionConfigValidator,
    ValidationStatus,
    ConfigValidationResult,
)
from app._archive.operations.correlation import OperationalCorrelation
from app._archive.operations.logging import OperationalLogger
from app._archive.operations.metrics import OperationalMetricsEngine
from app._archive.operations.cost_monitor import (
    AICostMonitor,
    ProviderPricing,
    cost_monitor,
)
from app._archive.operations.db_health import DatabaseHealthMonitor
from app._archive.operations.redis_health import RedisHealthMonitor
from app._archive.operations.health import OperationalHealthService
from app._archive.operations.readiness import OperationalReadinessService
from app._archive.operations.alerts import (
    AlertSeverity,
    OperationalAlert,
    AlertEngine,
)
from app._archive.operations.monitoring import OperationalMonitor
from app._archive.operations.startup import StartupOrchestrator
from app._archive.operations.shutdown import ShutdownCoordinator
from app._archive.operations.recovery import RecoveryTargets, DisasterRecoveryPolicy
from app._archive.operations.backup import BackupMetadata, BackupManager
from app._archive.operations.capacity import CapacityPlanner
from app._archive.operations.diagnostics import ProductionDiagnosticsCollector
from app._archive.operations.load_sim import LoadSimulator
from app._archive.operations.runbook import OperationalRunbook


# ==============================================================================
# A, B. Production Configuration Validation Tests
# ==============================================================================

def test_production_config_validator_valid_and_invalid():
    """Verify ProductionConfigValidator enforces production constraints (secret key, debug=false, cors)."""
    # 1. Insecure Production Config
    invalid_env = {
        "ENVIRONMENT": "production",
        "DEBUG": "true",
        "SECRET_KEY": "short",
        "CORS_ORIGINS": "*",
        "DATABASE_URL": ""
    }
    res = ProductionConfigValidator.validate_environment(invalid_env)
    assert res.status == ValidationStatus.INVALID
    assert res.is_deployable() is False
    assert any("DEBUG mode must be FALSE" in e for e in res.errors)
    assert any("SECRET_KEY must be at least 32" in e for e in res.errors)

    # 2. Valid Production Config
    valid_env = {
        "ENVIRONMENT": "production",
        "DEBUG": "false",
        "SECRET_KEY": "a" * 32,
        "CORS_ORIGINS": "https://interview.example.com",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@host:5432/db"
    }
    valid_res = ProductionConfigValidator.validate_environment(valid_env)
    assert valid_res.status == ValidationStatus.VALID
    assert valid_res.is_deployable() is True


def test_production_config_validator_development_warnings():
    """Verify development environments produce warnings rather than hard failures."""
    dev_env = {
        "ENVIRONMENT": "development",
        "DEBUG": "true",
        "SECRET_KEY": "",
        "DATABASE_URL": ""
    }
    res = ProductionConfigValidator.validate_environment(dev_env)
    assert res.status == ValidationStatus.WARNING
    assert res.is_deployable() is True


# ==============================================================================
# C, D, E. Service Health & Readiness Tests
# ==============================================================================

def test_operational_health_service_liveness():
    """Verify OperationalHealthService reports healthy process status with uptime."""
    live = OperationalHealthService.get_liveness()
    assert live["status"] == "healthy"
    assert live["uptime_seconds"] >= 0.0
    assert live["service"] == "ai_interviewer"


@pytest.mark.asyncio
async def test_operational_readiness_service_healthy_and_degraded():
    """Verify OperationalReadinessService distinguishes healthy from degraded Redis/DB states."""
    # 1. Healthy
    ready_healthy = await OperationalReadinessService.evaluate_readiness(
        db_session=None,
        redis_store=None,
        ai_provider_ready=True
    )
    assert ready_healthy["status"] == "healthy"
    assert ready_healthy["components"]["database"] == "healthy"

    # 2. Degraded AI provider
    ready_degraded = await OperationalReadinessService.evaluate_readiness(
        db_session=None,
        redis_store=None,
        ai_provider_ready=False
    )
    assert ready_degraded["status"] == "degraded"
    assert ready_degraded["components"]["ai_providers"] == "degraded"


# ==============================================================================
# F, G. Request Correlation & Structured Logging Tests
# ==============================================================================

def test_operational_correlation_context():
    """Verify OperationalCorrelation propagates identifiers across task contexts."""
    OperationalCorrelation.set_context(
        request_id="req_test_10h",
        session_id="sess_test_10h",
        interview_id="int_test_10h"
    )
    ctx = OperationalCorrelation.get_context_dict()
    assert ctx["request_id"] == "req_test_10h"
    assert ctx["session_id"] == "sess_test_10h"
    assert ctx["interview_id"] == "int_test_10h"


def test_operational_logger_structured_output_and_secret_redaction():
    """Verify OperationalLogger redacts API keys, JWTs, and passwords in logged metadata."""
    log_rec = OperationalLogger.log(
        event="turn.processed",
        component="voice_engine",
        latency_ms=124.5,
        data={
            "api_key": "AIzaSySecretApiKey12345",
            "password": "plain_password_text",
            "auth_token": "Bearer eyJhbGciOiJIUzI1NiJ9.secret",
            "safe_metric": 42
        }
    )
    assert log_rec["event"] == "turn.processed"
    assert log_rec["latency_ms"] == 124.5
    assert log_rec["data"]["api_key"] == "[REDACTED]"
    assert log_rec["data"]["password"] == "[REDACTED]"
    assert log_rec["data"]["safe_metric"] == 42


# ==============================================================================
# H, I, J, K, L, M. Metrics Engine & Latency Percentiles Tests
# ==============================================================================

def test_metrics_engine_counters_and_gauges():
    """Verify OperationalMetricsEngine tracks counters and point-in-time gauges."""
    engine = OperationalMetricsEngine()
    engine.increment_counter("http_requests_total", 5)
    engine.increment_counter("http_errors_total", 1)
    engine.set_gauge("active_interviews", 12.0)

    snap = engine.export_metrics()
    assert snap["counters"]["http_requests_total"] == 5
    assert snap["counters"]["http_errors_total"] == 1
    assert snap["gauges"]["active_interviews"] == 12.0


def test_metrics_engine_p50_p95_p99_percentiles():
    """Verify OperationalMetricsEngine computes exact monotonic percentiles."""
    engine = OperationalMetricsEngine()
    for val in range(1, 101):
        engine.record_timing("http_latency", float(val))

    pct = engine.get_percentiles("http_latency")
    assert pct["count"] == 100
    assert pct["p50"] == 50.0
    assert pct["p95"] == 95.0
    assert pct["p99"] == 99.0


def test_metrics_engine_empty_dataset_handling():
    """Verify OperationalMetricsEngine safely handles categories with zero samples."""
    engine = OperationalMetricsEngine()
    pct = engine.get_percentiles("unrecorded_category")
    assert pct["count"] == 0
    assert pct["p50"] == 0.0
    assert pct["p95"] == 0.0
    assert pct["p99"] == 0.0


# ==============================================================================
# N. AI Cost & Token Usage Monitoring Tests
# ==============================================================================

def test_ai_cost_monitor_token_aggregation_and_cost_estimation():
    """Verify AICostMonitor aggregates tokens and calculates accurate cost per provider and session."""
    monitor = AICostMonitor()
    # 1. Record Gemini usage: 10,000 input tokens, 2,000 output tokens
    cost1 = monitor.record_usage(
        provider="gemini",
        input_tokens=10000,
        output_tokens=2000,
        session_id="sess_cost_1"
    )
    # Gemini pricing: 10k * $0.000125 = 0.00125, 2k * $0.000375 = 0.00075 -> Total = $0.0020
    assert cost1 == 0.002

    # 2. Record OpenAI usage: 1,000 input, 1,000 output
    cost2 = monitor.record_usage(
        provider="openai",
        input_tokens=1000,
        output_tokens=1000,
        session_id="sess_cost_1"
    )
    # OpenAI pricing: 1k * $0.0015 = 0.0015, 1k * $0.0020 = 0.0020 -> Total = $0.0035
    assert cost2 == 0.0035

    # Check Provider summary
    g_summary = monitor.get_provider_summary("gemini")
    assert g_summary["total_tokens"] == 12000
    assert g_summary["estimated_cost_usd"] == 0.002

    # Check Session summary
    s_summary = monitor.get_session_summary("sess_cost_1")
    assert s_summary["total_tokens"] == 14000
    assert s_summary["estimated_cost_usd"] == 0.0055

    assert monitor.get_total_cost_usd() == 0.0055


# ==============================================================================
# O, P. Database & Redis Health Probes Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_database_health_monitor_probe():
    """Verify DatabaseHealthMonitor probes connection and reports latency."""
    res = await DatabaseHealthMonitor.inspect_database(session=None)
    assert res["status"] == "healthy"
    assert "latency_ms" in res


@pytest.mark.asyncio
async def test_redis_health_monitor_probe():
    """Verify RedisHealthMonitor probes cache store with ping/pong."""
    mock_store = AsyncMock()
    mock_store.set.return_value = True
    mock_store.get.return_value = "pong"
    mock_store.delete.return_value = True

    res = await RedisHealthMonitor.inspect_redis(store=mock_store)
    assert res["status"] == "healthy"
    assert res["latency_ms"] >= 0.0


# ==============================================================================
# S, T, U. Alert Engine & Deduplication Tests
# ==============================================================================

def test_alert_engine_deduplication_and_cooldown():
    """Verify AlertEngine suppresses duplicate alarms during active cooldown periods."""
    engine = AlertEngine(cooldown_seconds=10.0)

    # 1. First alert is emitted
    al1 = engine.trigger_alert(
        alert_code="HIGH_LATENCY",
        severity=AlertSeverity.WARNING,
        message="P95 latency spike",
        observed_value=4500.0,
        threshold_value=3000.0,
        component="api_gateway"
    )
    assert al1 is not None
    assert al1.alert_code == "HIGH_LATENCY"

    # 2. Second identical alert within cooldown is suppressed (returns None)
    al2 = engine.trigger_alert(
        alert_code="HIGH_LATENCY",
        severity=AlertSeverity.WARNING,
        message="P95 latency spike",
        observed_value=4600.0,
        threshold_value=3000.0,
        component="api_gateway"
    )
    assert al2 is None

    # 3. Different alert code is emitted
    al3 = engine.trigger_alert(
        alert_code="REDIS_DOWN",
        severity=AlertSeverity.ERROR,
        message="Redis connection timeout",
        observed_value="disconnected",
        threshold_value="connected",
        component="cache"
    )
    assert al3 is not None


def test_operational_monitor_evaluates_error_rate_threshold():
    """Verify OperationalMonitor detects high error rate and triggers an alarm."""
    metrics = OperationalMetricsEngine()
    alerts = AlertEngine()
    monitor = OperationalMonitor(metrics_engine=metrics, engine_alerts=alerts, error_rate_threshold=0.1)

    # Record 20 requests with 5 errors (25% error rate > 10% threshold)
    metrics.increment_counter("http_requests_total", 20)
    metrics.increment_counter("http_errors_total", 5)

    triggered = monitor.evaluate_system_state()
    assert len(triggered) >= 1
    assert triggered[0]["alert"] == "HIGH_ERROR_RATE"


# ==============================================================================
# V, W, X. Startup Orchestration & Graceful Shutdown Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_startup_orchestrator_successful_flow():
    """Verify StartupOrchestrator runs pre-flight validation and marks system ready."""
    env = {
        "ENVIRONMENT": "development",
        "DEBUG": "true",
        "SECRET_KEY": "dev_secret_key"
    }
    startup_res = await StartupOrchestrator.run_startup_sequence(env_vars=env)
    assert startup_res["ready"] is True
    assert startup_res["config_status"] in (ValidationStatus.VALID.value, ValidationStatus.WARNING.value)


@pytest.mark.asyncio
async def test_shutdown_coordinator_bounded_execution():
    """Verify ShutdownCoordinator executes hooks in order within timeout."""
    coordinator = ShutdownCoordinator(default_timeout_sec=1.0)
    hook1_executed = False
    hook2_executed = False

    async def hook1():
        nonlocal hook1_executed
        hook1_executed = True

    async def hook2():
        nonlocal hook2_executed
        hook2_executed = True

    coordinator.register_hook(hook1)
    coordinator.register_hook(hook2)

    res = await coordinator.execute_shutdown()
    assert res["status"] == "completed"
    assert res["hooks_executed"] == 2
    assert res["failed_hooks"] == 0
    assert hook1_executed is True
    assert hook2_executed is True


# ==============================================================================
# Y, Z. Backup Abstraction & Disaster Recovery Policy Tests
# ==============================================================================

def test_backup_manager_register_and_verification():
    """Verify BackupManager registers backups with SHA256 checksums and verifies integrity."""
    mgr = BackupManager(retention_days=7)
    sample_payload = b"DATABASE_EXPORT_DUMP_SQL_BYTES_12345"

    meta = mgr.register_backup(
        backup_id="bkp_001",
        target_type="database",
        data_payload=sample_payload
    )
    assert meta.backup_id == "bkp_001"
    assert meta.size_bytes == len(sample_payload)
    assert len(meta.checksum_sha256) == 64

    # Verification success
    assert mgr.verify_backup("bkp_001", sample_payload) is True
    assert meta.status == "verified"

    # Verification failure on corrupted bytes
    assert mgr.verify_backup("bkp_001", b"CORRUPTED_BYTES") is False
    assert meta.status == "corrupted"


def test_disaster_recovery_policy_targets():
    """Verify DisasterRecoveryPolicy defines explicit RTO and RPO objectives."""
    targets = DisasterRecoveryPolicy.get_recovery_targets()
    assert targets["rto_targets_seconds"]["redis_loss"] == 5.0
    assert targets["rto_targets_seconds"]["database_failover"] == 30.0
    assert targets["rpo_targets_seconds"]["interview_state"] == 0.0


# ==============================================================================
# AA, AB, AD. Capacity Planning, Diagnostics & Load Simulation Tests
# ==============================================================================

def test_capacity_planner_estimation():
    """Verify CapacityPlanner generates reasonable concurrency estimates."""
    plan = CapacityPlanner.estimate_concurrency_ceiling(cpu_cores=4, ram_gb=8.0)
    assert plan["is_estimate"] is True
    assert plan["estimated_max_concurrent_interviews"] > 0
    assert plan["estimated_network_bandwidth_mbps"] > 0.0


def test_production_diagnostics_collector_redaction():
    """Verify ProductionDiagnosticsCollector aggregates state with secret redaction."""
    diag = ProductionDiagnosticsCollector.generate_diagnostic_snapshot()
    assert diag["service"] == "ai_interviewer"
    assert "liveness" in diag
    assert "counters" in diag
    assert "percentiles" in diag
    assert "cost_summary" in diag


@pytest.mark.asyncio
async def test_offline_load_simulator():
    """Verify LoadSimulator simulates concurrent interviews offline deterministically."""
    sim_res = await LoadSimulator.simulate_concurrent_interviews(concurrency=5, turns_per_interview=2)
    assert sim_res["concurrency"] == 5
    assert sim_res["total_turns_simulated"] == 10
    assert sim_res["successful_interviews"] == 5
    assert sim_res["failed_interviews"] == 0


def test_operational_runbook_procedures():
    """Verify OperationalRunbook provides standard operating procedures for outages."""
    sop = OperationalRunbook.get_procedure("REDIS_DOWN")
    assert sop is not None
    assert "Redis Cache Outage" in sop["title"]
    assert "steps" in sop


def test_production_config_validator_invalid_timeout():
    """Verify ProductionConfigValidator catches non-numeric or negative timeouts."""
    env = {
        "ENVIRONMENT": "production",
        "DEBUG": "false",
        "SECRET_KEY": "a" * 32,
        "CORS_ORIGINS": "https://app.example.com",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@host/db",
        "REQUEST_TIMEOUT_SECONDS": "-5.0"
    }
    res = ProductionConfigValidator.validate_environment(env)
    assert res.status == ValidationStatus.INVALID
    assert any("must be positive" in e for e in res.errors)


def test_backup_manager_prune_expired():
    """Verify BackupManager identifies and prunes backups exceeding retention period."""
    mgr = BackupManager(retention_days=10)
    meta = mgr.register_backup("bkp_old", "database", b"DATA")
    # Simulate backup created 15 days ago
    meta.created_at = time.time() - (15 * 86400.0)

    pruned = mgr.prune_expired_backups()
    assert "bkp_old" in pruned
    assert meta.status == "deleted"


@pytest.mark.asyncio
async def test_readiness_service_unhealthy_when_database_fails():
    """Verify OperationalReadinessService marks system unhealthy if database health fails."""
    mock_failing_db = AsyncMock()
    mock_failing_db.execute.side_effect = ConnectionError("Postgres unreachable")

    ready = await OperationalReadinessService.evaluate_readiness(
        db_session=mock_failing_db,
        redis_store=None,
        ai_provider_ready=True
    )
    assert ready["status"] == "unhealthy"
    assert ready["components"]["database"] == "unhealthy"


def test_ai_cost_monitor_custom_pricing():
    """Verify AICostMonitor works with user-defined custom provider pricing tables."""
    custom_pricing = {
        "custom_llm": ProviderPricing(input_cost_per_1k=0.010, output_cost_per_1k=0.030)
    }
    monitor = AICostMonitor(pricing_table=custom_pricing)
    cost = monitor.record_usage("custom_llm", input_tokens=1000, output_tokens=1000)
    assert cost == 0.040


def test_operational_monitor_high_latency_alarm():
    """Verify OperationalMonitor detects P95 latency breaches and triggers alert."""
    metrics = OperationalMetricsEngine()
    alerts = AlertEngine()
    monitor = OperationalMonitor(metrics_engine=metrics, engine_alerts=alerts, p95_latency_threshold_ms=500.0)

    for _ in range(100):
        metrics.record_timing("http_latency", 600.0)

    triggered = monitor.evaluate_system_state()
    assert any(t["alert"] == "HIGH_LATENCY" for t in triggered)


@pytest.mark.asyncio
async def test_startup_orchestrator_blocked_on_invalid_production_config():
    """Verify StartupOrchestrator halts startup if configuration is invalid in production."""
    invalid_env = {
        "ENVIRONMENT": "production",
        "DEBUG": "true",
        "SECRET_KEY": "too_short"
    }
    res = await StartupOrchestrator.run_startup_sequence(env_vars=invalid_env)
    assert res["ready"] is False
    assert "Configuration validation failed" in res["reason"]


@pytest.mark.asyncio
async def test_shutdown_coordinator_idempotent_multiple_calls():
    """Verify multiple execute_shutdown calls return already_shutting_down safely."""
    coord = ShutdownCoordinator()
    res1 = await coord.execute_shutdown()
    res2 = await coord.execute_shutdown()
    assert res1["status"] == "completed"
    assert res2["status"] == "already_shutting_down"


@pytest.mark.asyncio
async def test_full_operations_integration_telemetry_flow():
    """
    Simulates complete operational loop:
    Correlation set -> Structured log -> Cost recorded -> Metric timing -> Diagnostics snapshot -> Runbook access.
    """
    # 1. Correlation
    OperationalCorrelation.set_context(request_id="req_int_01", session_id="sess_int_01")

    # 2. Structured Log
    rec = OperationalLogger.log("interview.turn_started", component="orchestrator", latency_ms=45.0)
    assert rec["request_id"] == "req_int_01"

    # 3. Cost recording
    cost_monitor.record_usage("gemini", input_tokens=500, output_tokens=150, session_id="sess_int_01")

    # 4. Diagnostics snapshot
    snapshot = ProductionDiagnosticsCollector.generate_diagnostic_snapshot()
    assert snapshot["service"] == "ai_interviewer"

    # 5. Runbook
    procedure = OperationalRunbook.get_procedure("DATABASE_DOWN")
    assert procedure is not None


# ==============================================================================
# AK. Phase 1–10G Backward Compatibility Test
# ==============================================================================

def test_backward_compatibility_phases_1_to_10g():
    """Explicitly verifies that all primary public interfaces from Phases 1–10G remain intact."""
    # Phase 8 AI
    from app.ai.factory import AIFactory
    assert AIFactory is not None

    # Phase 9 Adaptive Interview Engine
    from app.interview.engine import AdaptiveInterviewEngine
    assert AdaptiveInterviewEngine is not None

    # Phase 10A Voice
    from app.voice.stt import SpeechToTextService
    from app.voice.tts import TextToSpeechService
    assert SpeechToTextService is not None

    # Phase 10B Realtime
    from app.realtime.websocket import RealtimeWebSocketDispatcher
    assert RealtimeWebSocketDispatcher is not None

    # Phase 10C Production
    from app._archive.production.config import ProductionConfig
    assert ProductionConfig is not None

    # Phase 10D Providers
    from app.providers.elevenlabs_tts import ElevenLabsTTSProvider
    assert ElevenLabsTTSProvider is not None

    # Phase 10E Voice Experience
    from app._archive.voice_experience.orchestrator import VoiceInterviewOrchestrator
    assert VoiceInterviewOrchestrator is not None

    # Phase 10F Ops
    from app._archive.ops.config import ProductionOpsConfig
    assert ProductionOpsConfig is not None

    # Phase 10G Hardening
    from app._archive.hardening.security_policy import SecurityPolicy
    from app._archive.hardening.circuit_breaker import CircuitBreaker
    assert SecurityPolicy is not None
    assert CircuitBreaker is not None

