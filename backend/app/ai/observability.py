"""Phase 8: Observability, Structured Logging, and Secret Protection.

Emits structured logs for AI lifecycle events while ensuring API keys,
bearer tokens, and sensitive candidate PII are never logged.
"""

import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger("ai_interviewer.ai.observability")

# Regex patterns for masking sensitive authentication headers and keys
API_KEY_PATTERNS = [
    re.compile(r'(?i)(?:key|token|auth|secret|bearer)\s*[:=]\s*["\']?([A-Za-z0-9_\-\.]{8,})["\']?'),
    re.compile(r'(?i)(AIza[0-9A-Za-z-_]{35})'),  # Gemini API key format
    re.compile(r'(?i)(sk-[A-Za-z0-9]{20,})'),      # OpenAI API key format
]


def mask_sensitive_strings(text: str) -> str:
    """Mask credentials, API keys, and authorization tokens."""
    if not text:
        return text
    sanitized = text
    for pattern in API_KEY_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


def log_ai_operation(
    operation: str,
    provider: str,
    model: str,
    latency_ms: int,
    input_tokens: int = 0,
    output_tokens: int = 0,
    success: bool = True,
    error: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log structured operational metrics for an AI call with secrets masked.
    """
    safe_error = mask_sensitive_strings(error) if error else None
    
    log_data = {
        "event": "ai_operation",
        "operation": operation,
        "provider": provider,
        "model": model,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "success": success,
    }
    if safe_error:
        log_data["error"] = safe_error
    if extra:
        for k, v in extra.items():
            if isinstance(v, str):
                log_data[k] = mask_sensitive_strings(v)
            else:
                log_data[k] = v

    if success:
        logger.info(f"AI_OP_SUCCESS [{provider}/{model}] {operation} in {latency_ms}ms (in:{input_tokens}, out:{output_tokens})")
    else:
        logger.error(f"AI_OP_FAILURE [{provider}/{model}] {operation} failed after {latency_ms}ms: {safe_error}")
