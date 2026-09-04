"""Phase 10C: Normalized Production Exception Hierarchy.

Provides clear, categorized, secret-safe exceptions for production configuration,
security validation, storage operations, background jobs, and deployment checks.
"""

from typing import Optional, Any


class ProductionError(Exception):
    """Base exception for all production infrastructure operations."""

    def __init__(self, message: str, code: str = "PRODUCTION_ERROR", raw_error: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.raw_error = raw_error

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message
        }


class ConfigurationError(ProductionError):
    """Configuration parsing, loading, or missing parameter failure."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, code="CONFIGURATION_ERROR", raw_error=raw_error)


class SecurityConfigurationError(ProductionError):
    """Insecure production configuration detected."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, code="SECURITY_CONFIGURATION_ERROR", raw_error=raw_error)


class ProductionStorageError(ProductionError):
    """Object storage access or I/O failure."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, code="STORAGE_ERROR", raw_error=raw_error)


class StorageValidationError(ProductionStorageError):
    """Storage key, path traversal, content-type, or size validation failure."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, raw_error=raw_error)
        self.code = "STORAGE_VALIDATION_ERROR"


class JobError(ProductionError):
    """Background job processing error."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, code="JOB_ERROR", raw_error=raw_error)


class JobTimeoutError(JobError):
    """Background job execution exceeded maximum allowed time."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, raw_error=raw_error)
        self.code = "JOB_TIMEOUT_ERROR"


class HealthCheckError(ProductionError):
    """Health or readiness diagnostic failure."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, code="HEALTH_CHECK_ERROR", raw_error=raw_error)


class DeploymentError(ProductionError):
    """Deployment environment or pre-flight verification failure."""
    def __init__(self, message: str, raw_error: Optional[Any] = None):
        super().__init__(message, code="DEPLOYMENT_ERROR", raw_error=raw_error)
