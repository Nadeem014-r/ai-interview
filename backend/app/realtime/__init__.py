"""Phase 10B: Realtime Infrastructure Module Exports.
"""

from app.realtime.config import RealtimeConfig, config
from app.realtime.events import RealtimeEvents
from app.realtime.protocol import RealtimeProtocol, RealtimeMessage
from app.realtime.auth import RealtimeAuthenticator
from app.realtime.connection_manager import ConnectionManager
from app.realtime.session_manager import RealtimeSession, RealtimeSessionState, RealtimeSessionManager
from app.realtime.reconnect import ReconnectManager
from app.realtime.audio_pipeline import AudioChunkPipeline, AudioChunk
from app.realtime.redis_store import RedisStore, InMemoryStore
from app.realtime.redis_pubsub import RedisPubSub
from app.realtime.rate_limit import RealtimeRateLimiter, rate_limiter
from app.realtime.background import BackgroundJobManager
from app.realtime.storage import StorageService, LocalStorage
from app.realtime.observability import RealtimeMetrics, RealtimeLogger, RealtimeHealthChecker, metrics
from app.realtime.adapters import VoiceAdapter, InterviewEngineAdapter
from app.realtime.websocket import RealtimeWebSocketDispatcher
from app.realtime.exceptions import (
    RealtimeError,
    WebSocketAuthenticationError,
    WebSocketAuthorizationError,
    InvalidRealtimeMessageError,
    AudioLimitExceededError,
    SessionNotFoundError,
    SessionExpiredError,
    InvalidSessionStateError,
    ReplayDetectedError,
    RateLimitExceededError,
    RealtimeProviderTimeoutError,
    RealtimeDependencyUnavailableError,
    StorageError,
    RedisUnavailableError,
    BackpressureError,
)

__all__ = [
    "RealtimeConfig",
    "config",
    "RealtimeEvents",
    "RealtimeProtocol",
    "RealtimeMessage",
    "RealtimeAuthenticator",
    "ConnectionManager",
    "RealtimeSession",
    "RealtimeSessionState",
    "RealtimeSessionManager",
    "ReconnectManager",
    "AudioChunkPipeline",
    "AudioChunk",
    "RedisStore",
    "InMemoryStore",
    "RedisPubSub",
    "RealtimeRateLimiter",
    "rate_limiter",
    "BackgroundJobManager",
    "StorageService",
    "LocalStorage",
    "RealtimeMetrics",
    "RealtimeLogger",
    "RealtimeHealthChecker",
    "metrics",
    "VoiceAdapter",
    "InterviewEngineAdapter",
    "RealtimeWebSocketDispatcher",
    "RealtimeError",
    "WebSocketAuthenticationError",
    "WebSocketAuthorizationError",
    "InvalidRealtimeMessageError",
    "AudioLimitExceededError",
    "SessionNotFoundError",
    "SessionExpiredError",
    "InvalidSessionStateError",
    "ReplayDetectedError",
    "RateLimitExceededError",
    "RealtimeProviderTimeoutError",
    "RealtimeDependencyUnavailableError",
    "StorageError",
    "RedisUnavailableError",
    "BackpressureError",
]
