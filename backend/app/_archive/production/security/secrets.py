"""Phase 10C: Secret Masking & Sensitive Data Sanitization.

Provides robust secret masking (e.g. AIza...6789), header redaction,
and structured log sanitization.
"""

import re
from typing import Dict, Any, Optional

SENSITIVE_HEADER_KEYS = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "x-token",
    "cookie",
    "set-cookie"
}

SENSITIVE_LOG_KEYS = {
    "password",
    "token",
    "jwt",
    "secret",
    "secret_key",
    "authorization",
    "api_key",
    "gemini_api_key",
    "openai_api_key",
    "elevenlabs_api_key",
    "raw_audio",
    "audio_bytes",
    "resume_text",
    "candidate_audio"
}


def mask_secret(value: Optional[str], prefix_len: int = 4, suffix_len: int = 4) -> str:
    """
    Mask sensitive secret strings, showing only prefix and suffix if long enough.
    Example: 'AIzaSy123456789' -> 'AIza...6789'
    """
    if not value:
        return ""
    clean = str(value).strip()
    if len(clean) <= (prefix_len + suffix_len):
        return "[REDACTED_SECRET]"
    return f"{clean[:prefix_len]}...{clean[-suffix_len:]}"


def mask_sensitive_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Mask sensitive HTTP headers (Authorization, X-Api-Key, Cookie, etc.)."""
    masked = {}
    for k, v in headers.items():
        if k.lower() in SENSITIVE_HEADER_KEYS:
            masked[k] = "[REDACTED_HEADER]"
        else:
            masked[k] = str(v)
    return masked


def mask_log_record(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize dictionary keys and values for secure structured logging."""
    sanitized = {}
    for k, v in data.items():
        k_lower = str(k).lower()
        if any(sens in k_lower for sens in SENSITIVE_LOG_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = mask_log_record(v)
        elif isinstance(v, str):
            # Check for inline secret patterns
            masked_str = re.sub(r'(?i)(?:key|token|auth|secret)\s*[:=]\s*["\']?([A-Za-z0-9_\-\.]{8,})["\']?', '[REDACTED_SECRET]', v)
            masked_str = re.sub(r'(?i)bearer\s+([A-Za-z0-9_\-\.]{8,})', 'Bearer [REDACTED_SECRET]', masked_str)
            sanitized[k] = masked_str
        else:
            sanitized[k] = v
    return sanitized
