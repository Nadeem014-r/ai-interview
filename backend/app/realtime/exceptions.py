"""Phase 10B: Normalized Realtime Exception Hierarchy.

Provides clear, categorized, and client-safe exception definitions for
WebSocket transport, protocol parsing, authentication, audio streaming, and session lifecycle.
"""

from typing import Optional, Any


class RealtimeError(Exception):
    """Base exception for all realtime subsystem operations."""

    def __init__(self, message: str, code: str = "REALTIME_ERROR", raw_error: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.raw_error = raw_error

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message
        }


class WebSocketAuthenticationError(RealtimeError):
    """WebSocket client failed authentication."""
    def __init__(self, message: str = "Authentication failed", raw_error: Optional[Any] = None):
        super().__init__(message, code="AUTH_FAILED", raw_error=raw_error)


class WebSocketAuthorizationError(RealtimeError):
    """Authenticated client is not authorized for the target interview."""
    def __init__(self, message: str = "Authorization denied for this interview", raw_error: Optional[Any] = None):
        super().__init__(message, code="AUTHORIZATION_DENIED", raw_error=raw_error)


class InvalidRealtimeMessageError(RealtimeError):
    """Message failed envelope, version, or payload schema validation."""
    def __init__(self, message: str = "Invalid realtime message format", raw_error: Optional[Any] = None):
        super().__init__(message, code="INVALID_MESSAGE", raw_error=raw_error)


class AudioLimitExceededError(RealtimeError):
    """Audio chunk or session buffer exceeds maximum allowed size."""
    def __init__(self, message: str = "Audio limit exceeded", raw_error: Optional[Any] = None):
        super().__init__(message, code="AUDIO_LIMIT_EXCEEDED", raw_error=raw_error)


class SessionNotFoundError(RealtimeError):
    """Requested realtime session was not found."""
    def __init__(self, message: str = "Session not found", raw_error: Optional[Any] = None):
        super().__init__(message, code="SESSION_NOT_FOUND", raw_error=raw_error)


class SessionExpiredError(RealtimeError):
    """Realtime session has expired."""
    def __init__(self, message: str = "Session has expired", raw_error: Optional[Any] = None):
        super().__init__(message, code="SESSION_EXPIRED", raw_error=raw_error)


class InvalidSessionStateError(RealtimeError):
    """Illegal session state transition attempted."""
    def __init__(self, message: str = "Invalid session state transition", raw_error: Optional[Any] = None):
        super().__init__(message, code="INVALID_SESSION_STATE", raw_error=raw_error)


class ReplayDetectedError(RealtimeError):
    """Duplicate or out-of-order sequence detected (replay attack / duplicate chunk)."""
    def __init__(self, message: str = "Replayed or out-of-order sequence detected", raw_error: Optional[Any] = None):
        super().__init__(message, code="REPLAY_DETECTED", raw_error=raw_error)


class RateLimitExceededError(RealtimeError):
    """Client has exceeded rate limit thresholds."""
    def __init__(self, message: str = "Rate limit exceeded", retry_after_seconds: Optional[float] = None, raw_error: Optional[Any] = None):
        super().__init__(message, code="RATE_LIMITED", raw_error=raw_error)
        self.retry_after_seconds = retry_after_seconds

    def to_dict(self) -> dict:
        data = super().to_dict()
        if self.retry_after_seconds is not None:
            data["retry_after_seconds"] = self.retry_after_seconds
        return data


class RealtimeProviderTimeoutError(RealtimeError):
    """Underlying STT/TTS or interview provider timed out."""
    def __init__(self, message: str = "Realtime provider timed out", raw_error: Optional[Any] = None):
        super().__init__(message, code="PROVIDER_TIMEOUT", raw_error=raw_error)


class RealtimeDependencyUnavailableError(RealtimeError):
    """Critical realtime dependency (Redis, Storage) is unavailable."""
    def __init__(self, message: str = "Realtime dependency unavailable", raw_error: Optional[Any] = None):
        super().__init__(message, code="DEPENDENCY_UNAVAILABLE", raw_error=raw_error)


class StorageError(RealtimeError):
    """Object storage access or I/O failure."""
    def __init__(self, message: str = "Storage operation failed", raw_error: Optional[Any] = None):
        super().__init__(message, code="STORAGE_ERROR", raw_error=raw_error)


class RedisUnavailableError(RealtimeDependencyUnavailableError):
    """Redis connection failure."""
    def __init__(self, message: str = "Redis is unavailable", raw_error: Optional[Any] = None):
        super().__init__(message, raw_error=raw_error)
        self.code = "REDIS_UNAVAILABLE"


class BackpressureError(RealtimeError):
    """Audio pipeline queue is saturated, backpressure triggered."""
    def __init__(self, message: str = "Pipeline queue saturated, backpressure active", raw_error: Optional[Any] = None):
        super().__init__(message, code="BACKPRESSURE_ACTIVE", raw_error=raw_error)
