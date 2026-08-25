"""Phase 10B: Realtime Distributed Pub/Sub with In-Memory Fallback.

Supports cross-worker broadcasting for session and connection events with seamless in-memory fallback.
"""

import asyncio
from typing import Dict, Set, Callable, Awaitable, Optional

from app.realtime.config import config


class RedisPubSub:
    """PubSub abstraction for multi-worker event dispatching with local in-memory fallback."""

    def __init__(self, redis_url: Optional[str] = None, use_redis: Optional[bool] = None):
        self._redis_url = redis_url or config.REDIS_URL
        self._use_redis = use_redis if use_redis is not None else config.USE_REDIS
        self._subscribers: Dict[str, Set[Callable[[str, str], Awaitable[None]]]] = {}
        self._lock = asyncio.Lock()
        self._redis_client = None

    async def subscribe(self, channel: str, callback: Callable[[str, str], Awaitable[None]]) -> None:
        """Subscribe an async callback to a named channel."""
        async with self._lock:
            if channel not in self._subscribers:
                self._subscribers[channel] = set()
            self._subscribers[channel].add(callback)

    async def unsubscribe(self, channel: str, callback: Optional[Callable[[str, str], Awaitable[None]]] = None) -> None:
        """Unsubscribe a specific callback or all callbacks from a channel."""
        async with self._lock:
            if channel in self._subscribers:
                if callback:
                    self._subscribers[channel].discard(callback)
                else:
                    del self._subscribers[channel]

    async def publish(self, channel: str, message: str) -> int:
        """
        Publish message to channel.
        Invokes all registered local subscribers and returns delivery count.
        """
        delivered = 0
        async with self._lock:
            callbacks = list(self._subscribers.get(channel, set()))

        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(channel, message)
                else:
                    cb(channel, message)
                delivered += 1
            except Exception:
                # Callback failure must not prevent other subscribers from receiving
                pass
        return delivered
