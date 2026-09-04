"""Phase 10C: Comprehensive Production Infrastructure & Deployment Readiness Test Suite.

Tests configuration validation, secret masking, sandboxed storage, background worker,
exponential retries, health diagnostics, structured logging, latency percentiles,
lifecycle management, and Docker/Compose artifact conformance.
"""

import time
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app._archive.production.config import ProductionConfig, production_config
from app._archive.production.exceptions import (
    ProductionError,
    ConfigurationError,
    SecurityConfigurationError,
    ProductionStorageError,
    StorageValidationError,
    JobError,
    JobTimeoutError,
    HealthCheckError,
)
from app._archive.production.environment import ProductionEnvironmentValidator
from app._archive.production.security import (
    mask_secret,
    mask_sensitive_headers,
    mask_log_record,
    get_production_security_headers,
    SecurityValidator,
)
from app._archive.production.storage import (
    ProductionLocalStorage,
    ProductionS3Storage,
)
from app._archive.production.jobs import (
    Job,
    JobStatus,
    ExponentialBackoffPolicy,
    ProductionJobManager,
    ProductionJobWorker,
)
from app._archive.production.observability import (
    ProductionMetrics,
    StructuredProductionLogger,
)
from app._archive.production.health import ProductionHealthChecker
from app._archive.production.lifecycle import ProductionLifecycleManager


# ==============================================================================
# A, B, C & D. Production Configuration & Environment Validation Tests
# ==============================================================================

def test_production_config_loading_and_defaults():
    """Verify ProductionConfig loads with safe default parameters."""
    cfg = ProductionConfig.from_env()
    assert cfg.ENVIRONMENT in ("development", "staging", "production", "test")
    assert cfg.MAX_REQUEST_BYTES > 0
    assert cfg.MAX_UPLOAD_SIZE_BYTES > 0
    assert cfg.REQUEST_TIMEOUT_SECONDS > 0
    assert cfg.WORKER_CONCURRENCY > 0


def test_production_environment_validator_detects_insecure_defaults():
    """Verify validator flags insecure secrets and wildcard hosts in production."""
    insecure_prod_cfg = ProductionConfig(
        ENVIRONMENT="production",
        DEBUG=True,  # Insecure for prod
        SECRET_KEY="default_dev_secret_key_change_in_production_12345",  # Insecure
        ALLOWED_HOSTS=["*"],  # Wildcard insecure
        DATABASE_URL="sqlite+aiosqlite:///./prod.db"  # SQLite warning
    )
    issues = ProductionEnvironmentValidator.validate_configuration(insecure_prod_cfg)
    assert any("DEBUG mode must be disabled" in i for i in issues)
    assert any("SECRET_KEY must be a secure" in i for i in issues)
    assert any("Wildcard '*' in ALLOWED_HOSTS" in i for i in issues)

    with pytest.raises(SecurityConfigurationError, match="readiness validation failed"):
        ProductionEnvironmentValidator.enforce_production_readiness(insecure_prod_cfg)


def test_production_environment_validator_accepts_valid_production_config():
    """Verify validator passes a well-configured production environment."""
    valid_prod_cfg = ProductionConfig(
        ENVIRONMENT="production",
        DEBUG=False,
        SECRET_KEY="super_secure_production_secret_key_with_high_entropy_1234567890",
        ALLOWED_HOSTS=["api.interview.com", "interview.com"],
        DATABASE_URL="postgresql+asyncpg://user:pass@db:5432/interviews"
    )
    issues = ProductionEnvironmentValidator.validate_configuration(valid_prod_cfg)
    assert len(issues) == 0
    # Should not raise exception
    ProductionEnvironmentValidator.enforce_production_readiness(valid_prod_cfg)


# ==============================================================================
# E, F, G, H & I. Security, Secret Masking & Input Validation Tests
# ==============================================================================

