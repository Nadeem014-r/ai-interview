"""Phase 10C: Security Headers & Transport Hardening.

Provides production-ready HTTP security headers configuration.
"""

from typing import Dict


def get_production_security_headers() -> Dict[str, str]:
    """Returns standard recommended HTTP response security headers."""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none';",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=*, geolocation=()"
    }
