"""Phase 10F: Production Operations Exception Hierarchy & Client-Safe Error Classification.

Provides standardized, categorized error structures preventing internal details or secrets leakage.
"""

from typing import Optional, Any, Dict
from enum import Enum


class ErrorCategory(str, Enum):
    """Normalized production error classification categories."""
    CONFIGURATION_ERROR = "configuration_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    DEPENDENCY_ERROR = "dependency_error"
    DATABASE_ERROR = "database_error"
    REDIS_ERROR = "redis_error"
    STORAGE_ERROR = "storage_error"
    REALTIME_ERROR = "realtime_error"
    AI_PROVIDER_ERROR = "ai_provider_error"
    TIMEOUT_ERROR = "timeout_error"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"


class OpsError(Exception):
    """Base exception for all Phase 10F production operations."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.INTERNAL_ERROR,
        status_code: int = 500,
        raw_error: Optional[Any] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.status_code = status_code
        self.raw_error = raw_error

    def to_client_dict(self) -> Dict[str, Any]:
        """Generates a safe, sanitized client-facing response."""
        return {
            "error_category": self.category.value,
            "message": self.message,
            "status_code": self.status_code
        }


class OpsConfigurationError(OpsError):
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, ErrorCategory.CONFIGURATION_ERROR, status_code=500, raw_error=raw_error)


class OpsAuthenticationError(OpsError):
    def __init__(self, message: str = "Authentication failed.", raw_error: Optional[Any] = None):
        super().__init__(message, ErrorCategory.AUTHENTICATION_ERROR, status_code=401, raw_error=raw_error)


class OpsAuthorizationError(OpsError):
    def __init__(self, message: str = "Access forbidden.", raw_error: Optional[Any] = None):
        super().__init__(message, ErrorCategory.AUTHORIZATION_ERROR, status_code=403, raw_error=raw_error)


class OpsDependencyError(OpsError):
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, ErrorCategory.DEPENDENCY_ERROR, status_code=503, raw_error=raw_error)


class OpsDatabaseError(OpsError):
    def __init__(self, message: str = "Database operation failed.", raw_error: Optional[Any] = None):
        super().__init__(message, ErrorCategory.DATABASE_ERROR, status_code=503, raw_error=raw_error)


class OpsRedisError(OpsError):
    def __init__(self, message: str = "Redis cache operation failed.", raw_error: Optional[Any] = None):
        super().__init__(message, ErrorCategory.REDIS_ERROR, status_code=503, raw_error=raw_error)


class OpsStorageError(OpsError):
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, ErrorCategory.STORAGE_ERROR, status_code=500, raw_error=raw_error)


class OpsRealtimeError(OpsError):
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, ErrorCategory.REALTIME_ERROR, status_code=500, raw_error=raw_error)


class OpsAIProviderError(OpsError):
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, ErrorCategory.AI_PROVIDER_ERROR, status_code=502, raw_error=raw_error)


class OpsTimeoutError(OpsError):
    def __init__(self, message: str = "Operation timed out.", raw_error: Optional[Any] = None):
        super().__init__(message, ErrorCategory.TIMEOUT_ERROR, status_code=504, raw_error=raw_error)


class OpsValidationError(OpsError):
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, ErrorCategory.VALIDATION_ERROR, status_code=422, raw_error=raw_error)


class OpsInternalError(OpsError):
    def __init__(self, message: str = "An internal server error occurred.", raw_error: Optional[Any] = None):
        super().__init__(message, ErrorCategory.INTERNAL_ERROR, status_code=500, raw_error=raw_error)


def classify_exception(exc: Exception) -> Dict[str, Any]:
    """
    Classifies arbitrary exceptions into safe client responses.
    Ensures internal traces, database details, and secrets are NEVER returned to API callers.
    """
    if isinstance(exc, OpsError):
        return exc.to_client_dict()

    exc_name = type(exc).__name__.lower()
    exc_msg = str(exc).lower()
    combined = f"{exc_name} {exc_msg}"

    if "db" in combined or "sql" in combined or "postgres" in combined or "psycopg" in combined or "asyncpg" in combined:
        return {"error_category": ErrorCategory.DATABASE_ERROR.value, "message": "Database service temporarily unavailable.", "status_code": 503}
    if "redis" in combined:
        return {"error_category": ErrorCategory.REDIS_ERROR.value, "message": "Cache service temporarily unavailable.", "status_code": 503}
    if "timeout" in combined:
        return {"error_category": ErrorCategory.TIMEOUT_ERROR.value, "message": "Request timed out.", "status_code": 504}
    if "jwt" in combined or "bearer" in combined or "unauthorized" in combined or "auth" in exc_name:
        return {"error_category": ErrorCategory.AUTHENTICATION_ERROR.value, "message": "Authentication error.", "status_code": 401}
    if "valida" in combined or "valueerror" in combined:
        return {"error_category": ErrorCategory.VALIDATION_ERROR.value, "message": "Invalid input provided.", "status_code": 422}

    return {"error_category": ErrorCategory.INTERNAL_ERROR.value, "message": "An unexpected error occurred.", "status_code": 500}
