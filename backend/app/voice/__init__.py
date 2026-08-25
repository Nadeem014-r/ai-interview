"""Phase 10A: Voice Foundation Module Exports.
"""

from app.voice.exceptions import (
    VoiceError,
    AudioValidationError,
    UnsupportedAudioFormatError,
    AudioTooLargeError,
    AudioDurationError,
    STTError,
    STTTimeoutError,
    STTProviderError,
    TTSError,
    TTSTimeoutError,
    TTSProviderError,
    VoiceSecurityError,
    VoiceSessionError,
    VoiceCancelledError,
)
from app.voice.audio import AudioValidator, AudioMetadata
from app.voice.latency import LatencyTracker
from app.voice.security import VoiceSecurity
from app.voice.session import VoiceSession, VoiceSessionState, VoiceSessionManager
from app.voice.stt import SpeechToTextService
from app.voice.tts import TextToSpeechService

__all__ = [
    "VoiceError",
    "AudioValidationError",
    "UnsupportedAudioFormatError",
    "AudioTooLargeError",
    "AudioDurationError",
    "STTError",
    "STTTimeoutError",
    "STTProviderError",
    "TTSError",
    "TTSTimeoutError",
    "TTSProviderError",
    "VoiceSecurityError",
    "VoiceSessionError",
    "VoiceCancelledError",
    "AudioValidator",
    "AudioMetadata",
    "LatencyTracker",
    "VoiceSecurity",
    "VoiceSession",
    "VoiceSessionState",
    "VoiceSessionManager",
    "SpeechToTextService",
    "TextToSpeechService",
]
