"""Phase 10A: Voice Foundation Exception Hierarchy.

Provides clear, categorized exceptions for voice processing, audio validation,
speech-to-text, text-to-speech, session lifecycle, and security violations.
"""

from typing import Optional, Any


class VoiceError(Exception):
    """Base exception for all voice processing operations."""

    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.raw_error = raw_error

    def __str__(self) -> str:
        return self.message


class AudioValidationError(VoiceError):
    """Base exception for audio validation failures."""
    pass


class UnsupportedAudioFormatError(AudioValidationError):
    """Audio format or MIME type is not supported."""
    pass


class AudioTooLargeError(AudioValidationError):
    """Audio payload exceeds maximum allowable size in bytes."""
    pass


class AudioDurationError(AudioValidationError):
    """Audio duration exceeds allowable bounds or is too short."""
    pass


class STTError(VoiceError):
    """Base exception for Speech-to-Text operations."""
    pass


class STTTimeoutError(STTError):
    """STT provider request timed out."""
    pass


class STTProviderError(STTError):
    """STT provider failed to transcribe audio."""
    pass


class TTSError(VoiceError):
    """Base exception for Text-to-Speech operations."""
    pass


class TTSTimeoutError(TTSError):
    """TTS provider request timed out."""
    pass


class TTSProviderError(TTSError):
    """TTS provider failed to synthesize speech."""
    pass


class VoiceSecurityError(VoiceError):
    """Security violation detected during voice processing (e.g. path traversal, malicious payload)."""
    pass


class VoiceSessionError(VoiceError):
    """Voice session lifecycle or state transition failure."""
    pass


class VoiceCancelledError(VoiceError):
    """Voice operation was cancelled by the client or session manager."""
    pass