def test_secret_masking_format():
    """Verify mask_secret redacts middle characters leaving only prefix and suffix."""
    assert mask_secret("AIzaSy123456789") == "AIza...6789"
    assert mask_secret("sk-1234567890abcdef") == "sk-1...cdef"
    assert mask_secret("short") == "[REDACTED_SECRET]"
    assert mask_secret("") == ""


def test_sensitive_header_masking():
    """Verify mask_sensitive_headers redacts Authorization, X-Api-Key, and Cookie headers."""
    raw_headers = {
        "Host": "api.interview.com",
        "Authorization": "Bearer secret_jwt_token_123",
        "X-Api-Key": "my_api_key_456",
        "Cookie": "session_id=abc; token=def",
        "Content-Type": "application/json"
    }
    masked = mask_sensitive_headers(raw_headers)
    assert masked["Host"] == "api.interview.com"
    assert masked["Content-Type"] == "application/json"
    assert masked["Authorization"] == "[REDACTED_HEADER]"
    assert masked["X-Api-Key"] == "[REDACTED_HEADER]"
    assert masked["Cookie"] == "[REDACTED_HEADER]"


def test_security_validator_blocks_path_traversal():
    """Verify SecurityValidator rejects path traversal sequences and dangerous filenames."""
    with pytest.raises(StorageValidationError, match="Path traversal"):
        SecurityValidator.validate_filename("../../secret.txt")

    with pytest.raises(StorageValidationError, match="Path traversal"):
        SecurityValidator.validate_filename("C:\\Windows\\System32\\cmd.exe")

    with pytest.raises(StorageValidationError, match="Path traversal"):
        SecurityValidator.validate_filename("test\0nullbyte.txt")

    valid_clean = SecurityValidator.validate_filename("safe_recording (1).wav")
    assert "safe_recording" in valid_clean


def test_security_headers_configuration():
    """Verify get_production_security_headers contains standard security directives."""
    headers = get_production_security_headers()
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" in headers
    assert "Content-Security-Policy" in headers


# ==============================================================================
# J, K & L. Storage Abstraction, Atomic Writes & Sandbox Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_production_local_storage_lifecycle_and_atomic_writes(tmp_path):
    """Verify ProductionLocalStorage stores objects atomically and lists by prefix."""
    storage = ProductionLocalStorage(base_path=str(tmp_path))

    # Put object
    path = await storage.put_object("candidates/c1/resume.pdf", b"PDF_SAMPLE_DATA")
    assert await storage.exists("candidates/c1/resume.pdf") is True

    # Get object
    retrieved = await storage.get_object("candidates/c1/resume.pdf")
    assert retrieved == b"PDF_SAMPLE_DATA"

    # List objects with prefix
    await storage.put_object("candidates/c1/audio.wav", b"AUDIO_DATA")
    await storage.put_object("candidates/c2/audio.wav", b"AUDIO_DATA2")

    c1_objects = await storage.list_objects(prefix="candidates/c1")
    assert len(c1_objects) == 2
    assert "candidates/c1/audio.wav" in c1_objects

    # Delete object
    assert await storage.delete_object("candidates/c1/resume.pdf") is True
    assert await storage.exists("candidates/c1/resume.pdf") is False


@pytest.mark.asyncio
async def test_production_storage_sandbox_escape_blocking(tmp_path):
    """Verify storage operations reject sandbox escaping attempts."""
    storage = ProductionLocalStorage(base_path=str(tmp_path))

    with pytest.raises(StorageValidationError, match="Path traversal"):
        await storage.put_object("../../outside.txt", b"malicious")

    with pytest.raises(StorageValidationError, match="cannot be empty"):
        await storage.put_object("", b"malicious")


# ==============================================================================
# M, N, O, P, Q, R & S. Background Jobs, Exponential Retries & Worker Tests
# ==============================================================================

