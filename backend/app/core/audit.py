"""Phase 10: Security & Administrative Action Audit Logger.

Logs important administrative, security, and lifecycle actions with zero leakage
of secrets, passwords, API keys, or raw JWT authorization tokens.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("ai_interviewer.audit")


class AuditLogger:
    """Provides structured audit trail logging for university placement & security operations."""

    @staticmethod
    def log_event(
        event_type: str,
        user_id: Optional[int] = None,
        user_role: Optional[str] = None,
        resource: Optional[str] = None,
        status: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Records an auditable event with sanitized metadata.
        Excludes sensitive fields (passwords, tokens, keys).
        """
        sanitized_details = {}
        if details:
            for k, v in details.items():
                if any(sec in k.lower() for sec in ["password", "token", "secret", "key", "auth", "credential"]):
                    sanitized_details[k] = "[REDACTED]"
                else:
                    sanitized_details[k] = str(v)[:200]

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "user_role": user_role or "anonymous",
            "resource": resource or "system",
            "status": status,
            "details": sanitized_details
        }

        log_msg = f"[AUDIT] {record['timestamp']} | EVENT: {event_type} | USER: {user_id} ({user_role}) | STATUS: {status} | RESOURCE: {resource}"
        if status == "SUCCESS":
            logger.info(log_msg)
        else:
            logger.warning(log_msg)

        return record
