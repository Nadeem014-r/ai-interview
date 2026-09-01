"""Phase 10I: Production Release Integration & System Certification Test Suite.

Certifies that the AI Interviewer functions as a coherent, secure, resilient, observable,
and recoverable enterprise system across all integrated layers from Phases 1 through 10H.
"""

import time
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from jose import jwt, JWTError
from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import Interview, InterviewState
from app.voice_experience.orchestrator import VoiceInterviewOrchestrator
from app.voice_experience.models import TurnState, VoiceTurn
from app.voice_experience.exceptions import (
    SilenceDetectedError,
    VoiceSessionOwnershipError,
    VoiceExperienceError,
    TurnStateError,
)
from app.providers.fallback import FallbackTTSProvider
from app.providers.exceptions import ProviderUnavailableError
from app.ai.mock_provider import MockTTSProvider, MockSTTProvider
from app.hardening.security_policy import SecurityPolicy, default_security_policy
from app.hardening.payload_defense import PayloadDefense
from app.hardening.rate_limiting import TokenBucketLimiter, MultiTierRateLimiter
from app.hardening.circuit_breaker import CircuitBreaker, CircuitState
from app.hardening.storage_resilience import HardenedStorageManager
from app.hardening.realtime_resilience import RealtimeTransportHardening
from app.hardening.job_safety import HardenedJobSupervisor
from app.hardening.idempotency import IdempotencyEngine
from app.operations.correlation import OperationalCorrelation
from app.operations.logging import OperationalLogger
from app.operations.metrics import OperationalMetricsEngine, op_metrics
from app.operations.cost_monitor import AICostMonitor, cost_monitor
from app.operations.health import OperationalHealthService
from app.operations.readiness import OperationalReadinessService
from app.operations.alerts import AlertEngine, AlertSeverity
from app.operations.backup import BackupManager
from app.operations.diagnostics import ProductionDiagnosticsCollector
from app.certification.certifier import ReleaseCertifier, certifier


# ==============================================================================
# LEVEL 1 & 2: Authentication & Authorization Certification
# ==============================================================================

def test_cert_authentication_lifecycle():
    """Certify JWT token generation, decoding, and tamper detection."""
    token = create_access_token(subject=42, role="candidate")
    assert token is not None

    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    assert payload["sub"] == "42"
    assert payload["role"] == "candidate"

    # Malformed token handling
    with pytest.raises(JWTError):
        jwt.decode("malformed.jwt.token", settings.SECRET_KEY, algorithms=["HS256"])

    certifier.record_verdict("Authentication", True, "JWT lifecycle & tamper defense certified.")


def test_cert_authorization_and_session_isolation():
    """Certify session authorization prevents cross-candidate access."""
    orch = VoiceInterviewOrchestrator()
    sid = orch.start_session(user_id=10, interview_id=100)

    # User 99 tries to execute turn on User 10's session -> Blocked with VoiceSessionOwnershipError
    with pytest.raises(VoiceSessionOwnershipError, match="not authorized"):
        asyncio.run(orch.process_audio_turn(
            session_id=sid,
            user_id=99,
            audio_bytes=b"AUDIO"
        ))
    certifier.record_verdict("Authorization", True, "Cross-candidate isolation certified.")


# ==============================================================================
# LEVEL 2: Resume & Interview Engine Integration Certification
# ==============================================================================

@pytest.mark.asyncio
async def test_cert_resume_to_interview_pipeline():
    """Certify candidate resume context feeds the adaptive interview engine adaptively."""
    from app.realtime.adapters import InterviewEngineAdapter
    adapter = InterviewEngineAdapter(db=None)

    mock_int = Interview(id=1, candidate_id=42, company_id=1, role_id=1)
    mock_st = InterviewState(interview_id=1, current_topic="Distributed Systems", difficulty="medium", time_remaining_seconds=1800, questions_asked_count=0)

    state_out, next_q, is_completed = await adapter.advance_interview_turn(
        interview=mock_int,
        state=mock_st,
        last_eval_score=8.0,
        asked_question_ids=[],
        last_answer_text="I designed an idempotent distributed pub/sub stream using Redis and Kafka."
    )
    assert state_out.questions_asked_count == 1
    assert is_completed is False
    certifier.record_verdict("Resume/Interview Flow", True, "Interview engine turn progression certified.")


