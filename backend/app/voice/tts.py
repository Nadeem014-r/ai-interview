"""Phase 10A: Text-to-Speech Service.

Orchestrates input text validation, timeout enforcement, monotonic latency measurement,
cancellation support, and safe exception normalization for speech synthesis.
"""

import asyncio
from typing import Optional, Tuple, Dict, Any

from app.ai.factory import AIFactory
from app.voice.latency import LatencyTracker
from app.voice.session import VoiceSession, VoiceSessionState
from app.voice.security import VoiceSecurity, MAX_TTS_TEXT_CHARS
from app.voice.exceptions import (
    TTSError,
    TTSTimeoutError,
    TTSProviderError,
    VoiceCancelledError,
    VoiceSecurityError,
)


class TextToSpeechService:
    """Production TTS service with text validation, timeout, and monotonic latency measurement."""

    @staticmethod
    async def synthesize(
        text: str,
        voice_id: str = "default",
        session: Optional[VoiceSession] = None,
        timeout_seconds: float = 30.0
    ) -> bytes:
        """
        Synthesizes text into audio bytes.
        Preserves backward compatibility with existing callers expecting raw bytes.
        """
        audio_bytes, _ = await TextToSpeechService.synthesize_with_metadata(
            text=text,
            voice_id=voice_id,
            session=session,
            timeout_seconds=timeout_seconds
        )
        return audio_bytes

    @staticmethod
    async def synthesize_with_metadata(
        text: str,
        voice_id: str = "default",
        session: Optional[VoiceSession] = None,
        timeout_seconds: float = 30.0
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Synthesizes text into audio bytes and returns structured operation metadata.
        """
        tracker = LatencyTracker()

        # 1. Check session cancellation if provided
        if session:
            session.check_cancelled()
            session.transition_to(VoiceSessionState.PROCESSING_TTS)

        # 2. Text Validation Stage
        tracker.start_stage("text_validation")
        try:
            clean_text = VoiceSecurity.validate_text_length(text, max_chars=MAX_TTS_TEXT_CHARS)
        except Exception as e:
            if session:
                session.transition_to(VoiceSessionState.FAILED)
            raise TTSError(f"TTS text validation failed: {str(e)}", raw_error=e)
        val_latency = tracker.stop_stage("text_validation")

        # Check cancellation again before provider call
        if session:
            session.check_cancelled()

        # 3. Provider Invocation with Timeout
        tracker.start_stage("tts")
        tts_provider = AIFactory.get_tts_provider()

        try:
            audio_bytes = await asyncio.wait_for(
                tts_provider.synthesize_speech(clean_text, voice_id=voice_id or "default"),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError as e:
            if session:
                session.transition_to(VoiceSessionState.FAILED)
            raise TTSTimeoutError(f"TTS provider request timed out after {timeout_seconds} seconds.", raw_error=e)
        except VoiceCancelledError:
            if session:
                session.transition_to(VoiceSessionState.CANCELLED)
            raise
        except Exception as e:
            if session:
                session.transition_to(VoiceSessionState.FAILED)
            clean_msg = VoiceSecurity.mask_secrets(str(e))
            raise TTSProviderError(f"TTS provider failed: {clean_msg}", raw_error=e)

        tts_latency = tracker.stop_stage("tts")

        # 4. Audio Bytes Validation
        if not audio_bytes or len(audio_bytes) < 4:
            if session:
                session.transition_to(VoiceSessionState.FAILED)
            raise TTSError("TTS provider returned empty or invalid audio data.")

        metadata = {
            "size_bytes": len(audio_bytes),
            "voice_id": voice_id,
            "text_length": len(clean_text),
            "latency_ms": int(tracker.get_total_latency_ms()),
            "validation_latency_ms": val_latency,
            "tts_latency_ms": tts_latency,
            "success": True
        }

        if session:
            session.transition_to(VoiceSessionState.COMPLETED)
            session.metadata["tts_result"] = metadata

        return audio_bytes, metadata
