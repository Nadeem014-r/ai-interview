"""Phase 10F: Security Hardening, Trusted Hosts & CORS Policy Validator.

Validates origin policies, trusted hosts, security headers, and WebSocket upgrade origins.
"""

from typing import Dict, List, Set, Optional
from app._archive.ops.config import ProductionOpsConfig
from app._archive.ops.exceptions import OpsConfigurationError


class SecurityHardeningSupervisor:
    """Oversees transport security, origin restrictions, and security headers."""

    @staticmethod
    def validate_security_configuration(config: ProductionOpsConfig) -> List[str]:
        """Inspects security parameters and returns a list of security issues or warnings."""
        issues: List[str] = []

        if config.ENVIRONMENT == "production":
            if config.DEBUG:
                issues.append("DEBUG mode must be disabled in production.")

            if "*" in config.ALLOWED_HOSTS:
                issues.append("Wildcard '*' in ALLOWED_HOSTS is dangerous in production.")

            if "*" in config.CORS_ORIGINS:
                issues.append("Wildcard '*' in CORS_ORIGINS is dangerous in production.")

            if not config.SECRET_KEY or len(config.SECRET_KEY) < 32:
                issues.append("SECRET_KEY must be at least 32 characters with high entropy in production.")

        return issues

    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Returns standard enterprise HTTP security headers."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "Content-Security-Policy": "default-src 'self'; connect-src 'self' wss: https:;",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }

    @staticmethod
    def validate_websocket_origin(origin: Optional[str], allowed_origins: List[str]) -> bool:
        """Validates that a WebSocket connection upgrade originates from an authorized domain."""
        if not origin:
            return True  # Native clients or tests without origin header
        clean_origin = origin.strip().rstrip("/")
        normalized_allowed = [o.strip().rstrip("/") for o in allowed_origins]
        if "*" in normalized_allowed:
            return True
        return clean_origin in normalized_allowed