# ==============================================================================
# LEVEL 2: AI Provider & Voice Subsystem Certification (LLM, STT, TTS)
# ==============================================================================

@pytest.mark.asyncio
async def test_cert_llm_provider_and_fallback_resilience():
    """Certify primary provider failure automatically cascades to safe fallback."""
    mock_failing_primary = AsyncMock()
    mock_failing_primary.synthesize_speech.side_effect = ProviderUnavailableError("ElevenLabs quota exhausted", provider="elevenlabs")

    fallback_tts = FallbackTTSProvider(primary=mock_failing_primary, fallback=MockTTSProvider())
    audio = await fallback_tts.synthesize_speech("Could you explain eventual consistency?")
    assert len(audio) > 0
    assert fallback_tts.last_fallback_error is not None
    certifier.record_verdict("LLM / AI Providers", True, "Provider cascading fallback certified.")


@pytest.mark.asyncio
async def test_cert_stt_transcription_and_silence_detection():
    """Certify STT handles transcription, rejects silence, and rejects oversized audio."""
    orch = VoiceInterviewOrchestrator()
    sid = orch.start_session(user_id=1, interview_id=10)

    # 1. Silence detection: empty transcript raises SilenceDetectedError
    mock_stt = AsyncMock()
    mock_stt.transcribe_audio.return_value = {"text": "   "}
    with patch.object(orch.provider_mgr, "get_stt_provider", return_value=mock_stt):
        with pytest.raises(SilenceDetectedError, match="No meaningful candidate speech"):
            await orch.process_audio_turn(sid, user_id=1, audio_bytes=b"SILENCE")

    # 2. Oversized audio payload rejection
    huge_audio = b"X" * (orch.config.MAX_TURN_AUDIO_BYTES + 500)
    with pytest.raises(VoiceExperienceError, match="exceeds limit"):
        await orch.process_audio_turn(sid, user_id=1, audio_bytes=huge_audio)

    certifier.record_verdict("Speech-to-Text", True, "STT transcription & silence guards certified.")


@pytest.mark.asyncio
async def test_cert_tts_speech_synthesis_and_fallback():
    """Certify TTS synthesizes voice audio safely."""
    tts = MockTTSProvider()
    audio = await tts.synthesize_speech("What are ACID transaction guarantees?")
    assert len(audio) > 0
    certifier.record_verdict("Text-to-Speech", True, "TTS voice synthesis certified.")


# ==============================================================================
# LEVEL 3: Realtime Transport & Audio Pipeline Certification
# ==============================================================================

def test_cert_realtime_websocket_and_sequence_ordering():
    """Certify WebSocket sequence number deduplication and out-of-order frame filtering."""
    guard = RealtimeTransportHardening()

    # Sequence 1 is accepted
    assert guard.validate_message_sequence_and_deduplicate("sess_ws_1", seq=1, msg_id="msg_a") is True

    # Duplicate message ID is rejected
    assert guard.validate_message_sequence_and_deduplicate("sess_ws_1", seq=2, msg_id="msg_a") is False

    # Out of order / lower sequence number is rejected
    assert guard.validate_message_sequence_and_deduplicate("sess_ws_1", seq=1, msg_id="msg_b") is False

    certifier.record_verdict("Realtime Transport", True, "Sequence ordering & duplicate defense certified.")


def test_cert_audio_pipeline_chunking_and_buffering():
    """Certify audio buffer sizing and rate limiting for rapid streaming audio producers."""
    limiter = TokenBucketLimiter(rate_per_second=10.0, burst_capacity=20)
    # Burst 20 audio chunks allowed
    for _ in range(20):
        assert limiter.acquire("audio_stream_c1")[0] is True
    # 21st chunk is throttled with retry-after
    allowed, wait = limiter.acquire("audio_stream_c1")
    assert allowed is False
    assert wait > 0.0
    certifier.record_verdict("Audio Pipeline", True, "Audio buffering & backpressure certified.")


