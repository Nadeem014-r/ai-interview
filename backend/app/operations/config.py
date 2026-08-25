"""Phase 10H: Production Configuration Validation Layer.

Validates environment variables, secret presence, CORS rules, and resource limits
without exposing secrets in error messages or logs.
"""

import os
from enum import Enum
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field

from app.ops.secrets import redact_secrets


class ValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    WARNING = "WARNING"


@dataclass
class ConfigValidationResult:
    status: ValidationStatus
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def is_deployable(self) -> bool:
        return self.status in (ValidationStatus.VALID, ValidationStatus.WARNING)


class ProductionConfigValidator:
    """Validates runtime configuration for enterprise production deployment."""

    @staticmethod
    def validate_environment(env_vars: Optional[Dict[str, str]] = None) -> ConfigValidationResult:
        """
        Validates the provided environment dictionary or active os.environ.
        Returns a ConfigValidationResult with human-readable, secret-safe errors and warnings.
        """
        env = env_vars if env_vars is not None else dict(os.environ)
        errors: List[str] = []
        warnings: List[str] = []

        environment = env.get("ENVIRONMENT", "development").lower()
        debug_val = env.get("DEBUG", "false").lower() in ("true", "1", "yes")

        # 1. Environment & Debug
        if environment == "production" and debug_val:
            errors.append("DEBUG mode must be FALSE in production environments.")

        # 2. Secret Key Validation
        secret_key = env.get("SECRET_KEY", "")
        if not secret_key:
            if environment == "production":
                errors.append("SECRET_KEY is required and cannot be empty in production.")
            else:
                warnings.append("SECRET_KEY is empty; using insecure dev fallback.")
        elif len(secret_key) < 32 and environment == "production":
            errors.append("SECRET_KEY must be at least 32 characters in production.")

        # 3. Database URL Validation
        db_url = env.get("DATABASE_URL", "")
        if not db_url:
            if environment == "production":
                errors.append("DATABASE_URL is required in production.")
            else:
                warnings.append("DATABASE_URL is empty; defaulting to SQLite.")
        elif "sqlite" in db_url.lower() and environment == "production":
            warnings.append("SQLite detected in production; PostgreSQL is strongly recommended.")

        # 4. CORS Origins Validation
        cors = env.get("CORS_ORIGINS", "")
        if environment == "production":
            if not cors or cors.strip() == "*":
                errors.append("CORS_ORIGINS cannot be empty or wildcard '*' in production.")

        # 5. Resource Limits & Timeouts
        try:
            req_timeout = float(env.get("REQUEST_TIMEOUT_SECONDS", "30.0"))
            if req_timeout <= 0:
                errors.append("REQUEST_TIMEOUT_SECONDS must be positive.")
        except ValueError:
            errors.append("REQUEST_TIMEOUT_SECONDS must be a valid float.")

        # 6. Overall Status Determination
        if errors:
            status = ValidationStatus.INVALID
        elif warnings:
            status = ValidationStatus.WARNING
        else:
            status = ValidationStatus.VALID

        return ConfigValidationResult(
            status=status,
            errors=errors,
            warnings=warnings,
            details={"environment": environment, "debug": debug_val}
        )
