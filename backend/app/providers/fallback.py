"""Phase 10D: Safe Deterministic Provider Fallback Wrappers.

Gracefully handles primary voice provider failure by delegating to deterministic
fallback providers while logging structured diagnostic telemetry.
"""

import logging
from typing import Dict, Any, Optional

from app.ai.base import TTSProvider, STTProvider
from app.providers.exceptions import (
    ProviderError,
    ProviderFallbackError,
    ProviderAuthenticationError,
)

logger = logging.getLogger("app.providers.fallback")


class FallbackTTSProvider(TTSProvider):
    """Wraps primary TTS provider with a safe fallback provider."""

    def __init__(self, primary: TTSProvider, fallback: TTSProvider):
        self.primary = primary
        self.fallback = fallback
        self.last_fallback_error: Optional[Exception] = None

    async def synthesize_speech(self, text: str, voice_id: str = "default") -> bytes:
        """Attempts primary TTS synthesis; cascades to fallback upon failure."""
        try:
            return await self.primary.synthesize_speech(text, voice_id=voice_id)
        except Exception as e:
            self.last_fallback_error = e
            logger.warning(
                "Primary TTS provider failed. Cascading to fallback provider. "
                f"Error type: {type(e).__name__}, Message: {str(e)}"
            )

            try:
                return await self.fallback.synthesize_speech(text, voice_id=voice_id)
            except Exception as fallback_exc:
                raise ProviderFallbackError(
                    f"Both primary and fallback TTS providers failed. Primary: {str(e)}, Fallback: {str(fallback_exc)}",
                    provider="fallback_tts",
                    raw_error=fallback_exc
                )


class FallbackSTTProvider(STTProvider):
    """Wraps primary STT provider with a safe fallback provider."""

    def __init__(self, primary: STTProvider, fallback: STTProvider):
        self.primary = primary
        self.fallback = fallback
        self.last_fallback_error: Optional[Exception] = None

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> Dict[str, Any]:
        """Attempts primary STT transcription; cascades to fallback upon failure."""
        try:
            return await self.primary.transcribe_audio(audio_bytes, filename=filename)
        except Exception as e:
            self.last_fallback_error = e
            logger.warning(
                "Primary STT provider failed. Cascading to fallback provider. "
                f"Error type: {type(e).__name__}, Message: {str(e)}"
            )

            try:
                res = await self.fallback.transcribe_audio(audio_bytes, filename=filename)
                # Mark metadata that fallback was used
                if isinstance(res, dict):
                    res["fallback_used"] = True
                    res["primary_error"] = type(e).__name__
                return res
            except Exception as fallback_exc:
                raise ProviderFallbackError(
                    f"Both primary and fallback STT providers failed. Primary: {str(e)}, Fallback: {str(fallback_exc)}",
                    provider="fallback_stt",
                    raw_error=fallback_exc
                )