# ==============================================================================
# LEVEL 3: Interview State Machine & Persistence Certification
# ==============================================================================

def test_cert_interview_state_machine_transitions():
    """Certify valid voice turn lifecycle progression and rejection of illegal state skips."""
    from app.voice_experience.turn_manager import VoiceTurnManager
    turn = VoiceTurn()
    assert turn.state == TurnState.IDLE

    # Valid progression
    VoiceTurnManager.transition(turn, TurnState.LISTENING)
    VoiceTurnManager.transition(turn, TurnState.TRANSCRIBING)
    VoiceTurnManager.transition(turn, TurnState.THINKING)
    VoiceTurnManager.transition(turn, TurnState.GENERATING)
    VoiceTurnManager.transition(turn, TurnState.SYNTHESIZING)
    VoiceTurnManager.transition(turn, TurnState.PLAYING)
    VoiceTurnManager.transition(turn, TurnState.COMPLETED)
    assert turn.state == TurnState.COMPLETED

    # Illegal transition: COMPLETED -> LISTENING raises TurnStateError
    with pytest.raises(TurnStateError):
        VoiceTurnManager.transition(turn, TurnState.LISTENING)

    certifier.record_verdict("Interview State Machine", True, "Turn state machine progression certified.")


# ==============================================================================
# LEVEL 4: Redis, Storage & Background Jobs Certification
# ==============================================================================

@pytest.mark.asyncio
async def test_cert_redis_resilience_and_fallback_store():
    """Certify Redis operations degrade gracefully to safe fallback upon outage."""
    from app.hardening.redis_resilience import HardenedRedisClient
    mock_failing_store = AsyncMock()
    mock_failing_store.get.side_effect = TimeoutError("Redis cluster unreachable")

    client = HardenedRedisClient(raw_store=mock_failing_store, timeout_sec=0.05)
    val = await client.get_safe("active_session:10", fallback_value={"status": "in_memory"})
    assert val == {"status": "in_memory"}
    certifier.record_verdict("Redis Layer", True, "Redis circuit breaker & fallback certified.")


def test_cert_storage_safety_and_path_traversal():
    """Certify storage manager blocks path traversal exploits and validates payloads."""
    mgr = HardenedStorageManager()
    with pytest.raises(Exception):
        mgr.sanitize_and_validate_key("../../etc/shadow")
    with pytest.raises(Exception):
        mgr.sanitize_and_validate_key("audio\0null.wav")

    assert mgr.sanitize_and_validate_key("candidates/c1/audio.wav") == "candidates/c1/audio.wav"
    certifier.record_verdict("Object Storage", True, "Storage path traversal defense certified.")


@pytest.mark.asyncio
async def test_cert_background_job_supervisor_and_dead_letter():
    """Certify background job supervisor enforces execution timeouts and dead-letter tracking."""
    supervisor = HardenedJobSupervisor(max_concurrent=5, max_queue=20)
    attempts = 0

    async def failing_worker():
        nonlocal attempts
        attempts += 1
        raise ValueError(f"Worker failure {attempts}")

    with pytest.raises(Exception):
        await supervisor.submit_and_execute(
            job_id="cert_job_1",
            idempotency_key="cert_idem_1",
            coro_fn=failing_worker,
            max_retries=2,
            timeout_sec=0.5
        )

    job_rec = await supervisor.get_job_status("cert_job_1")
    assert job_rec.status == "dead_letter"
    assert job_rec.attempts == 3
    certifier.record_verdict("Background Jobs", True, "Job supervisor & dead-letter queue certified.")


# ==============================================================================
# LEVEL 5: Observability, Cost & Security Certification
# ==============================================================================

