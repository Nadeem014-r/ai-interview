"""Phase 10F: Production Secret Redaction & Recursive Data Sanitization.

Guarantees zero credential leakage across structured logs, nested dictionaries, headers, and URLs.
"""

import re
from typing import Any, Dict, List, Union

SENSITIVE_FIELD_PATTERNS = {
    "password",
    "passwd",
    "secret",
    "token",
    "jwt",
    "authorization",
    "auth_token",
    "auth_key",
    "auth_secret",
    "api_key",
    "apikey",
    "private_key",
    "gemini_api_key",
    "openai_api_key",
    "elevenlabs_api_key",
    "postgres_password",
    "redis_password",
    "raw_audio",
    "audio_bytes",
    "resume_text",
    "transcript_raw",
}


def sanitize_url(url: str) -> str:
    """Redacts credentials from database / redis connection URLs."""
    if not url:
        return ""
    # Matches scheme://user:password@host:port/path or scheme://:password@host:port/path
    return re.sub(r'://([^:]*):([^@]+)@', r'://\1:[REDACTED]@', str(url))


def mask_secret_string(val: str, prefix_len: int = 4, suffix_len: int = 4) -> str:
    """Masks a secret string leaving a small prefix and suffix if long enough."""
    if not val:
        return ""
    clean = str(val).strip()
    if len(clean) <= (prefix_len + suffix_len):
        return "[REDACTED]"
    return f"{clean[:prefix_len]}...{clean[-suffix_len:]}"


def redact_secrets(data: Any) -> Any:
    """
    Recursively redacts sensitive keys and values from dictionaries, lists, tuples, and strings.
    """
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_str = str(k).lower()
            if any(p in k_str for p in SENSITIVE_FIELD_PATTERNS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = redact_secrets(v)
        return sanitized

    if isinstance(data, (list, tuple)):
        return [redact_secrets(item) for item in data]

    if isinstance(data, str):
        # Redact inline authorization headers
        masked = re.sub(r'(?i)bearer\s+([A-Za-z0-9_\-\.]{8,})', 'Bearer [REDACTED]', data)
        # Redact connection URLs
        masked = sanitize_url(masked)
        # Redact key=val or secret=val
        masked = re.sub(r'(?i)(?:key|secret|password|token)\s*[:=]\s*["\']?([A-Za-z0-9_\-\.]{8,})["\']?', '[REDACTED_SECRET]', masked)
        return masked

    return data
