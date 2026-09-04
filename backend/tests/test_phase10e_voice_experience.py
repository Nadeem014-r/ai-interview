"""Phase 10E: Comprehensive End-to-End Voice Experience Test Suite.

Tests full turn orchestration: Audio capture -> STT -> Phase 9 Adaptive Engine ->
TTS synthesis -> Playback lifecycle -> Candidate interruption -> Cleanup & Diagnostics.
"""

import time
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.models import Interview, InterviewState
from app.providers.exceptions import ProviderAuthenticationError, ProviderUnavailableError
from app._archive.voice_experience.config import VoiceExperienceConfig
from app._archive.voice_experience.exceptions import (
    VoiceExperienceError,
    TurnStateError,
    SilenceDetectedError,
    VoiceSessionOwnershipError,
    PermissionDeniedError,
)
from app._archive.voice_experience.models import (
    TurnState,
    PermissionState,
    LatencyClassification,
    VoiceTurn,
)
from app._archive.voice_experience.turn_manager import VoiceTurnManager
from app._archive.voice_experience.playback import PlaybackController
from app._archive.voice_experience.diagnostics import VoiceDiagnostics
from app._archive.voice_experience.permissions import PermissionHandler
from app._archive.voice_experience.cleanup import AudioLifecycleManager
from app._archive.voice_experience.health import VoiceExperienceHealthChecker
from app._archive.voice_experience.orchestrator import VoiceInterviewOrchestrator


# ==============================================================================
# A, B, C, D & E. Session & Turn State Machine Tests
# ==============================================================================

def test_voice_turn_state_machine_valid_transitions():
    """Verify VoiceTurnManager allows valid state progression."""
    turn = VoiceTurn()
    assert turn.state == TurnState.IDLE

    VoiceTurnManager.transition(turn, TurnState.LISTENING)
    VoiceTurnManager.transition(turn, TurnState.TRANSCRIBING)
    VoiceTurnManager.transition(turn, TurnState.THINKING)
    VoiceTurnManager.transition(turn, TurnState.GENERATING)
    VoiceTurnManager.transition(turn, TurnState.SYNTHESIZING)
    VoiceTurnManager.transition(turn, TurnState.PLAYING)
    VoiceTurnManager.transition(turn, TurnState.COMPLETED)
    assert turn.state == TurnState.COMPLETED


def test_voice_turn_state_machine_blocks_illegal_transitions():
    """Verify VoiceTurnManager rejects illegal state skips."""
    turn = VoiceTurn()
    # Illegal: IDLE -> SYNTHESIZING
    with pytest.raises(TurnStateError, match="Illegal voice turn state transition"):
        VoiceTurnManager.transition(turn, TurnState.SYNTHESIZING)

    # Illegal: COMPLETED -> LISTENING
    turn.state = TurnState.COMPLETED
    with pytest.raises(TurnStateError, match="Illegal voice turn state transition"):
        VoiceTurnManager.transition(turn, TurnState.LISTENING)


# ==============================================================================
# N, O & P. Playback Lifecycle & Barge-in Interruption Tests
# ==============================================================================

def test_playback_lifecycle_and_candidate_barge_in():
    """Verify playback starts, can be interrupted by candidate, and records interruption flag."""
    turn = VoiceTurn()
    VoiceTurnManager.transition(turn, TurnState.LISTENING)
    VoiceTurnManager.transition(turn, TurnState.TRANSCRIBING)
    VoiceTurnManager.transition(turn, TurnState.GENERATING)
    VoiceTurnManager.transition(turn, TurnState.SYNTHESIZING)

    # Start playback
    PlaybackController.start_playback(turn)
    assert turn.state == TurnState.PLAYING
    assert turn.playback_started_at is not None

    # Candidate interrupts interviewer
    PlaybackController.interrupt_playback(turn)
    assert turn.state == TurnState.INTERRUPTED
    assert turn.is_interrupted is True
    assert turn.completed_at is not None


# ==============================================================================
# Q & R. Silence Handling & Audio Size Validation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_silence_detection_handles_empty_speech():
    """Verify empty or whitespace transcript raises SilenceDetectedError without calling interview engine."""
    orchestrator = VoiceInterviewOrchestrator()
    sid = orchestrator.start_session(user_id=1, interview_id=10)

    # Mock STT to return empty transcript
    mock_stt = AsyncMock()
    mock_stt.transcribe_audio.return_value = {"text": "   "}

    with patch.object(orchestrator.provider_mgr, "get_stt_provider", return_value=mock_stt):
        with pytest.raises(SilenceDetectedError, match="No meaningful candidate speech"):
            await orchestrator.process_audio_turn(
                session_id=sid,
                user_id=1,
                audio_bytes=b"SILENT_AUDIO_BYTES"
            )


