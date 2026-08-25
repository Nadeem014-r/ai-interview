"""Phase 10E: Normalized Voice Experience Exception Hierarchy.

Categorizes turn lifecycle, interruption, silence detection, audio processing,
playback control, and permission evaluation without leaking credentials.
"""

from typing import Optional, Any, Dict


class VoiceExperienceError(Exception):
    """Base exception for all end-to-end voice experience operations."""

    def __init__(
        self,
        message: str,
        code: str = "VOICE_EXPERIENCE_ERROR",
        status_code: int = 400,
        raw_error: Optional[Any] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.raw_error = raw_error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "status_code": self.status_code
        }


class TurnStateError(VoiceExperienceError):
    """Invalid turn state transition or out-of-order turn progression."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, code="TURN_STATE_ERROR", status_code=409, raw_error=raw_error)


class InterruptionError(VoiceExperienceError):
    """Interruption or barge-in failure during audio playback."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, code="INTERRUPTION_ERROR", status_code=409, raw_error=raw_error)


class SilenceDetectedError(VoiceExperienceError):
    """No meaningful candidate speech detected in audio stream."""
    def __init__(self, message: str = "No meaningful speech detected in audio stream.", raw_error: Optional[Any] = None):
        super().__init__(message, code="SILENCE_DETECTED", status_code=422, raw_error=raw_error)


class PlaybackError(VoiceExperienceError):
    """Audio playback failure or buffer stream corruption."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, code="PLAYBACK_ERROR", status_code=500, raw_error=raw_error)


class PermissionDeniedError(VoiceExperienceError):
    """Client microphone or audio permissions denied or unavailable."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, code="PERMISSION_DENIED", status_code=403, raw_error=raw_error)


class VoiceSessionOwnershipError(VoiceExperienceError):
    """Candidate is not authorized to interact with the target voice session."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, code="SESSION_OWNERSHIP_ERROR", status_code=403, raw_error=raw_error)
