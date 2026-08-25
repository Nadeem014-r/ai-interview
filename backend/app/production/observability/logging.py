"""Phase 10C: Secret-Safe Structured Production Logging.

Formats log entries as structured JSON with correlation IDs and automatic secret masking.
"""

import time
import json
import logging
from typing import Optional, Dict, Any

from app.production.security.secrets import mask_log_record

logger = logging.getLogger("app.production")


class StructuredProductionLogger:
    """Structured JSON logger with automatic secret redaction."""

    @staticmethod
    def log_event(
        event: str,
        correlation_id: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        job_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        level: str = "info",
        **kwargs
    ) -> Dict[str, Any]:
        """Formats and emits a structured JSON log entry."""
        raw_payload = {
            "timestamp": time.time(),
            "event": event,
            "correlation_id": correlation_id,
            "request_id": request_id,
            "session_id": session_id,
            "job_id": job_id,
            "duration_ms": duration_ms,
            **kwargs
        }

        # Mask secrets automatically
        sanitized = mask_log_record(raw_payload)

        # Output to logging subsystem
        log_str = json.dumps(sanitized)
        if level == "error":
            logger.error(log_str)
        elif level == "warning":
            logger.warning(log_str)
        else:
            logger.info(log_str)

        return sanitized
