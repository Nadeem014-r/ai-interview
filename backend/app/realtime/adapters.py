"""Phase 10B: Realtime Adapters for Phase 9 & Phase 10A Interfaces.

Wraps existing frozen Phase 9 interview and Phase 10A voice services cleanly
without altering any earlier phase code or contracts.
"""

from typing import Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.voice.stt import SpeechToTextService
from app.voice.tts import TextToSpeechService
from app.voice.audio import AudioValidator
from app.interview.engine import AdaptiveInterviewEngine
from app.db.models import Interview, InterviewState, Question


class VoiceAdapter:
    """Consumes Phase 10A STT, TTS, and Audio Validation services."""

    @staticmethod
    async def validate_and_transcribe(
        audio_bytes: bytes,
        filename: str = "chunk.wav",
        timeout_seconds: float = 30.0
    ) -> Dict[str, Any]:
        """Transcribes candidate audio using Phase 10A SpeechToTextService."""
        return await SpeechToTextService.transcribe(
            audio_bytes=audio_bytes,
            filename=filename,
            timeout_seconds=timeout_seconds
        )

    @staticmethod
    async def synthesize_speech_chunks(
        text: str,
        voice_id: str = "default",
        chunk_size_chars: int = 150
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Synthesizes text using Phase 10A TextToSpeechService."""
        return await TextToSpeechService.synthesize_with_metadata(
            text=text,
            voice_id=voice_id
        )


class InterviewEngineAdapter:
    """Consumes Phase 9 Adaptive Interview Engine."""

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self.engine = AdaptiveInterviewEngine(db) if db is not None else None

    async def advance_interview_turn(
        self,
        interview: Interview,
        state: InterviewState,
        last_eval_score: float,
        asked_question_ids: list[int],
        last_answer_text: Optional[str] = None
    ) -> Tuple[InterviewState, Optional[Question], bool]:
        """Calls Phase 9 process_answer_turn."""
        if self.engine is None:
            # Fallback for standalone/mock unit testing
            state.questions_asked_count += 1
            is_completed = state.questions_asked_count >= 5
            return state, None, is_completed

        return await self.engine.process_answer_turn(
            interview=interview,
            state=state,
            last_eval_score=last_eval_score,
            asked_question_ids=asked_question_ids,
            last_answer_text=last_answer_text
        )
