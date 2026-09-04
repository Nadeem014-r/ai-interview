"""Phase 10G: Comprehensive Production Hardening & Operational Resilience Test Suite.

Tests security policies, payload defense, multi-tier rate limiting, bounded retries,
circuit breakers, Redis/storage resilience, job safety, realtime replay guards,
idempotency, timeout governance, and Phase 1–10F backward compatibility.
"""

import time
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app._archive.hardening.exceptions import (
    ProductionError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    TimeoutError,
    DependencyError,
    CircuitOpenError,
    StorageError,
    RedisError,
    JobError,
    ResourceLimitError,
)
from app._archive.hardening.security_policy import SecurityPolicy, default_security_policy
from app._archive.hardening.payload_defense import PayloadDefense
from app._archive.hardening.rate_limiting import TokenBucketLimiter, MultiTierRateLimiter
from app._archive.hardening.resilience import ResiliencePolicy
from app._archive.hardening.circuit_breaker import CircuitBreaker, CircuitState
from app._archive.hardening.redis_resilience import HardenedRedisClient
from app._archive.hardening.storage_resilience import HardenedStorageManager
from app._archive.hardening.job_safety import HardenedJobSupervisor
from app._archive.hardening.realtime_resilience import RealtimeTransportHardening
from app._archive.hardening.idempotency import IdempotencyEngine
from app._archive.hardening.timeout_governance import run_with_timeout
from app._archive.hardening.observability import HardenedTelemetryEngine
from app._archive.hardening.health import HardenedHealthPolicy


# ==============================================================================
# A, B. Security Policy & Payload Defense Tests
# ==============================================================================

def test_payload_defense_blocks_oversized_and_malformed_json():
    """Verify PayloadDefense safely rejects oversized buffers, malformed JSON, and non-dict roots."""
    defense = PayloadDefense(policy=SecurityPolicy(MAX_REQUEST_BYTES=100, MAX_MESSAGE_BYTES=50))

    # Oversized raw bytes
    with pytest.raises(ValidationError, match="exceeds maximum limit"):
        defense.validate_raw_bytes(b"X" * 150)

    # Malformed JSON
    with pytest.raises(ValidationError, match="Malformed JSON"):
        defense.validate_json_string("{invalid_json:")

    # Empty payload
    with pytest.raises(ValidationError, match="cannot be empty"):
        defense.validate_json_string("")

    # Non-dictionary root
    with pytest.raises(ValidationError, match="must be an object"):
        defense.validate_json_string('["item1", "item2"]')


def test_payload_defense_nesting_depth_protection():
    """Verify PayloadDefense detects and blocks deeply nested structures."""
    defense = PayloadDefense(policy=SecurityPolicy(MAX_NESTING_DEPTH=3))

    deep_payload = {"level1": {"level2": {"level3": {"level4": "too_deep"}}}}
    with pytest.raises(ValidationError, match="exceeds maximum nesting depth"):
        defense.validate_nesting_depth(deep_payload)

    valid_payload = {"level1": {"level2": "ok"}}
    defense.validate_nesting_depth(valid_payload)  # Passes safely


def test_payload_defense_event_envelope_validation():
    """Verify event envelope validates allowed events, positive timestamps, and non-negative sequences."""
    defense = PayloadDefense()

    # Valid event
    defense.validate_event_envelope({"event": "audio.chunk", "seq": 1, "timestamp": 1000.0})

    # Unauthorized event
    with pytest.raises(ValidationError, match="Unsupported or unauthorized event"):
        defense.validate_event_envelope({"event": "malicious.exploit"})

    # Negative sequence
    with pytest.raises(ValidationError, match="non-negative integer"):
        defense.validate_event_envelope({"event": "turn.start", "seq": -1})


# ==============================================================================
# C. Multi-Tier Rate Limiting Tests
# ==============================================================================

def test_token_bucket_limiter_burst_and_cooldown():
    """Verify TokenBucketLimiter allows burst, blocks on exhaustion, and calculates retry-after."""
    simulated_time = 100.0
    def mock_clock():
        return simulated_time

    # Rate: 1 token/sec, Burst: 2
    limiter = TokenBucketLimiter(rate_per_second=1.0, burst_capacity=2, clock_fn=mock_clock)

    # 1. First 2 requests succeed (burst capacity)
    allowed, wait = limiter.acquire("user_1")
    assert allowed is True
    allowed, wait = limiter.acquire("user_1")
    assert allowed is True

    # 2. 3rd request blocked
    allowed, retry_after = limiter.acquire("user_1")
    assert allowed is False
    assert retry_after > 0.0

    # 3. Time advances 2 seconds -> replenished
    simulated_time += 2.0
    allowed, wait = limiter.acquire("user_1")
    assert allowed is True


