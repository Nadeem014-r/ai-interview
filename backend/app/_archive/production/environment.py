"""Phase 10C: Production Environment Pre-Flight Validator.

Validates environment variables, detects missing production secrets,
prevents insecure defaults, and enforces strict production readiness boundaries.
"""

from typing import List, Dict, Any
from app._archive.production.config import ProductionConfig
from app._archive.production.exceptions import SecurityConfigurationError, ConfigurationError

INSECURE_DEV_SECRETS = {
    "default_dev_secret_key_change_in_production_12345",
    "secret",
    "secretkey",
    "changeme",
    "admin",
    "password",
    "default_insecure_development_secret_key_for_testing_only_12345"
}


class ProductionEnvironmentValidator:
    """Pre-flight environment and configuration validator."""

    @staticmethod
    def validate_configuration(config: ProductionConfig) -> List[str]:
        """
        Inspects configuration and returns a list of warnings or detected issues.
        Does NOT raise exceptions.
        """
        issues: List[str] = []

        # 1. Environment & Debug
        if config.ENVIRONMENT == "production":
            if config.DEBUG:
                issues.append("DEBUG mode must be disabled (False) in production.")

            # 2. Secret Key
            if not config.SECRET_KEY or config.SECRET_KEY in INSECURE_DEV_SECRETS or len(config.SECRET_KEY) < 32:
                issues.append("SECRET_KEY must be a secure, high-entropy secret (at least 32 characters) in production.")

            # 3. Allowed Hosts
            if "*" in config.ALLOWED_HOSTS:
                issues.append("Wildcard '*' in ALLOWED_HOSTS is not permitted in production.")

            # 4. Database URL
            if "sqlite" in config.DATABASE_URL.lower():
                issues.append("SQLite is not recommended for production. Use PostgreSQL or high-availability database.")

        # 5. Numeric limits validation (applies across all environments)
        if config.MAX_REQUEST_BYTES <= 0:
            issues.append("MAX_REQUEST_BYTES must be a positive integer.")

        if config.MAX_UPLOAD_SIZE_BYTES <= 0:
            issues.append("MAX_UPLOAD_SIZE_BYTES must be a positive integer.")

        if config.REQUEST_TIMEOUT_SECONDS <= 0:
            issues.append("REQUEST_TIMEOUT_SECONDS must be a positive number.")

        if config.GRACEFUL_SHUTDOWN_TIMEOUT <= 0:
            issues.append("GRACEFUL_SHUTDOWN_TIMEOUT must be a positive number.")

        if config.WORKER_CONCURRENCY <= 0:
            issues.append("WORKER_CONCURRENCY must be a positive integer.")

        # 6. S3 Storage validation
        if config.STORAGE_BACKEND == "s3" and not config.STORAGE_S3_BUCKET:
            issues.append("STORAGE_S3_BUCKET is required when STORAGE_BACKEND is set to 's3'.")

        return issues

    @staticmethod
    def enforce_production_readiness(config: ProductionConfig) -> None:
        """
        Enforces strict readiness criteria. Raises SecurityConfigurationError or ConfigurationError
        if critical issues are detected.
        """
        issues = ProductionEnvironmentValidator.validate_configuration(config)
        if not issues:
            return

        if config.ENVIRONMENT == "production":
            # Any issue in production is a fatal startup blocker
            raise SecurityConfigurationError(
                f"Production readiness validation failed: {'; '.join(issues)}"
            )
        else:
            # In development/test, raise ConfigurationError only for fatal limit misconfigurations
            fatal = [i for i in issues if "must be a positive" in i or "STORAGE_S3_BUCKET is required" in i]
            if fatal:
                raise ConfigurationError(f"Configuration error: {'; '.join(fatal)}")
