"""Phase 10E: End-to-End Voice Interview Orchestrator.

Coordinates Speech-to-Text transcription, Phase 9 Adaptive Interview Engine turn advancement,
Text-to-Speech synthesis, playback management, barge-in interruption, and telemetry diagnostics.
"""

import time
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Interview, InterviewState
from app.realtime.adapters import InterviewEngineAdapter
from app.providers.provider_manager import provider_manager, ProviderManager
from app.voice_experience.config import experience_config, VoiceExperienceConfig
from app.voice_experience.models import TurnState, VoiceTurn, PermissionState
from app.voice_experience.turn_manager import VoiceTurnManager
from app.voice_experience.playback import PlaybackController
from app.voice_experience.diagnostics import VoiceDiagnostics
from app.voice_experience.cleanup import AudioLifecycleManager
from app.voice_experience.exceptions import (
    VoiceExperienceError,
    TurnStateError,
    SilenceDetectedError,
    VoiceSessionOwnershipError,
    PermissionDeniedError,
)

logger = logging.getLogger("app.voice_experience")


class VoiceInterviewOrchestrator:
    """Master coordinator of the real-time AI voice interview experience."""

    def __init__(
        self,
        provider_mgr: Optional[ProviderManager] = None,
        config: Optional[VoiceExperienceConfig] = None
    ):
        self.provider_mgr = provider_mgr or provider_manager
        self.config = config or experience_config
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._turns: Dict[str, Dict[str, VoiceTurn]] = {}  # session_id -> {turn_id: VoiceTurn}

    def start_session(
        self,
        user_id: int,
        interview_id: int,
        session_id: Optional[str] = None
    ) -> str:
        """Initializes a new voice interview session."""
        sid = session_id or f"vsess_{uuid.uuid4().hex[:12]}"
        self._sessions[sid] = {
            "session_id": sid,
            "user_id": user_id,
            "interview_id": interview_id,
            "created_at": time.time(),
            "turn_counter": 0,
            "is_active": True
        }
        self._turns[sid] = {}
        return sid

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves session metadata."""
        return self._sessions.get(session_id)

    async def process_audio_turn(
        self,
        session_id: str,
        user_id: int,
        audio_bytes: bytes,
        filename: str = "recording.wav",
        db: Optional[AsyncSession] = None,
        interview: Optional[Interview] = None,
        interview_state: Optional[InterviewState] = None,
        correlation_id: Optional[str] = None
    ) -> Tuple[VoiceTurn, bytes, Dict[str, Any]]:
        """
        Executes a complete voice turn:
        1. Validates session authorization and audio boundaries.
        2. STT: Transcribes candidate speech with silence detection.
        3. Interview Engine: Evaluates answer and generates next question.
        4. TTS: Synthesizes interviewer response audio.
        5. Returns turn record, synthesized audio bytes, and diagnostics.
        """
        session_meta = self._sessions.get(session_id)
        if not session_meta:
            raise VoiceExperienceError(f"Voice session '{session_id}' not found.", status_code=404)

        if session_meta["user_id"] != user_id:
            raise VoiceSessionOwnershipError(f"User {user_id} is not authorized for session {session_id}.")

        session_meta["turn_counter"] += 1
        turn = VoiceTurn(
            turn_index=session_meta["turn_counter"],
            audio_bytes=audio_bytes
        )
        self._turns[session_id][turn.turn_id] = turn

        try:
            # 1. State: LISTENING -> TRANSCRIBING
            VoiceTurnManager.transition(turn, TurnState.LISTENING)
            VoiceTurnManager.transition(turn, TurnState.TRANSCRIBING)

            # Audio size boundary check
            if len(audio_bytes) > self.config.MAX_TURN_AUDIO_BYTES:
                raise VoiceExperienceError(
                    f"Turn audio size ({len(audio_bytes)}B) exceeds limit ({self.config.MAX_TURN_AUDIO_BYTES}B).",
                    status_code=413
                )

            # 2. Stage: Speech-to-Text Transcription
            turn.stt_started_at = time.monotonic()
            stt_provider = self.provider_mgr.get_stt_provider(enable_fallback=True)
            stt_result = await stt_provider.transcribe_audio(audio_bytes, filename=filename)
            turn.stt_completed_at = time.monotonic()

            transcript = stt_result.get("text") or stt_result.get("transcript") or ""
            transcript = transcript.strip()
            turn.candidate_transcript = transcript

            # Silence / empty speech detection
            if len(transcript) < self.config.SILENCE_MIN_CHAR_COUNT:
                turn.state = TurnState.IDLE
                raise SilenceDetectedError("No meaningful candidate speech detected.")

            # 3. Stage: Interview Engine Turn Processing
            VoiceTurnManager.transition(turn, TurnState.THINKING)
            turn.interview_started_at = time.monotonic()

            # Adaptively advance interview turn via existing Phase 9 Engine
            engine_adapter = InterviewEngineAdapter(db=db)
            mock_int = interview or Interview(id=session_meta["interview_id"], candidate_id=user_id, company_id=1, role_id=1)
            mock_st = interview_state or InterviewState(interview_id=session_meta["interview_id"], current_topic="General", difficulty="medium", time_remaining_seconds=1800, questions_asked_count=0)

            state_out, next_q_obj, is_completed = await engine_adapter.advance_interview_turn(
                interview=mock_int,
                state=mock_st,
                last_eval_score=7.5,
                asked_question_ids=[],
                last_answer_text=transcript
            )
            turn.interview_completed_at = time.monotonic()

            if next_q_obj is not None:
                next_question_text = getattr(next_q_obj, "text", str(next_q_obj))
            elif is_completed:
                next_question_text = "Thank you for completing the interview. We have recorded all your responses."
            else:
                next_question_text = "Thank you for your answer. Could you elaborate on your experience with distributed architectures?"

            turn.interviewer_response_text = next_question_text

            # 4. Stage: Text-to-Speech Synthesis
            VoiceTurnManager.transition(turn, TurnState.GENERATING)
            VoiceTurnManager.transition(turn, TurnState.SYNTHESIZING)
            turn.tts_started_at = time.monotonic()

            tts_provider = self.provider_mgr.get_tts_provider(enable_fallback=True)
            synthesized_audio = await tts_provider.synthesize_speech(next_question_text)
            turn.tts_completed_at = time.monotonic()

            # 5. Playback initiation
            PlaybackController.start_playback(turn)

            # 6. Structured Diagnostics & Telemetry
            diagnostics = VoiceDiagnostics.generate_turn_diagnostics(
                turn=turn,
                session_id=session_id,
                correlation_id=correlation_id,
                config=self.config
            )

            return turn, synthesized_audio, diagnostics

        except Exception as e:
            turn.error = str(e)
            if turn.state not in (TurnState.IDLE, TurnState.COMPLETED, TurnState.INTERRUPTED):
                turn.state = TurnState.FAILED
            raise
        finally:
            if self.config.ENABLE_AUTO_CLEANUP:
                AudioLifecycleManager.cleanup_turn_audio(turn)

    def handle_candidate_interruption(self, session_id: str, turn_id: str) -> bool:
        """Halts active interviewer audio playback when candidate speaks."""
        turns = self._turns.get(session_id, {})
        turn = turns.get(turn_id)
        if turn and turn.state == TurnState.PLAYING:
            PlaybackController.interrupt_playback(turn)
            return True
        return False

    def complete_turn(self, session_id: str, turn_id: str) -> bool:
        """Marks playback and turn as successfully finished."""
        turns = self._turns.get(session_id, {})
        turn = turns.get(turn_id)
        if turn and turn.state == TurnState.PLAYING:
            PlaybackController.complete_playback(turn)
            return True
        return False

    def end_session(self, session_id: str) -> None:
        """Gracefully closes voice session and releases resources."""
        session_meta = self._sessions.get(session_id)
        if session_meta:
            session_meta["is_active"] = False
        turns = self._turns.get(session_id, {})
        AudioLifecycleManager.release_session_buffers(turns)
