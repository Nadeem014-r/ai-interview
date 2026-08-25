"""Phase 10G: Production Security Policy & Boundary Configuration.

Defines strict, bounded limits for payload sizing, nesting depths, allowable MIME types, and event catalogs.
"""

from dataclasses import dataclass, field
from typing import Set, Dict, Any


@dataclass(frozen=True)
class SecurityPolicy:
    """Configurable security boundaries and resource limit thresholds."""

    # Sizing Limits (Bytes)
    MAX_REQUEST_BYTES: int = 10 * 1024 * 1024       # 10 MB HTTP request body limit
    MAX_MESSAGE_BYTES: int = 64 * 1024              # 64 KB WebSocket text frame limit
    MAX_AUDIO_BYTES: int = 25 * 1024 * 1024         # 25 MB Audio upload / turn limit
    MAX_METADATA_BYTES: int = 16 * 1024             # 16 KB JSON metadata payload limit
    MAX_NESTING_DEPTH: int = 10                     # Maximum recursive JSON depth

    # Rate & Concurrency Limits
    MAX_REQUESTS_PER_MINUTE: int = 120
    MAX_AUTH_ATTEMPTS_PER_MINUTE: int = 10
    MAX_WS_CONNECTIONS_PER_IP: int = 20
    MAX_WS_MESSAGES_PER_SECOND: int = 30
    MAX_RECONNECT_ATTEMPTS_PER_MINUTE: int = 10
    MAX_CONCURRENT_JOBS: int = 50
    MAX_JOB_QUEUE_SIZE: int = 1000

    # Content Type Whitelist
    ALLOWED_CONTENT_TYPES: Set[str] = field(default_factory=lambda: {
        "application/json",
        "audio/wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/webm",
        "audio/ogg",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    })

    # Allowed Realtime Event Types Whitelist
    ALLOWED_EVENT_TYPES: Set[str] = field(default_factory=lambda: {
        "session.start",
        "session.join",
        "session.leave",
        "audio.chunk",
        "audio.end",
        "turn.start",
        "turn.complete",
        "turn.interrupt",
        "interruption",
        "ping",
        "pong",
        "error"
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "MAX_REQUEST_BYTES": self.MAX_REQUEST_BYTES,
            "MAX_MESSAGE_BYTES": self.MAX_MESSAGE_BYTES,
            "MAX_AUDIO_BYTES": self.MAX_AUDIO_BYTES,
            "MAX_METADATA_BYTES": self.MAX_METADATA_BYTES,
            "MAX_NESTING_DEPTH": self.MAX_NESTING_DEPTH,
            "MAX_REQUESTS_PER_MINUTE": self.MAX_REQUESTS_PER_MINUTE,
            "MAX_AUTH_ATTEMPTS_PER_MINUTE": self.MAX_AUTH_ATTEMPTS_PER_MINUTE,
            "MAX_WS_CONNECTIONS_PER_IP": self.MAX_WS_CONNECTIONS_PER_IP,
            "MAX_WS_MESSAGES_PER_SECOND": self.MAX_WS_MESSAGES_PER_SECOND,
            "MAX_RECONNECT_ATTEMPTS_PER_MINUTE": self.MAX_RECONNECT_ATTEMPTS_PER_MINUTE
        }


# Default system security policy
default_security_policy = SecurityPolicy()