def test_exponential_backoff_calculations():
    """Verify ExponentialBackoffPolicy calculates predictable exponential delays."""
    policy = ExponentialBackoffPolicy(initial_backoff_sec=0.5, backoff_factor=2.0, max_backoff_sec=10.0)
    assert policy.get_delay_seconds(1) == 0.5
    assert policy.get_delay_seconds(2) == 1.0
    assert policy.get_delay_seconds(3) == 2.0
    assert policy.get_delay_seconds(4) == 4.0
    assert policy.get_delay_seconds(10) == 10.0  # Capped at max_backoff


@pytest.mark.asyncio
async def test_job_manager_enqueue_cancel_and_listing():
    """Verify ProductionJobManager tracks job state transitions and cancellation."""
    mgr = ProductionJobManager()

    async def dummy_task(arg: int):
        return arg * 2

    job = await mgr.enqueue_job("double_number", dummy_task, payload={"arg": 21})
    assert job.status == JobStatus.PENDING
    assert job.job_id in [j.job_id for j in await mgr.list_jobs(JobStatus.PENDING)]

    # Cancel job
    assert await mgr.cancel_job(job.job_id) is True
    assert job.status == JobStatus.CANCELLED


@pytest.mark.asyncio
async def test_job_worker_execution_retries_and_timeout():
    """Verify ProductionJobWorker executes tasks, retries upon transient failure, and handles timeouts."""
    mgr = ProductionJobManager()
    worker = ProductionJobWorker(manager=mgr, concurrency=2)
    await worker.start()

    attempts = 0
    async def flaky_task(val: str):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ValueError("Transient error")
        return f"Processed: {val}"

    job = await mgr.enqueue_job("flaky_clean", flaky_task, payload={"val": "audio_1"}, max_retries=2)

    # Wait for completion
    for _ in range(20):
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break
        await asyncio.sleep(0.1)

    assert job.status == JobStatus.COMPLETED
    assert job.result == "Processed: audio_1"
    assert attempts == 2

    await worker.stop(timeout_seconds=1.0)


# ==============================================================================
# T, U & V. Health, Readiness & Liveness Tests
# ==============================================================================

def test_liveness_check_returns_healthy():
    """Verify liveness check returns healthy process status without external dependencies."""
    live = ProductionHealthChecker.check_liveness()
    assert live["status"] == "healthy"
    assert live["uptime_seconds"] >= 0.0


@pytest.mark.asyncio
async def test_readiness_check_evaluates_subsystems(tmp_path):
    """Verify readiness check inspects DB, store, storage, and configuration."""
    storage = ProductionLocalStorage(base_path=str(tmp_path))
    cfg = ProductionConfig(ENVIRONMENT="development")

    ready = await ProductionHealthChecker.check_readiness(
        db=None,
        store=None,
        storage=storage,
        config=cfg
    )
    assert ready["status"] in ("healthy", "degraded")
    assert ready["components"]["storage"] == "healthy"
    assert ready["components"]["configuration"] == "healthy"


# ==============================================================================
# W, X, Y & Z. Structured Logging & Latency Metrics Tests
# ==============================================================================

def test_structured_logger_masks_secrets_and_emits_json():
    """Verify StructuredProductionLogger redacts secrets and formats log entries."""
    entry = StructuredProductionLogger.log_event(
        event="storage.uploaded",
        request_id="req_12345",
        job_id="job_67890",
        duration_ms=45.2,
        token="Bearer eyJhbGciOiJIUzI1NiJ9.secret",
        password="my_admin_password",
        filename="resume.pdf"
    )
    assert entry["event"] == "storage.uploaded"
    assert entry["token"] == "[REDACTED]"
    assert entry["password"] == "[REDACTED]"
    assert entry["filename"] == "resume.pdf"


def test_production_metrics_percentile_distributions():
    """Verify ProductionMetrics calculates P50, P95, and P99 percentiles."""
    metrics = ProductionMetrics()
    for val in range(1, 101):  # 1 to 100
        metrics.record_latency("http_request", float(val))

    p = metrics.get_percentiles("http_request")
    assert p["count"] == 100
    assert p["p50"] == 50.0
    assert p["p95"] == 95.0
    assert p["p99"] == 99.0