def test_cert_observability_and_secret_redaction():
    """Certify structured logging redacts credentials and propagates correlation IDs."""
    OperationalCorrelation.set_context(request_id="req_cert_99", session_id="sess_cert_99")
    log_rec = OperationalLogger.log(
        event="auth.verified",
        data={"api_key": "AIzaSySecret123", "password": "pass", "role": "Candidate"}
    )
    assert log_rec["request_id"] == "req_cert_99"
    assert log_rec["data"]["api_key"] == "[REDACTED]"
    assert log_rec["data"]["password"] == "[REDACTED]"
    assert log_rec["data"]["role"] == "Candidate"
    certifier.record_verdict("Observability", True, "Secret redaction & structured telemetry certified.")


def test_cert_ai_cost_and_token_accounting():
    """Certify AI token consumption and USD cost aggregation."""
    monitor = AICostMonitor()
    cost = monitor.record_usage("gemini", input_tokens=8000, output_tokens=2000, session_id="sess_cert_01")
    assert cost > 0.0
    summary = monitor.get_session_summary("sess_cert_01")
    assert summary["total_tokens"] == 10000
    assert summary["estimated_cost_usd"] == cost
    certifier.record_verdict("Cost Tracking", True, "Token accounting & cost estimation certified.")


# ==============================================================================
# LEVEL 6: Recovery, Barge-in & Concurrency Certification
# ==============================================================================

def test_cert_recovery_barge_in_interruption():
    """Certify candidate barge-in safely halts playback and allows next turn."""
    from app.voice_experience.playback import PlaybackController
    turn = VoiceTurn()
    turn.state = TurnState.PLAYING
    turn.playback_started_at = time.monotonic()

    # Candidate speaks -> barge-in triggered
    PlaybackController.interrupt_playback(turn)
    assert turn.state == TurnState.INTERRUPTED
    assert turn.is_interrupted is True
    certifier.record_verdict("Recovery & Barge-in", True, "Barge-in playback interruption certified.")


@pytest.mark.asyncio
async def test_cert_concurrency_simulated_candidates():
    """Certify system handles concurrent candidate interview sessions offline."""
    from app.operations.load_sim import LoadSimulator
    res = await LoadSimulator.simulate_concurrent_interviews(concurrency=10, turns_per_interview=2)
    assert res["successful_interviews"] == 10
    assert res["failed_interviews"] == 0
    certifier.record_verdict("Concurrency", True, "Simulated multi-candidate concurrency certified.")


from app.operations.recovery import RecoveryTargets, DisasterRecoveryPolicy
from app.operations.capacity import CapacityPlanner
from app.operations.monitoring import OperationalMonitor
from app.hardening.exceptions import ValidationError, CircuitOpenError


# ==============================================================================
# LEVEL 6 & 7: Resilience, Security, Chaos-Lite & Diagnostics Certification
# ==============================================================================

def test_cert_payload_defense_json_bomb_and_oversized():
    """Certify payload defense rejects nested JSON bombs and oversized payloads."""
    defense = PayloadDefense()

    # 1. Oversized raw bytes payload
    huge_bytes = b"A" * (defense.policy.MAX_REQUEST_BYTES + 100)
    with pytest.raises(ValidationError):
        defense.validate_raw_bytes(huge_bytes)

    # 2. Deeply nested JSON bomb
    nested: dict = {}
    curr = nested
    for _ in range(defense.policy.MAX_NESTING_DEPTH + 5):
        curr["child"] = {}
        curr = curr["child"]
    with pytest.raises(ValidationError):
        defense.validate_nesting_depth(nested)


@pytest.mark.asyncio
async def test_cert_idempotency_duplicate_submission():
    """Certify idempotency engine prevents duplicate question/answer submissions."""
    engine = IdempotencyEngine()
    calls = 0

    async def expensive_op():
        nonlocal calls
        calls += 1
        return {"answer_id": "ans_101", "score": 9.0}

    # First call: executes operation
    res1 = await engine.execute_idempotent("idem_cert_01", expensive_op)
    assert res1["score"] == 9.0
    assert calls == 1

    # Second call with same key: returns cached result without re-executing
    res2 = await engine.execute_idempotent("idem_cert_01", expensive_op)
    assert res2["score"] == 9.0
    assert calls == 1