@pytest.mark.asyncio
async def test_audio_size_validation_enforcement():
    """Verify oversized audio payload is rejected with error."""
    orchestrator = VoiceInterviewOrchestrator()
    sid = orchestrator.start_session(user_id=1, interview_id=10)

    huge_audio = b"X" * (orchestrator.config.MAX_TURN_AUDIO_BYTES + 1024)
    with pytest.raises(VoiceExperienceError, match="exceeds limit"):
        await orchestrator.process_audio_turn(
            session_id=sid,
            user_id=1,
            audio_bytes=huge_audio
        )


# ==============================================================================
# T. Session Ownership Security Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_session_ownership_enforcement():
    """Verify unauthorized candidate is blocked from processing turns on another user's session."""
    orchestrator = VoiceInterviewOrchestrator()
    sid = orchestrator.start_session(user_id=10, interview_id=5)

    # User 99 attempts to process turn on User 10's session
    with pytest.raises(VoiceSessionOwnershipError, match="not authorized"):
        await orchestrator.process_audio_turn(
            session_id=sid,
            user_id=99,
            audio_bytes=b"AUDIO"
        )


# ==============================================================================
# Z & AA. Latency Measurement & Classification Tests
# ==============================================================================

def test_latency_classification_ranges():
    """Verify VoiceDiagnostics categorizes latencies into FAST, NORMAL, SLOW, TIMEOUT."""
    target = 1000.0  # 1s target
    assert VoiceDiagnostics.classify_latency(500.0, target) == LatencyClassification.FAST
    assert VoiceDiagnostics.classify_latency(1100.0, target) == LatencyClassification.NORMAL
    assert VoiceDiagnostics.classify_latency(1800.0, target) == LatencyClassification.SLOW
    assert VoiceDiagnostics.classify_latency(2500.0, target) == LatencyClassification.TIMEOUT


def test_turn_diagnostics_generation():
    """Verify generate_turn_diagnostics constructs complete secret-safe telemetry."""
    turn = VoiceTurn(turn_index=2)
    turn.stt_started_at = 10.0
    turn.stt_completed_at = 10.5  # 500ms
    turn.interview_started_at = 10.5
    turn.interview_completed_at = 11.2  # 700ms
    turn.tts_started_at = 11.2
    turn.tts_completed_at = 11.8  # 600ms
    turn.completed_at = 12.0

    diag = VoiceDiagnostics.generate_turn_diagnostics(turn, session_id="s123", correlation_id="corr_456")
    assert diag["session_id"] == "s123"
    assert diag["correlation_id"] == "corr_456"
    assert diag["latencies_ms"]["stt"] == 500.0
    assert diag["classifications"]["stt"] in ("FAST", "NORMAL")


# ==============================================================================
# 19. Permission Handler Tests
# ==============================================================================

def test_permission_handler_evaluation_and_enforcement():
    """Verify PermissionHandler allows granted permissions and blocks denied states."""
    allowed, msg = PermissionHandler.evaluate_permission(PermissionState.GRANTED)
    assert allowed is True
    PermissionHandler.enforce_permission(PermissionState.GRANTED)

    allowed_denied, msg_denied = PermissionHandler.evaluate_permission(PermissionState.DENIED)
    assert allowed_denied is False
    with pytest.raises(PermissionDeniedError, match="denied"):
        PermissionHandler.enforce_permission(PermissionState.DENIED)


# ==============================================================================
# 23. Pipeline Health Check Tests
# ==============================================================================

def test_voice_experience_pipeline_health():
    """Verify VoiceExperienceHealthChecker inspects STT, TTS, and transport."""
    health = VoiceExperienceHealthChecker.evaluate_voice_pipeline()
    assert health["status"] in ("READY", "DEGRADED", "NOT_READY")
    assert "realtime_transport" in health["pipeline"]
    assert "speech_to_text" in health["pipeline"]
    assert "text_to_speech" in health["pipeline"]


# ==============================================================================
# 24. Audio Lifecycle & Buffer Cleanup Tests
# ==============================================================================

def test_audio_lifecycle_cleanup():
    """Verify AudioLifecycleManager safely releases raw audio bytes."""
    turn = VoiceTurn(audio_bytes=b"RAW_RECORDED_AUDIO_STREAM_DATA")
    AudioLifecycleManager.cleanup_turn_audio(turn)
    assert turn.audio_bytes is None


# ==============================================================================
# AF. End-to-End Happy Path Orchestration Test
# ==============================================================================