# ==============================================================================
# AA, AB, AC & AD. Docker & Docker Compose Conformance Tests
# ==============================================================================

def test_dockerfile_production_conformance():
    """Verify Dockerfile.production exists, specifies non-root user, and includes healthcheck."""
    dockerfile_path = Path("Dockerfile.production")
    if not dockerfile_path.is_file():
        dockerfile_path = Path("../Dockerfile.production")
    assert dockerfile_path.is_file()
    content = dockerfile_path.read_text(encoding="utf-8")

    # Non-root user check
    assert "USER appuser" in content or "useradd" in content
    # Healthcheck check
    assert "HEALTHCHECK" in content
    # Multi-stage check
    assert "FROM" in content and "AS" in content


def test_docker_compose_production_conformance():
    """Verify docker-compose.production.yml exists and has no hardcoded secrets."""
    compose_path = Path("docker-compose.production.yml")
    if not compose_path.is_file():
        compose_path = Path("../docker-compose.production.yml")
    assert compose_path.is_file()
    content = compose_path.read_text(encoding="utf-8")

    # Services check
    assert "backend:" in content
    assert "postgres:" in content
    assert "redis:" in content
    assert "worker:" in content

    # Zero hardcoded API keys
    assert "AIzaSy" not in content
    assert "sk-" not in content


# ==============================================================================
# AF, AG & AH. Lifecycle Startup, Shutdown & Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_production_lifecycle_manager_startup_and_shutdown(tmp_path):
    """Verify ProductionLifecycleManager starts workers, validates environment, and shuts down idempotently."""
    cfg = ProductionConfig(
        ENVIRONMENT="development",
        STORAGE_LOCAL_PATH=str(tmp_path)
    )
    lifecycle = ProductionLifecycleManager(config=cfg)

    # Startup
    await lifecycle.startup()
    assert lifecycle._is_started is True
    assert lifecycle.worker is not None

    # Shutdown
    await lifecycle.shutdown(timeout_seconds=1.0)
    assert lifecycle._is_shut_down is True

    # Repeated shutdown should be idempotent
    await lifecycle.shutdown(timeout_seconds=1.0)


@pytest.mark.asyncio
async def test_s3_storage_adapter_contract():
    """Verify ProductionS3Storage behaves properly with and without configured bucket."""
    s3_unconfigured = ProductionS3Storage(bucket_name="")
    with pytest.raises(ProductionStorageError, match="not configured"):
        await s3_unconfigured.put_object("test.pdf", b"data")

    s3_configured = ProductionS3Storage(bucket_name="my-interview-bucket")
    res = await s3_configured.put_object("recordings/rec1.wav", b"audio_data")
    assert res == "s3://my-interview-bucket/recordings/rec1.wav"


@pytest.mark.asyncio
async def test_job_worker_timeout_enforcement():
    """Verify background job worker marks job as failed/retrying when timeout is exceeded."""
    mgr = ProductionJobManager()
    worker = ProductionJobWorker(manager=mgr, concurrency=1)
    await worker.start()

    async def slow_hanging_job():
        await asyncio.sleep(2.0)
        return "done"

    job = await mgr.enqueue_job("slow_task", slow_hanging_job, timeout_seconds=0.1, max_retries=1)

    # Wait for completion
    for _ in range(25):
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break
        await asyncio.sleep(0.1)

    assert job.status == JobStatus.FAILED
    assert "timed out" in (job.error or "").lower()

    await worker.stop(timeout_seconds=1.0)


def test_security_validator_content_types():
    """Verify SecurityValidator allows permitted content types and rejects unpermitted."""
    allowed = {"application/pdf", "audio/wav", "image/png"}
    assert SecurityValidator.validate_content_type("application/pdf", allowed) is True
    assert SecurityValidator.validate_content_type("application/pdf; charset=utf-8", allowed) is True
    assert SecurityValidator.validate_content_type("application/x-executable", allowed) is False

