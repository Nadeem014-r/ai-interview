"""Phase 8: Normalized AI Exceptions.

Provides a unified exception hierarchy across all AI providers (Gemini, OpenAI, Mock)
so caller code does not need provider-specific error handling.
"""

from typing import Optional, Dict, Any


class AIError(Exception):
    """Base exception for all AI provider and LLM operations."""

    def __init__(self, message: str, provider: Optional[str] = None, raw_error: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.raw_error = raw_error

    def __str__(self) -> str:
        prefix = f"[{self.provider}] " if self.provider else ""
        return f"{prefix}{self.message}"


class AIProviderError(AIError):
    """General AI provider failure or internal provider service error."""
    pass


class AIAuthenticationError(AIError):
    """Authentication or authorization failure (e.g. invalid or missing API key)."""
    pass


class AIRateLimitError(AIError):
    """Rate limit exceeded or quota exhausted (HTTP 429)."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        raw_error: Optional[Any] = None,
        retry_after: Optional[float] = None
    ):
        super().__init__(message, provider=provider, raw_error=raw_error)
        self.retry_after = retry_after


class AITimeoutError(AIError):
    """Request timeout when communicating with an AI service."""
    pass


class AIInvalidRequestError(AIError):
    """Client-side invalid request (e.g. malformed parameters, invalid prompt, HTTP 400)."""
    pass


class AIModelNotFoundError(AIError):
    """Requested AI model is not supported or not found."""
    pass


class AIStructuredOutputError(AIError):
    """Failure to parse, extract, or validate structured JSON response from LLM."""

    def __init__(
        self,
        message: str,
        raw_response: Optional[str] = None,
        schema_errors: Optional[Any] = None,
        provider: Optional[str] = None
    ):
        super().__init__(message, provider=provider)
        self.raw_response = raw_response
        self.schema_errors = schema_errors


class AIContextLimitError(AIError):
    """Input prompt exceeds context window or token budget."""
    pass


class AIEmbeddingError(AIError):
    """Failure during single or batch embedding generation or validation."""
    pass


class AIFallbackExhaustedError(AIError):
    """All primary and fallback AI providers failed to process the request."""
    pass


class AISecurityError(AIError):
    """Security violation detected during prompt construction, tool execution, or output validation."""
    pass
