"""Phase 10D: AI Voice Provider Input Validation.

Guards against empty payloads, oversized requests, and malformed identifiers.
"""

import re
from typing import Optional
from app.providers.exceptions import ProviderValidationError


class ProviderValidator:
    """Input validation for Speech-to-Text and Text-to-Speech operations."""

    @staticmethod
    def validate_tts_input(text: Optional[str], voice_id: Optional[str] = "default", max_chars: int = 4000) -> None:
        """Validates text input for TTS synthesis."""
        if text is None or not text.strip():
            raise ProviderValidationError("TTS synthesis text cannot be empty or None.", provider="tts")

        clean_text = text.strip()
        if len(clean_text) > max_chars:
            raise ProviderValidationError(
                f"TTS text length ({len(clean_text)} chars) exceeds maximum allowable limit ({max_chars} chars).",
                provider="tts"
            )

        if voice_id is not None and not re.match(r'^[A-Za-z0-9_\-\.]{1,64}$', voice_id):
            raise ProviderValidationError(f"Invalid voice identifier: '{voice_id}'.", provider="tts")

    @staticmethod
    def validate_stt_input(audio_bytes: Optional[bytes], filename: Optional[str] = "audio.wav", max_bytes: int = 25 * 1024 * 1024) -> None:
        """Validates audio input for STT transcription."""
        if audio_bytes is None or len(audio_bytes) == 0:
            raise ProviderValidationError("STT audio payload cannot be empty or None.", provider="stt")

        if len(audio_bytes) > max_bytes:
            raise ProviderValidationError(
                f"STT audio size ({len(audio_bytes)}B) exceeds maximum allowable limit ({max_bytes}B).",
                provider="stt"
            )
