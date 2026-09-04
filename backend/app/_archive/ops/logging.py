"""Phase 10F: Production Structured JSON Logging with Automatic Redaction.

Emits standardized JSON logs enriched with correlation IDs, service context, and monotonic timings.
"""

import time
import json
import logging
from typing import Optional, Dict, Any

from app._archive.ops.config import ops_config
from app._archive.ops.secrets import redact_secrets
from app._archive.ops.correlation import CorrelationContext

logger = logging.getLogger("app._archive.ops")


class ProductionLogger:
    """Emits production-grade, secret-redacted structured JSON log lines."""

    @staticmethod
    def log(
        event: str,
        level: str = "INFO",
        duration_ms: Optional[float] = None,
        status: str = "success",
        data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Formats, redacts, and emits a structured log record."""
        req_id = request_id or CorrelationContext.get_request_id()
        corr_id = correlation_id or CorrelationContext.get_correlation_id()
        sess_id = session_id or CorrelationContext.get_session_id()

        payload = {
            "timestamp": time.time(),
            "service": "ai_interviewer",
            "environment": ops_config.ENVIRONMENT,
            "level": level.upper(),
            "event": event,
            "status": status,
            "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
            "request_id": req_id,
            "correlation_id": corr_id,
            "session_id": sess_id,
            "data": data or {}
        }

        # Apply recursive secret redaction
        sanitized = redact_secrets(payload)
        json_output = json.dumps(sanitized)

        # Log to Python standard logging
        lvl = level.upper()
        if lvl == "ERROR":
            logger.error(json_output)
        elif lvl == "WARNING":
            logger.warning(json_output)
        elif lvl == "DEBUG":
            logger.debug(json_output)
        else:
            logger.info(json_output)

        return sanitized
