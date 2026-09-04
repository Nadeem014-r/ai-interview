"""Phase 10F: Pre-Flight Deployment & Environment Validator.

Inspects operational settings and outputs human-readable diagnostic checks without leaking secrets.
"""

from typing import Tuple, List, Dict, Any, Optional
from app._archive.ops.config import ProductionOpsConfig, ops_config
from app._archive.ops.security import SecurityHardeningSupervisor


class DeploymentValidator:
    """Validates full readiness for deployment in staging and production."""

    @staticmethod
    def validate_deployment(config: Optional[ProductionOpsConfig] = None) -> Tuple[bool, List[str], List[str]]:
        """
        Validates deployment configuration.
        Returns (is_valid, errors, warnings).
        """
        cfg = config or ops_config
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Security inspection
        sec_issues = SecurityHardeningSupervisor.validate_security_configuration(cfg)
        if cfg.ENVIRONMENT == "production":
            errors.extend(sec_issues)
        else:
            warnings.extend(sec_issues)

        # 2. Database URL validation
        if not cfg.DATABASE_URL:
            errors.append("DATABASE_URL must not be empty.")
        elif cfg.ENVIRONMENT == "production" and "sqlite" in cfg.DATABASE_URL.lower():
            warnings.append("SQLite detected in production configuration; PostgreSQL is recommended.")

        # 3. Numeric limits validation
        if cfg.MAX_REQUEST_BYTES <= 0:
            errors.append("MAX_REQUEST_BYTES must be a positive integer.")

        if cfg.MAX_UPLOAD_BYTES <= 0:
            errors.append("MAX_UPLOAD_BYTES must be a positive integer.")

        if cfg.REQUEST_TIMEOUT_SECONDS <= 0:
            errors.append("REQUEST_TIMEOUT_SECONDS must be a positive number.")

        if cfg.GRACEFUL_SHUTDOWN_TIMEOUT <= 0:
            errors.append("GRACEFUL_SHUTDOWN_TIMEOUT must be a positive number.")

        is_valid = len(errors) == 0
        return is_valid, errors, warnings

    @classmethod
    def get_validation_report(cls, config: Optional[ProductionOpsConfig] = None) -> Dict[str, Any]:
        """Generates a human-readable, secret-safe deployment validation summary."""
        is_valid, errors, warnings = cls.validate_deployment(config)
        return {
            "status": "VALID" if is_valid else "INVALID",
            "errors": errors,
            "warnings": warnings,
            "environment": (config or ops_config).ENVIRONMENT
        }
