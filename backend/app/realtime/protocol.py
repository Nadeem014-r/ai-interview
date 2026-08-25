"""Phase 10B: Realtime Message Protocol & Envelope Validation.

Enforces strict JSON schema validation, protocol versioning, sequence ordering,
and payload size boundaries for all WebSocket messages.
"""

import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Union

from app.realtime.config import config
from app.realtime.events import RealtimeEvents
from app.realtime.exceptions import InvalidRealtimeMessageError


@dataclass
class RealtimeMessage:
    """Structured in-memory representation of a validated realtime message."""
    event: str
    session_id: Optional[str] = None
    sequence: int = 0
    payload: Dict[str, Any] = field(default_factory=dict)
    version: str = config.PROTOCOL_VERSION
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": str(self.version),
            "event": self.event,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "payload": self.payload
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class RealtimeProtocol:
    """Validator and serializer for realtime protocol messages."""

    @staticmethod
    def parse_client_message(raw_text: Union[str, bytes]) -> RealtimeMessage:
        """
        Parses and validates an inbound client message.
        Raises InvalidRealtimeMessageError if message is malformed, oversized,
        has an unsupported version, or uses an unrecognized client event.
        """
        if raw_text is None:
            raise InvalidRealtimeMessageError("Message payload cannot be None.")

        # 1. Byte limit check
        if isinstance(raw_text, bytes):
            if len(raw_text) > config.MAX_MESSAGE_BYTES:
                raise InvalidRealtimeMessageError(f"Message size ({len(raw_text)}B) exceeds maximum limit ({config.MAX_MESSAGE_BYTES}B).")
            try:
                raw_text = raw_text.decode("utf-8")
            except UnicodeDecodeError as e:
                raise InvalidRealtimeMessageError("Message binary is not valid UTF-8 text.", raw_error=e)
        else:
            if len(raw_text.encode("utf-8")) > config.MAX_MESSAGE_BYTES:
                raise InvalidRealtimeMessageError(f"Message size exceeds maximum limit of {config.MAX_MESSAGE_BYTES} bytes.")

        # 2. JSON Deserialization
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise InvalidRealtimeMessageError(f"Malformed JSON envelope: {str(e)}", raw_error=e)

        if not isinstance(data, dict):
            raise InvalidRealtimeMessageError("Envelope must be a JSON object.")

        # 3. Protocol Version
        version = str(data.get("version", "1"))
        if version != config.PROTOCOL_VERSION:
            raise InvalidRealtimeMessageError(f"Unsupported protocol version '{version}'. Expected '{config.PROTOCOL_VERSION}'.")

        # 4. Event Validation
        event = data.get("event")
        if not event or not isinstance(event, str):
            raise InvalidRealtimeMessageError("Message is missing valid 'event' field.")

        if event not in RealtimeEvents.client_events():
            raise InvalidRealtimeMessageError(f"Unknown or unauthorized client event '{event}'.")

        # 5. Sequence Validation
        sequence = data.get("sequence", 0)
        if not isinstance(sequence, int) or sequence < 0:
            raise InvalidRealtimeMessageError("Sequence must be a non-negative integer.")

        # 6. Payload Validation
        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            raise InvalidRealtimeMessageError("Message 'payload' must be a dictionary object.")

        session_id = data.get("session_id")
        if session_id is not None and not isinstance(session_id, str):
            raise InvalidRealtimeMessageError("Field 'session_id' must be a string if provided.")

        timestamp = data.get("timestamp") or datetime.now(timezone.utc).isoformat()

        return RealtimeMessage(
            version=version,
            event=event,
            session_id=session_id,
            sequence=sequence,
            timestamp=timestamp,
            payload=payload
        )

    @staticmethod
    def create_server_message(
        event: str,
        session_id: Optional[str] = None,
        sequence: int = 0,
        payload: Optional[Dict[str, Any]] = None
    ) -> RealtimeMessage:
        """Create a validated outbound server envelope."""
        return RealtimeMessage(
            version=config.PROTOCOL_VERSION,
            event=event,
            session_id=session_id,
            sequence=sequence,
            payload=payload or {},
            timestamp=datetime.now(timezone.utc).isoformat()
        )
