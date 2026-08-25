"""Phase 10B: Realtime Infrastructure Configuration.

Contains bounded operational limits, timeouts, buffer sizes, and connection thresholds.
All settings have safe production defaults and can be configured via environment variables.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RealtimeConfig:
    """Production realtime configuration settings."""
    # Protocol & Message Limits
    PROTOCOL_VERSION: str = "1"
    MAX_MESSAGE_BYTES: int = int(os.getenv("REALTIME_MAX_MESSAGE_BYTES", 64 * 1024))  # 64 KB per JSON envelope
    MAX_AUDIO_CHUNK_BYTES: int = int(os.getenv("REALTIME_MAX_AUDIO_CHUNK_BYTES", 128 * 1024))  # 128 KB per chunk
    MAX_BUFFER_BYTES: int = int(os.getenv("REALTIME_MAX_BUFFER_BYTES", 10 * 1024 * 1024))  # 10 MB max session buffer
    MAX_QUEUE_SIZE: int = int(os.getenv("REALTIME_MAX_QUEUE_SIZE", 100))  # Max pending chunks in pipeline

    # Connection & Concurrency Limits
    MAX_GLOBAL_CONNECTIONS: int = int(os.getenv("REALTIME_MAX_GLOBAL_CONNECTIONS", 10000))
    MAX_CONNECTIONS_PER_USER: int = int(os.getenv("REALTIME_MAX_CONNECTIONS_PER_USER", 3))
    MAX_CONNECTIONS_PER_INTERVIEW: int = int(os.getenv("REALTIME_MAX_CONNECTIONS_PER_INTERVIEW", 2))

    # Timeouts & Lifecycles (seconds)
    HEARTBEAT_INTERVAL: float = float(os.getenv("REALTIME_HEARTBEAT_INTERVAL", 15.0))
    HEARTBEAT_TIMEOUT: float = float(os.getenv("REALTIME_HEARTBEAT_TIMEOUT", 45.0))
    IDLE_CONNECTION_TIMEOUT: float = float(os.getenv("REALTIME_IDLE_CONNECTION_TIMEOUT", 120.0))
    MAX_CONNECTION_DURATION: float = float(os.getenv("REALTIME_MAX_CONNECTION_DURATION", 7200.0))  # 2 hours max
    RECONNECT_GRACE_SECONDS: float = float(os.getenv("REALTIME_RECONNECT_GRACE_SECONDS", 60.0))  # 60s reconnect window
    SESSION_TTL_SECONDS: int = int(os.getenv("REALTIME_SESSION_TTL_SECONDS", 3600))  # 1 hour session TTL

    # Rate Limits
    RATE_LIMIT_MESSAGES_PER_SEC: int = int(os.getenv("REALTIME_RATE_LIMIT_MESSAGES_PER_SEC", 50))
    RATE_LIMIT_AUDIO_CHUNKS_PER_SEC: int = int(os.getenv("REALTIME_RATE_LIMIT_AUDIO_CHUNKS_PER_SEC", 25))
    RATE_LIMIT_RECONNECTS_PER_MIN: int = int(os.getenv("REALTIME_RATE_LIMIT_RECONNECTS_PER_MIN", 10))

    # Redis & Storage
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    USE_REDIS: bool = os.getenv("REALTIME_USE_REDIS", "false").lower() in ("true", "1", "yes")
    STORAGE_PATH: str = os.getenv("REALTIME_STORAGE_PATH", "./realtime_storage")
    STORAGE_MAX_OBJECT_BYTES: int = int(os.getenv("REALTIME_STORAGE_MAX_OBJECT_BYTES", 50 * 1024 * 1024))  # 50 MB


# Singleton instance
config = RealtimeConfig()
