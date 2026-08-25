"""Phase 10G: Production Hardening Exception Hierarchy.

Normalized production error model with stable error codes, safe public messages,
internal diagnostic metadata, and retryability classifications.
"""

from typing import Optional, Any, Dict


class ProductionError(Exception):
    """Base exception for all Phase 10G production hardening errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        retryable: bool = False,
        internal_details: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.retryable = retryable
        self.internal_details = internal_details

    def to_public_dict(self) -> Dict[str, Any]:
        """Returns safe public error response without leaking internal details."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "retryable": self.retryable
        }


class ValidationError(ProductionError):
    def __init__(self, message: str, internal_details: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            retryable=False,
            internal_details=internal_details
        )


class AuthenticationError(ProductionError):
    def __init__(self, message: str = "Authentication failed.", internal_details: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
            retryable=False,
            internal_details=internal_details
        )


class AuthorizationError(ProductionError):
    def __init__(self, message: str = "Access forbidden.", internal_details: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
            retryable=False,
            internal_details=internal_details
        )


class RateLimitError(ProductionError):
    def __init__(self, message: str = "Rate limit exceeded.", retry_after_sec: float = 1.0, internal_details: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            retryable=True,
            internal_details=internal_details
        )
        self.retry_after_sec = retry_after_sec

    def to_public_dict(self) -> Dict[str, Any]:
        res = super().to_public_dict()
        res["retry_after_seconds"] = self.retry_after_sec
        return res


class TimeoutError(ProductionError):
    def __init__(self, message: str = "Operation timed out.", internal_details: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="TIMEOUT_ERROR",
            status_code=504,
            retryable=True,
            internal_details=internal_details
        )


class DependencyError(ProductionError):
    def __init__(self, message: str = "Dependency service unavailable.", internal_details: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="DEPENDENCY_ERROR",
            status_code=503,
            retryable=True,
            internal_details=internal_details
        )


class CircuitOpenError(ProductionError):
    def __init__(self, service_name: str, cooldown_remaining: float = 0.0):
        super().__init__(
            message=f"Service '{service_name}' circuit breaker is OPEN.",
            error_code="CIRCUIT_OPEN",
            status_code=503,
            retryable=True,
            internal_details=f"Cooldown remaining: {cooldown_remaining:.2f}s"
        )
        self.cooldown_remaining = cooldown_remaining


class StorageError(ProductionError):
    def __init__(self, message: str = "Storage operation failed.", internal_details: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="STORAGE_ERROR",
            status_code=500,
            retryable=False,
            internal_details=internal_details
        )


class RedisError(ProductionError):
    def __init__(self, message: str = "Cache service operation failed.", internal_details: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="REDIS_ERROR",
            status_code=503,
            retryable=True,
            internal_details=internal_details
        )


class JobError(ProductionError):
    def __init__(self, message: str = "Background job execution failed.", internal_details: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="JOB_ERROR",
            status_code=500,
            retryable=False,
            internal_details=internal_details
        )


class ResourceLimitError(ProductionError):
    def __init__(self, message: str = "Resource capacity limit reached.", internal_details: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="RESOURCE_LIMIT_EXCEEDED",
            status_code=503,
            retryable=True,
            internal_details=internal_details
        )
