"""Phase 10D: Normalized AI Voice Provider Exception Hierarchy.

Categorizes provider authentication, rate limits, timeouts, network errors,
validation failures, and fallback routing without leaking secrets.
"""

from typing import Optional, Any, Dict


class ProviderError(Exception):
    """Base exception for all AI voice and audio provider operations."""

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        code: str = "PROVIDER_ERROR",
        status_code: Optional[int] = None,
        raw_error: Optional[Any] = None
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.code = code
        self.status_code = status_code
        self.raw_error = raw_error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "provider": self.provider,
            "status_code": self.status_code
        }


class ProviderAuthenticationError(ProviderError):
    """Authentication or authorization failure (e.g. 401/403, missing or invalid API key)."""
    def __init__(self, message: str, provider: str = "unknown", raw_error: Optional[Any] = None):
        super().__init__(message, provider=provider, code="PROVIDER_AUTH_ERROR", status_code=401, raw_error=raw_error)


class ProviderRateLimitError(ProviderError):
    """Rate limit or quota exhaustion (429)."""
    def __init__(self, message: str, provider: str = "unknown", retry_after: Optional[float] = None, raw_error: Optional[Any] = None):
        super().__init__(message, provider=provider, code="PROVIDER_RATE_LIMIT", status_code=429, raw_error=raw_error)
        self.retry_after = retry_after


class ProviderTimeoutError(ProviderError):
    """Request timed out or deadline exceeded."""
    def __init__(self, message: str, provider: str = "unknown", raw_error: Optional[Any] = None):
        super().__init__(message, provider=provider, code="PROVIDER_TIMEOUT", status_code=504, raw_error=raw_error)


class ProviderNetworkError(ProviderError):
    """Connection, DNS, or network-level transport failure."""
    def __init__(self, message: str, provider: str = "unknown", raw_error: Optional[Any] = None):
        super().__init__(message, provider=provider, code="PROVIDER_NETWORK_ERROR", status_code=503, raw_error=raw_error)


class ProviderUnavailableError(ProviderError):
    """Provider service unavailable or server error (5xx)."""
    def __init__(self, message: str, provider: str = "unknown", status_code: int = 500, raw_error: Optional[Any] = None):
        super().__init__(message, provider=provider, code="PROVIDER_UNAVAILABLE", status_code=status_code, raw_error=raw_error)


class ProviderResponseError(ProviderError):
    """Malformed response or empty payload returned by provider."""
    def __init__(self, message: str, provider: str = "unknown", raw_error: Optional[Any] = None):
        super().__init__(message, provider=provider, code="PROVIDER_RESPONSE_ERROR", status_code=502, raw_error=raw_error)


class ProviderValidationError(ProviderError):
    """Input validation failure (e.g. empty text, invalid audio size, illegal voice ID)."""
    def __init__(self, message: str, provider: str = "unknown", raw_error: Optional[Any] = None):
        super().__init__(message, provider=provider, code="PROVIDER_VALIDATION_ERROR", status_code=400, raw_error=raw_error)


class ProviderFallbackError(ProviderError):
    """Both primary and secondary fallback providers failed."""
    def __init__(self, message: str, provider: str = "unknown", raw_error: Optional[Any] = None):
        super().__init__(message, provider=provider, code="PROVIDER_FALLBACK_ERROR", raw_error=raw_error)


# Aliases for provider-specific errors
TTSProviderError = ProviderResponseError
STTProviderError = ProviderResponseError

