"""Phase 10H: Operational Structured Logging Layer with Secret Redaction.

Emits structured JSON logs with correlation context, component tagging, latency tracking, and zero credential leakage.
"""

import time
import json
import logging
from typing import Dict, Any, Optional

from app._archive.ops.secrets import redact_secrets
from app._archive.operations.correlation import OperationalCorrelation

logger = logging.getLogger("app._archive.operations")


class OperationalLogger:
    """Emits production-safe, structured JSON logs with automatic correlation and secret redaction."""

    @staticmethod
    def log(
        event: str,
        level: str = "INFO",
        component: str = "core",
        operation: str = "execute",
        status: str = "success",
        latency_ms: Optional[float] = None,
        error_code: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        interview_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Formats and logs a structured event record."""
        ctx = OperationalCorrelation.get_context_dict()

        record = {
            "timestamp": time.time(),
            "level": level.upper(),
            "event": event,
            "component": component,
            "operation": operation,
            "status": status,
            "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
            "error_code": error_code,
            "request_id": request_id or ctx.get("request_id"),
            "session_id": session_id or ctx.get("session_id"),
            "interview_id": interview_id or ctx.get("interview_id"),
            "data": data or {}
        }

        # Apply recursive secret redaction
        sanitized = redact_secrets(record)
        json_line = json.dumps(sanitized)

        lvl = level.upper()
        if lvl == "ERROR":
            logger.error(json_line)
        elif lvl == "WARNING":
            logger.warning(json_line)
        elif lvl == "DEBUG":
            logger.debug(json_line)
        else:
            logger.info(json_line)

        return sanitized