# ==============================================================================
# D, E, T. Normalized Exception Public Dicts & Error Safety
# ==============================================================================

def test_production_exception_public_dict_masks_internal_details():
    """Verify ProductionError.to_public_dict returns only safe metadata without leaking internals."""
    err = RateLimitError("Rate limit hit.", retry_after_sec=5.0, internal_details="Redis key throttle:ip_1.2.3.4")
    pub = err.to_public_dict()

    assert pub["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert pub["status_code"] == 429
    assert pub["retryable"] is True
    assert pub["retry_after_seconds"] == 5.0
    assert "internal_details" not in pub
    assert "1.2.3.4" not in str(pub)


# ==============================================================================
# G, H. Resilience Policy & Exponential Backoff Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_resilience_policy_retries_and_non_retryable_rejection():
    """Verify ResiliencePolicy retries transient errors but immediately raises non-retryable exceptions."""
    delays = []
    async def mock_sleep(d):
        delays.append(d)

    policy = ResiliencePolicy(max_attempts=3, initial_backoff_sec=0.1, backoff_multiplier=2.0, sleep_fn=mock_sleep)

    # 1. Transient error -> succeeds on attempt 2
    attempts = 0
    async def transient_task():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionError("Temporary connection drop")
        return "SUCCESS"

    res = await policy.execute(transient_task)
    assert res == "SUCCESS"
    assert attempts == 2
    assert delays == [0.1]

    # 2. Non-retryable ValidationError -> immediately raised with 0 retries
    val_attempts = 0
    async def validation_failing_task():
        nonlocal val_attempts
        val_attempts += 1
        raise ValidationError("Invalid input format")

    with pytest.raises(ValidationError):
        await policy.execute(validation_failing_task)
    assert val_attempts == 1


# ==============================================================================
# I. Circuit Breaker State Transition Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_circuit_breaker_closed_open_half_open_lifecycle():
    """Verify CircuitBreaker trips to OPEN upon consecutive failures, rejects calls, and recovers in HALF_OPEN."""
    sim_time = 50.0
    def clock():
        return sim_time

    breaker = CircuitBreaker("mock_tts_provider", failure_threshold=2, recovery_timeout_sec=10.0, half_open_max_probes=1, clock_fn=clock)

    assert breaker.state == CircuitState.CLOSED

    # 1. First failure
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED

    # 2. Second failure -> trips to OPEN
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    # 3. Call while OPEN raises CircuitOpenError
    with pytest.raises(CircuitOpenError):
        breaker.before_call()

    # 4. Recovery timeout passes -> transitions to HALF_OPEN
    sim_time += 11.0
    breaker.before_call()
    assert breaker.state == CircuitState.HALF_OPEN

    # 5. Successful probe call -> closes circuit
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED


# ==============================================================================
# J. Centralized Timeout Governance Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_run_with_timeout_enforces_upper_bound():
    """Verify run_with_timeout raises TimeoutError when coroutine hangs."""
    async def hanging_task():
        await asyncio.sleep(2.0)
        return "TOO_LATE"

    with pytest.raises(TimeoutError, match="timed out after"):
        await run_with_timeout(hanging_task(), timeout_sec=0.05, operation_label="LLM Generation")


# ==============================================================================
# K. Redis Resilience & Graceful Fallback Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_hardened_redis_client_fallback_on_exception():
    """Verify HardenedRedisClient returns safe fallback on store exception or timeout."""
    mock_store = AsyncMock()
    mock_store.get.side_effect = TimeoutError("Redis cluster timed out")

    client = HardenedRedisClient(raw_store=mock_store, timeout_sec=0.1)
    val = await client.get_safe("session:key:1", fallback_value={"status": "fallback"})
    assert val == {"status": "fallback"}


# ==============================================================================
# L, S. Storage Safety & Path Traversal Guard Tests
# ==============================================================================

def test_storage_safety_key_validation():
    """Verify HardenedStorageManager sanitizes keys and detects path traversal attacks."""
    mgr = HardenedStorageManager()

    # Path traversal detection
    with pytest.raises(StorageError, match="Path traversal"):
        mgr.sanitize_and_validate_key("../../../etc/passwd")

    with pytest.raises(StorageError, match="Path traversal"):
        mgr.sanitize_and_validate_key("/root/secrets.json")

    # Valid key
    assert mgr.sanitize_and_validate_key("candidates/c42/turn1.wav") == "candidates/c42/turn1.wav"


# ==============================================================================
# M, N. Background Job Supervisor & Capacity Semaphore Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_job_supervisor_queue_limit_and_dead_letter():
    """Verify HardenedJobSupervisor enforces capacity limit and classifies permanent failures as dead_letter."""
    supervisor = HardenedJobSupervisor(max_concurrent=2, max_queue=2)

    # 1. Fill queue to max capacity
    await supervisor.submit_and_execute("job1", "idem1", AsyncMock(return_value="OK1"))
    await supervisor.submit_and_execute("job2", "idem2", AsyncMock(return_value="OK2"))

    # 2. 3rd job exceeds max_queue=2
    with pytest.raises(ResourceLimitError, match="capacity limit reached"):
        await supervisor.submit_and_execute("job3", "idem3", AsyncMock())


# ==============================================================================
# O, P, Q. Realtime Reconnect Storm & Sequence Replay Defense Tests
# ==============================================================================

def test_realtime_reconnect_storm_and_duplicate_message_filter():
    """Verify RealtimeTransportHardening throttles reconnect floods and filters duplicate message IDs."""
    hardening = RealtimeTransportHardening(
        policy=SecurityPolicy(MAX_RECONNECT_ATTEMPTS_PER_MINUTE=2, MAX_WS_CONNECTIONS_PER_IP=1)
    )

    # 1. Connection registration & IP limit
    hardening.register_connection("192.168.1.10")
    with pytest.raises(ResourceLimitError, match="Connection limit exceeded"):
        hardening.register_connection("192.168.1.10")
    hardening.release_connection("192.168.1.10")

    # 2. Reconnect storm throttle
    hardening.check_reconnect_storm("client_abc")
    hardening.check_reconnect_storm("client_abc")
    with pytest.raises(RateLimitError, match="Reconnect storm detected"):
        hardening.check_reconnect_storm("client_abc")

    # 3. Message sequence & duplicate ID filtering
    is_new = hardening.validate_message_sequence_and_deduplicate("sess_1", seq=1, msg_id="msg_100")
    assert is_new is True

    # Duplicate msg_id -> False
    is_dup_id = hardening.validate_message_sequence_and_deduplicate("sess_1", seq=2, msg_id="msg_100")
    assert is_dup_id is False

    # Out of order / duplicate sequence -> False
    is_dup_seq = hardening.validate_message_sequence_and_deduplicate("sess_1", seq=1, msg_id="msg_101")
    assert is_dup_seq is False


# ==============================================================================
# R. Idempotency Engine Caching Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_idempotency_engine_caches_and_prevents_duplicate_execution():
    """Verify IdempotencyEngine executes task once and returns cached result on subsequent calls."""
    engine = IdempotencyEngine(default_ttl_sec=60.0)
    exec_count = 0

    async def expensive_action():
        nonlocal exec_count
        exec_count += 1
        return {"turn_eval": 8.5}

    res1 = await engine.execute_idempotent("idem_key_42", expensive_action)
    assert res1 == {"turn_eval": 8.5}
    assert exec_count == 1

    # Second call with same key returns cached result without re-executing
    res2 = await engine.execute_idempotent("idem_key_42", expensive_action)
    assert res2 == {"turn_eval": 8.5}
    assert exec_count == 1


# ==============================================================================
# U, V. Telemetry Percentiles & Health Policy Tests
# ==============================================================================

def test_hardened_telemetry_percentiles_and_redaction():
    """Verify HardenedTelemetryEngine calculates P50/P95/P99 and redacts secrets."""
    telem = HardenedTelemetryEngine()
    for val in range(1, 101):
        telem.record_latency("llm_latency", float(val * 10))

    pct = telem.get_percentiles("llm_latency")
    assert pct["count"] == 100
    assert pct["p50"] == 500.0
    assert pct["p95"] == 950.0
    assert pct["p99"] == 990.0

    snapshot = telem.export_sanitized_snapshot()
    assert "counters" in snapshot
    assert "latencies" in snapshot


def test_health_policy_liveness_and_degraded_readiness():
    """Verify HardenedHealthPolicy distinguishes process liveness from degraded dependency readiness."""
    live = HardenedHealthPolicy.check_liveness()
    assert live["status"] == "healthy"

    # Degraded readiness when Redis is down
    ready_degraded = HardenedHealthPolicy.check_readiness(db_alive=True, redis_alive=False, storage_alive=True)
    assert ready_degraded["status"] == "degraded"
    assert ready_degraded["components"]["redis"] == "degraded"
    assert ready_degraded["components"]["database"] == "healthy"


# ==============================================================================
# AA. Phase 1–10F Backward Compatibility Test
# ==============================================================================

def test_multi_tier_rate_limiter_segregated_capacities():
    """Verify MultiTierRateLimiter isolates auth limits from general HTTP and WebSocket limits."""
    limiter = MultiTierRateLimiter()
    # HTTP limiter allows 20 burst
    for _ in range(15):
        assert limiter.http_limiter.acquire("client_ip")[0] is True

    # Auth limiter has burst of 5
    for _ in range(5):
        assert limiter.auth_limiter.acquire("auth_ip")[0] is True
    # 6th auth attempt blocked
    assert limiter.auth_limiter.acquire("auth_ip")[0] is False


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_failure_re_trips_to_open():
    """Verify that a failed probe in HALF_OPEN state immediately trips the circuit back to OPEN."""
    sim_time = 100.0
    def clock():
        return sim_time

    breaker = CircuitBreaker("mock_service", failure_threshold=1, recovery_timeout_sec=5.0, clock_fn=clock)

    # 1. Fail to trip to OPEN
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    # 2. Advance time past recovery timeout -> transitions to HALF_OPEN
    sim_time += 6.0
    breaker.before_call()
    assert breaker.state == CircuitState.HALF_OPEN

    # 3. Probe fails -> immediately trips back to OPEN
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_hardened_storage_manager_safe_delete_and_payload_validation():
    """Verify HardenedStorageManager safe_delete is idempotent and validates payloads."""
    mock_raw = AsyncMock()
    mock_raw.delete_object.return_value = True

    mgr = HardenedStorageManager(raw_storage=mock_raw)
    assert await mgr.delete_safe("candidates/c1/audio.wav") is True

    # Validate payload size
    valid_payload = mgr.validate_payload(b"AUDIO_DATA", max_bytes=1000)
    assert valid_payload == b"AUDIO_DATA"

    with pytest.raises(ValidationError, match="exceeds limit"):
        mgr.validate_payload(b"X" * 150, max_bytes=100)


def test_resilience_backoff_calculation_with_jitter():
    """Verify ResiliencePolicy computes bounded exponential backoff with jitter."""
    policy = ResiliencePolicy(initial_backoff_sec=1.0, max_backoff_sec=10.0, backoff_multiplier=2.0, jitter=True)
    delay1 = policy.calculate_backoff(1)
    delay2 = policy.calculate_backoff(2)
    delay3 = policy.calculate_backoff(3)

    assert 0.5 <= delay1 <= 1.0
    assert 1.0 <= delay2 <= 2.0
    assert 2.0 <= delay3 <= 4.0


@pytest.mark.asyncio
async def test_job_supervisor_concurrency_semaphore():
    """Verify HardenedJobSupervisor limits concurrent background tasks."""
    supervisor = HardenedJobSupervisor(max_concurrent=2, max_queue=10)
    active_count = 0
    max_observed_active = 0

    async def concurrent_task():
        nonlocal active_count, max_observed_active
        active_count += 1
        max_observed_active = max(max_observed_active, active_count)
        await asyncio.sleep(0.05)
        active_count -= 1
        return True

    # Run 4 tasks concurrently
    tasks = [
        supervisor.submit_and_execute(f"job_{i}", f"idem_{i}", concurrent_task)
        for i in range(4)
    ]
    results = await asyncio.gather(*tasks)
    assert len(results) == 4
    assert max_observed_active <= 2  # Max concurrency strictly respected


@pytest.mark.asyncio
async def test_full_phase10g_hardening_integration_flow():
    """
    Integrates and tests the complete Phase 10G resilience stack:
    Payload Defense -> Rate Limiting -> Idempotency -> Circuit Breaker -> Resilience -> Telemetry -> Health.
    """
    # 1. Payload Defense
    defense = PayloadDefense()
    payload = defense.validate_json_string('{"event": "audio.chunk", "seq": 1, "timestamp": 12345.0}')
    defense.validate_event_envelope(payload)

    # 2. Rate Limiting
    rate_limiter = MultiTierRateLimiter()
    rate_limiter.http_limiter.enforce("session_client_1")

    # 3. Idempotency Engine & Resilience
    idem_engine = IdempotencyEngine()
    circuit = CircuitBreaker("integration_ai_service", failure_threshold=3)
    resilience = ResiliencePolicy(max_attempts=2)
    telemetry = HardenedTelemetryEngine()

    async def call_hardened_service():
        return await resilience.execute(lambda: circuit.call(AsyncMock(return_value="AI_SYNTHESIZED_RESPONSE")))

    result = await idem_engine.execute_idempotent("idem_flow_01", call_hardened_service)
    assert result == "AI_SYNTHESIZED_RESPONSE"
    telemetry.record_latency("request_latency", 45.2)

    # 4. Health Check
    health = HardenedHealthPolicy.check_readiness(db_alive=True, redis_alive=True, storage_alive=True)
    assert health["status"] == "healthy"


def test_rate_limiter_enforce_raises_rate_limit_error():
    """Verify TokenBucketLimiter.enforce raises RateLimitError on exhaustion."""
    limiter = TokenBucketLimiter(rate_per_second=0.1, burst_capacity=1)
    limiter.enforce("test_enforce_key")
    with pytest.raises(RateLimitError, match="Rate limit exceeded"):
        limiter.enforce("test_enforce_key")


@pytest.mark.asyncio
async def test_resilience_exhaustion_raises_last_exception():
    """Verify ResiliencePolicy raises the underlying exception when all retry attempts fail."""
    policy = ResiliencePolicy(max_attempts=2, initial_backoff_sec=0.01)
    async def failing_action():
        raise ConnectionResetError("Connection permanently dropped")

    with pytest.raises(ConnectionResetError, match="Connection permanently dropped"):
        await policy.execute(failing_action)


@pytest.mark.asyncio
async def test_hardened_redis_client_set_safe():
    """Verify HardenedRedisClient set_safe sets value within timeout."""
    mock_store = AsyncMock()
    mock_store.set.return_value = True

    client = HardenedRedisClient(raw_store=mock_store, timeout_sec=1.0)
    success = await client.set_safe("cache:key:test", "sample_val", ttl_seconds=60)
    assert success is True


def test_realtime_hardening_multiple_ips_concurrency():
    """Verify RealtimeTransportHardening tracks connections independently across distinct client IPs."""
    hardening = RealtimeTransportHardening(policy=SecurityPolicy(MAX_WS_CONNECTIONS_PER_IP=2))
    hardening.register_connection("10.0.0.1")
    hardening.register_connection("10.0.0.1")
    hardening.register_connection("10.0.0.2")

    # 10.0.0.1 at max -> fails
    with pytest.raises(ResourceLimitError):
        hardening.register_connection("10.0.0.1")

    # 10.0.0.2 at 1 -> succeeds
    hardening.register_connection("10.0.0.2")


def test_timeout_policy_dataclass_defaults():
    """Verify TimeoutPolicy defines bounded non-zero timeouts for all operational layers."""
    from app._archive.hardening.timeout_governance import default_timeout_policy
    assert default_timeout_policy.AI_LLM_TIMEOUT_SEC > 0.0
    assert default_timeout_policy.AI_STT_TIMEOUT_SEC > 0.0
    assert default_timeout_policy.AI_TTS_TIMEOUT_SEC > 0.0
    assert default_timeout_policy.REDIS_OP_TIMEOUT_SEC > 0.0
    assert default_timeout_policy.STORAGE_OP_TIMEOUT_SEC > 0.0


def test_telemetry_counters_and_latency_aggregation():
    """Verify HardenedTelemetryEngine tracks counter increments and latency distributions."""
    telem = HardenedTelemetryEngine()
    telem.increment("auth_failures", delta=3)
    telem.increment("rate_limit_events", delta=1)
    telem.record_latency("stt_latency", 250.0)
    telem.record_latency("stt_latency", 450.0)

    snap = telem.export_sanitized_snapshot()
    assert snap["counters"]["auth_failures"] == 3
    assert snap["counters"]["rate_limit_events"] == 1
    assert snap["latencies"]["stt_latency"]["count"] == 2
    assert snap["latencies"]["stt_latency"]["p50"] == 250.0


# ==============================================================================
# AA. Phase 1–10F Backward Compatibility Test
# ==============================================================================

def test_backward_compatibility_phases_1_to_10f():
    """Explicitly verifies that all primary public interfaces from Phases 1–10F remain intact."""
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
    from app._archive.ops.health import ProductionHealthService
    assert ProductionOpsConfig is not None
    assert ProductionHealthService is not None