@pytest.mark.asyncio
async def test_end_to_end_happy_path_voice_turn():
    """
    Simulates complete happy-path voice interaction turn:
    1. Candidate speaks audio.
    2. STT transcribes answer.
    3. Interview engine processes answer and generates follow-up question.
    4. TTS synthesizes interviewer audio.
    5. Playback starts and completes successfully.
    """
    orchestrator = VoiceInterviewOrchestrator()
    session_id = orchestrator.start_session(user_id=1, interview_id=10)

    # 1. Process turn
    raw_candidate_audio = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00" + b"\x00" * 40
    turn, synthesized_audio, diagnostics = await orchestrator.process_audio_turn(
        session_id=session_id,
        user_id=1,
        audio_bytes=raw_candidate_audio,
        correlation_id="corr_test_happy"
    )

    # 2. Verify state progression & artifacts
    assert turn.state == TurnState.PLAYING
    assert len(turn.candidate_transcript) > 0
    assert len(turn.interviewer_response_text) > 0
    assert len(synthesized_audio) > 0
    assert diagnostics["latencies_ms"]["total"] >= 0.0

    # 3. Complete playback
    completed = orchestrator.complete_turn(session_id, turn.turn_id)
    assert completed is True
    assert turn.state == TurnState.COMPLETED

    # 4. End session
    orchestrator.end_session(session_id)
    assert orchestrator.get_session(session_id)["is_active"] is False


# ==============================================================================
# AG. End-to-End Fallback / Failure Path Orchestration Test
# ==============================================================================

@pytest.mark.asyncio
async def test_end_to_end_failure_fallback_path():
    """
    Simulates TTS provider failure:
    1. Candidate speaks.
    2. STT & Interview engine succeed.
    3. ElevenLabs TTS throws transient error -> Fallback mock TTS catches and synthesizes.
    4. Text question remains available and session remains intact.
    """
    orchestrator = VoiceInterviewOrchestrator()
    session_id = orchestrator.start_session(user_id=1, interview_id=10)

    # Configure primary TTS to fail with ProviderUnavailableError
    mock_failing_tts = AsyncMock()
    mock_failing_tts.synthesize_speech.side_effect = ProviderUnavailableError("ElevenLabs down", provider="elevenlabs")

    from app.providers.fallback import FallbackTTSProvider
    from app.ai.mock_provider import MockTTSProvider
    safe_fallback = FallbackTTSProvider(primary=mock_failing_tts, fallback=MockTTSProvider())

    with patch.object(orchestrator.provider_mgr, "get_tts_provider", return_value=safe_fallback):
        turn, audio, diag = await orchestrator.process_audio_turn(
            session_id=session_id,
            user_id=1,
            audio_bytes=b"CANDIDATE_INPUT_AUDIO"
        )

        assert turn.state == TurnState.PLAYING
        assert len(turn.interviewer_response_text) > 0
        assert len(audio) > 0
        assert safe_fallback.last_fallback_error is not None


@pytest.mark.asyncio
async def test_multi_turn_sequential_execution():
    """Verify orchestrator successfully progresses multiple sequential turns in a session."""
    orchestrator = VoiceInterviewOrchestrator()
    sid = orchestrator.start_session(user_id=1, interview_id=10)

    # Turn 1
    raw_audio = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00" + b"\x00" * 40
    turn1, audio1, diag1 = await orchestrator.process_audio_turn(sid, user_id=1, audio_bytes=raw_audio)
    assert turn1.turn_index == 1
    orchestrator.complete_turn(sid, turn1.turn_id)

    # Turn 2
    turn2, audio2, diag2 = await orchestrator.process_audio_turn(sid, user_id=1, audio_bytes=raw_audio)
    assert turn2.turn_index == 2
    orchestrator.complete_turn(sid, turn2.turn_id)

    assert orchestrator.get_session(sid)["turn_counter"] == 2


@pytest.mark.asyncio
async def test_stt_failure_graceful_handling():
    """Verify STT provider failure marks turn failed but preserves session for retry."""
    orchestrator = VoiceInterviewOrchestrator()
    sid = orchestrator.start_session(user_id=1, interview_id=10)

    mock_failing_stt = AsyncMock()
    mock_failing_stt.transcribe_audio.side_effect = ProviderUnavailableError("Whisper STT cluster down", provider="whisper")

    with patch.object(orchestrator.provider_mgr, "get_stt_provider", return_value=mock_failing_stt):
        with pytest.raises(ProviderUnavailableError, match="Whisper STT"):
            await orchestrator.process_audio_turn(sid, user_id=1, audio_bytes=b"AUDIO")

    # Session is still intact and ready for retry
    assert orchestrator.get_session(sid)["is_active"] is True

