"""Phase 10G: Payload Defense & Input Sanitization Layer.

Guards endpoints and WebSockets against deeply nested objects, oversized frames, malformed JSON, and malformed sequence IDs.
"""

import json
from typing import Any, Dict, Optional, Set
from app._archive.hardening.exceptions import ValidationError
from app._archive.hardening.security_policy import SecurityPolicy, default_security_policy


class PayloadDefense:
    """Validates structural and content properties of incoming payloads."""

    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or default_security_policy

    def validate_raw_bytes(self, data: Optional[bytes], max_bytes: Optional[int] = None) -> bytes:
        """Enforces payload byte size limits."""
        if data is None:
            raise ValidationError("Payload data cannot be None.")

        limit = max_bytes or self.policy.MAX_REQUEST_BYTES
        if len(data) > limit:
            raise ValidationError(f"Payload size ({len(data)}B) exceeds maximum limit ({limit}B).")

        return data

    def validate_json_string(self, raw_str: Optional[str], max_bytes: Optional[int] = None) -> Dict[str, Any]:
        """Safely parses JSON string enforcing size and syntax correctness."""
        if not raw_str or not raw_str.strip():
            raise ValidationError("JSON string payload cannot be empty.")

        limit = max_bytes or self.policy.MAX_MESSAGE_BYTES
        if len(raw_str.encode("utf-8")) > limit:
            raise ValidationError(f"JSON text length exceeds limit ({limit}B).")

        try:
            parsed = json.loads(raw_str)
        except Exception as e:
            raise ValidationError(f"Malformed JSON payload: {str(e)}")

        if not isinstance(parsed, dict):
            raise ValidationError("JSON payload root must be an object/dictionary.")

        self.validate_nesting_depth(parsed)
        return parsed

    def validate_nesting_depth(self, obj: Any, current_depth: int = 1) -> None:
        """Recursively checks object nesting depth against policy threshold."""
        if current_depth > self.policy.MAX_NESTING_DEPTH:
            raise ValidationError(f"Payload exceeds maximum nesting depth of {self.policy.MAX_NESTING_DEPTH}.")

        if isinstance(obj, dict):
            for v in obj.values():
                if isinstance(v, (dict, list, tuple)):
                    self.validate_nesting_depth(v, current_depth + 1)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                if isinstance(item, (dict, list, tuple)):
                    self.validate_nesting_depth(item, current_depth + 1)

    def validate_event_envelope(self, envelope: Dict[str, Any]) -> None:
        """Validates standard realtime event message envelope."""
        event_type = envelope.get("event") or envelope.get("type")
        if not event_type or not isinstance(event_type, str):
            raise ValidationError("Event envelope is missing required 'event' or 'type' field.")

        clean_type = event_type.strip().lower()
        if clean_type not in self.policy.ALLOWED_EVENT_TYPES:
            raise ValidationError(f"Unsupported or unauthorized event type: '{event_type}'.")

        # Validate sequence number if present
        seq = envelope.get("seq")
        if seq is not None:
            if not isinstance(seq, int) or seq < 0:
                raise ValidationError("Event sequence number 'seq' must be a non-negative integer.")

        # Validate timestamp if present
        ts = envelope.get("timestamp")
        if ts is not None:
            if not isinstance(ts, (int, float)) or ts <= 0:
                raise ValidationError("Event timestamp must be a positive numeric value.")