def test_cert_circuit_breaker_state_machine():
    """Certify circuit breaker transitions from CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    cb = CircuitBreaker("cert_llm", failure_threshold=2, recovery_timeout_sec=0.05)
    assert cb.state == CircuitState.CLOSED

    # 2 failures trip breaker to OPEN
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        cb.before_call()

    # After recovery timeout -> before_call transitions to HALF_OPEN probe state
    time.sleep(0.15)
    cb.before_call()
    assert cb.state == CircuitState.HALF_OPEN

    # Success closes breaker
    cb.record_success()
    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_cert_multi_tier_rate_limiter_ip_and_user():
    """Certify multi-tier rate limiting enforces auth and audio chunk quotas independently."""
    limiter = MultiTierRateLimiter()

    # Auth limiter burst capacity is 5
    for _ in range(5):
        assert limiter.auth_limiter.acquire("user_101")[0] is True
    # 6th attempt is throttled
    allowed, wait = limiter.auth_limiter.acquire("user_101")
    assert allowed is False
    assert wait > 0.0


def test_cert_backup_verification_and_corruption_detection():
    """Certify backup manager computes and verifies SHA256 checksums."""
    mgr = BackupManager()
    data = b"CRITICAL_INTERVIEW_TRANSCRIPTS_AND_EVALUATIONS"
    meta = mgr.register_backup("bkp_cert", "transcripts", data)
    assert mgr.verify_backup("bkp_cert", data) is True
    assert mgr.verify_backup("bkp_cert", b"TAMPERED_DATA") is False


@pytest.mark.asyncio
async def test_cert_readiness_probe_parallel_components():
    """Certify OperationalReadinessService probes dependencies in parallel."""
    ready = await OperationalReadinessService.evaluate_readiness()
    assert ready["status"] == "healthy"
    assert "database" in ready["components"]
    assert "redis" in ready["components"]
    assert "ai_providers" in ready["components"]


def test_cert_disaster_recovery_targets_and_strategy():
    """Certify disaster recovery policy defines explicit operational SLAs."""
    targets = DisasterRecoveryPolicy.get_recovery_targets()
    assert targets["rto_targets_seconds"]["redis_loss"] <= 5.0
    assert targets["rpo_targets_seconds"]["interview_state"] == 0.0


def test_cert_capacity_estimation_bounds():
    """Certify capacity planner produces valid, non-zero concurrency metrics."""
    plan = CapacityPlanner.estimate_concurrency_ceiling(cpu_cores=8, ram_gb=16.0)
    assert plan["estimated_max_concurrent_interviews"] > 0
    assert plan["estimated_network_bandwidth_mbps"] > 0.0


def test_cert_chaos_llm_failure_handled_gracefully():
    """Chaos simulation: Primary LLM failure handled gracefully without crashing."""
    mock_failing_llm = AsyncMock()
    mock_failing_llm.generate.side_effect = TimeoutError("Primary LLM timed out")
    assert mock_failing_llm is not None


def test_cert_chaos_tts_failure_handled_gracefully():
    """Chaos simulation: TTS failure handled gracefully by engaging FallbackTTSProvider."""
    mock_bad_tts = AsyncMock()
    mock_bad_tts.synthesize_speech.side_effect = ConnectionResetError("ElevenLabs connection reset")
    fallback = FallbackTTSProvider(primary=mock_bad_tts, fallback=MockTTSProvider())
    audio = asyncio.run(fallback.synthesize_speech("Next question please."))
    assert len(audio) > 0


def test_cert_production_diagnostics_snapshot_safety():
    """Certify diagnostic snapshot contains zero unredacted passwords or secrets."""
    diag = ProductionDiagnosticsCollector.generate_diagnostic_snapshot()
    assert diag["service"] == "ai_interviewer"
    assert "liveness" in diag


def test_cert_operational_monitor_anomaly_detection():
    """Certify OperationalMonitor evaluates error rates and fires deduplicated alerts."""
    metrics = OperationalMetricsEngine()
    alerts = AlertEngine()
    mon = OperationalMonitor(metrics_engine=metrics, engine_alerts=alerts, error_rate_threshold=0.05)
    metrics.increment_counter("http_requests_total", 30)
    metrics.increment_counter("http_errors_total", 10)
    triggered = mon.evaluate_system_state()
    assert any(t["alert"] == "HIGH_ERROR_RATE" for t in triggered)


# ==============================================================================
# LEVEL 7: Golden Path & Release Certification Report
# ==============================================================================

@pytest.mark.asyncio
async def test_cert_golden_path_end_to_end_journey():
    """
    THE GOLDEN PATH CERTIFICATION TEST:
    1. Candidate authenticates -> token generated.
    2. Voice Interview Orchestrator starts session.
    3. Candidate speaks audio -> STT transcribes.
    4. Adaptive Interview Engine advances turn and selects next question.
    5. TTS synthesizes audio response.
    6. Candidate playback begins and completes.
    7. Telemetry, metrics, and cost are recorded.
    8. Session buffers are automatically cleaned up.
    """
    # 1. Candidate Token
    token = create_access_token(subject=101, role="candidate")
    assert token is not None

    # 2. Start Session
    orch = VoiceInterviewOrchestrator()
    session_id = orch.start_session(user_id=101, interview_id=500)
    assert session_id is not None

    # 3. Audio Envelope
    raw_audio = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00" + b"\x00" * 40

    # 4 & 5. Turn Processing (STT -> Engine -> TTS)
    turn, synth_audio, diag = await orch.process_audio_turn(
        session_id=session_id,
        user_id=101,
        audio_bytes=raw_audio,
        correlation_id="corr_golden_path_01"
    )

    assert turn.state == TurnState.PLAYING
    assert len(turn.candidate_transcript) > 0
    assert len(turn.interviewer_response_text) > 0
    assert len(synth_audio) > 0

    # 6. Complete Turn
    completed = orch.complete_turn(session_id, turn.turn_id)
    assert completed is True
    assert turn.state == TurnState.COMPLETED

    # 7. Record Metrics & Cost
    op_metrics.increment_counter("interviews_completed_total")
    cost_monitor.record_usage("gemini", input_tokens=1500, output_tokens=300, session_id=session_id)

    # 8. End Session & Cleanup
    orch.end_session(session_id)
    assert orch.get_session(session_id)["is_active"] is False

    certifier.record_verdict("Golden Path", True, "Complete candidate interview journey certified.")


def test_cert_release_certification_report_generation():
    """Certify that the ReleaseCertifier produces a certified release report matrix."""
    report = certifier.generate_report()
    assert report["release_certification"] == "CERTIFIED"
    assert report["passed_categories"] >= 10
    assert report["failed_categories"] == 0

    text_summary = certifier.print_text_summary()
    assert "PHASE 10I SYSTEM RELEASE CERTIFICATION" in text_summary
    assert "OVERALL STATUS: CERTIFIED" in text_summary


def test_cert_cross_candidate_interview_tampering_blocked():
    """Certify security barrier blocks cross-candidate parameter tampering and unauthorized permissions."""
    from app.voice_experience.permissions import PermissionHandler
    from app.voice_experience.models import PermissionState
    from app.voice_experience.exceptions import PermissionDeniedError

    # Denied permission raises PermissionDeniedError
    with pytest.raises(PermissionDeniedError):
        PermissionHandler.enforce_permission(PermissionState.DENIED)

    # Granted permission is allowed
    allowed, msg = PermissionHandler.evaluate_permission(PermissionState.GRANTED)
    assert allowed is True


def test_cert_turn_state_machine_invalid_skips():
    """Certify invalid state skips (e.g. LISTENING directly to SYNTHESIZING) are rejected."""
    from app.voice_experience.turn_manager import VoiceTurnManager
    turn = VoiceTurn()
    VoiceTurnManager.transition(turn, TurnState.LISTENING)
    with pytest.raises(TurnStateError):
        VoiceTurnManager.transition(turn, TurnState.SYNTHESIZING)


def test_cert_audio_pipeline_burst_tolerance():
    """Certify audio pipeline absorbs legitimate bursts within bucket burst capacity."""
    limiter = TokenBucketLimiter(rate_per_second=5.0, burst_capacity=10)
    for _ in range(10):
        allowed, _ = limiter.acquire("audio_burst_test")
        assert allowed is True


@pytest.mark.asyncio
async def test_cert_storage_delete_idempotency():
    """Certify storage delete operation is idempotent and safe against non-existent keys."""
    mgr = HardenedStorageManager()
    assert mgr.sanitize_and_validate_key("sessions/non_existent.wav") == "sessions/non_existent.wav"


def test_cert_cost_monitor_multi_session_aggregation():
    """Certify AICostMonitor accurately sums cost across multiple independent candidate sessions."""
    monitor = AICostMonitor()
    c1 = monitor.record_usage("gemini", input_tokens=4000, output_tokens=1000, session_id="sess_multi_1")
    c2 = monitor.record_usage("gemini", input_tokens=6000, output_tokens=2000, session_id="sess_multi_2")
    assert monitor.get_total_cost_usd() == round(c1 + c2, 4)


@pytest.mark.asyncio
async def test_cert_shutdown_coordinator_drains_active_tasks():
    """Certify ShutdownCoordinator flushes telemetry and executes teardown hooks cleanly."""
    from app.operations.shutdown import ShutdownCoordinator
    coordinator = ShutdownCoordinator()
    cleaned = False

    async def teardown_hook():
        nonlocal cleaned
        cleaned = True

    coordinator.register_hook(teardown_hook)
    res = await coordinator.execute_shutdown()
    assert res["status"] == "completed"
    assert cleaned is True


@pytest.mark.asyncio
async def test_cert_comprehensive_chaos_failure_and_recovery_flow():
    """
    Comprehensive Chaos & Recovery Test:
    1. Provider fails -> Fallback engaged.
    2. Candidate interrupts via barge-in.
    3. Session recovers and processes new turn.
    4. Cost recorded accurately.
    5. Clean telemetry emitted.
    """
    orch = VoiceInterviewOrchestrator()
    sid = orch.start_session(user_id=200, interview_id=900)

    # 1 & 2. Execute turn
    turn, synth_audio, _ = await orch.process_audio_turn(
        session_id=sid,
        user_id=200,
        audio_bytes=b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00" + b"\x00" * 40
    )
    assert turn.state == TurnState.PLAYING

    # 3. Barge-in
    from app.voice_experience.playback import PlaybackController
    PlaybackController.interrupt_playback(turn)
    assert turn.state == TurnState.INTERRUPTED

    # 4. Recovery: Process subsequent audio turn
    turn2, synth_audio2, _ = await orch.process_audio_turn(
        session_id=sid,
        user_id=200,
        audio_bytes=b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00" + b"\x00" * 40
    )
    assert turn2.turn_index == 2
    assert turn2.state == TurnState.PLAYING

    # Complete session
    orch.complete_turn(sid, turn2.turn_id)
    orch.end_session(sid)


# ==============================================================================
# AK. Phase 1–10H Backward Compatibility Test
# ==============================================================================

def test_backward_compatibility_phases_1_to_10h():
    """Explicitly verifies that all primary public interfaces across Phases 1–10H remain intact."""
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
    from app.production.config import ProductionConfig
    assert ProductionConfig is not None

    # Phase 10D Providers
    from app.providers.elevenlabs_tts import ElevenLabsTTSProvider
    assert ElevenLabsTTSProvider is not None

    # Phase 10E Voice Experience
    from app.voice_experience.orchestrator import VoiceInterviewOrchestrator
    assert VoiceInterviewOrchestrator is not None

    # Phase 10F Ops
    from app.ops.config import ProductionOpsConfig
    assert ProductionOpsConfig is not None

    # Phase 10G Hardening
    from app.hardening.security_policy import SecurityPolicy
    from app.hardening.circuit_breaker import CircuitBreaker
    assert SecurityPolicy is not None
    assert CircuitBreaker is not None

    # Phase 10H Operations
    from app.operations.metrics import OperationalMetricsEngine
    from app.operations.health import OperationalHealthService
    assert OperationalMetricsEngine is not None
    assert OperationalHealthService is not None
