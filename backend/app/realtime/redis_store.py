"""Phase 10B: Async Redis Store with In-Memory Offline Fallback.

Provides a unified key-value and TTL storage abstraction supporting both real Redis
deployments and deterministic in-memory storage for offline testability.
"""

import time
import asyncio
from typing import Optional, Dict, Tuple, Any

from app.realtime.config import config


class InMemoryStore:
    """Thread-safe and async-safe in-memory key-value store with TTL support."""

    def __init__(self):
        # key -> (value, expire_at_timestamp_or_None)
        self._data: Dict[str, Tuple[str, Optional[float]]] = {}
        self._lock = asyncio.Lock()

    def _purge_if_expired(self, key: str) -> None:
        if key in self._data:
            val, expire_at = self._data[key]
            if expire_at is not None and time.time() > expire_at:
                del self._data[key]

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            self._purge_if_expired(key)
            if key in self._data:
                return self._data[key][0]
            return None

    async def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> bool:
        async with self._lock:
            expire_at = (time.time() + ttl_seconds) if ttl_seconds is not None else None
            self._data[key] = (str(value), expire_at)
            return True

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    async def exists(self, key: str) -> bool:
        async with self._lock:
            self._purge_if_expired(key)
            return key in self._data

    async def expire(self, key: str, ttl_seconds: int) -> bool:
        async with self._lock:
            self._purge_if_expired(key)
            if key in self._data:
                val, _ = self._data[key]
                self._data[key] = (val, time.time() + ttl_seconds)
                return True
            return False

    async def ttl(self, key: str) -> int:
        async with self._lock:
            self._purge_if_expired(key)
            if key not in self._data:
                return -2  # Key does not exist
            _, expire_at = self._data[key]
            if expire_at is None:
                return -1  # No TTL set
            rem = int(expire_at - time.time())
            return max(0, rem)

    async def clear(self) -> None:
        async with self._lock:
            self._data.clear()


class RedisStore:
    """High-level async store wrapper that connects to Redis or falls back to InMemoryStore."""

    def __init__(self, redis_url: Optional[str] = None, use_redis: Optional[bool] = None):
        self._redis_url = redis_url or config.REDIS_URL
        self._use_redis = use_redis if use_redis is not None else config.USE_REDIS
        self._in_memory = InMemoryStore()
        self._redis_client = None
        self._is_connected = False

    async def _get_client(self):
        if not self._use_redis:
            return None

        if self._redis_client is None:
            try:
                import redis.asyncio as aioredis
                self._redis_client = aioredis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2.0
                )
                await self._redis_client.ping()
                self._is_connected = True
            except Exception:
                # Graceful fallback on connection failure
                self._redis_client = None
                self._is_connected = False
        return self._redis_client

    async def get(self, key: str) -> Optional[str]:
        client = await self._get_client()
        if client is not None:
            try:
                return await client.get(key)
            except Exception:
                pass
        return await self._in_memory.get(key)

    async def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> bool:
        client = await self._get_client()
        if client is not None:
            try:
                if ttl_seconds:
                    await client.setex(key, ttl_seconds, value)
                else:
                    await client.set(key, value)
                return True
            except Exception:
                pass
        return await self._in_memory.set(key, value, ttl_seconds=ttl_seconds)

    async def delete(self, key: str) -> bool:
        client = await self._get_client()
        if client is not None:
            try:
                res = await client.delete(key)
                return res > 0
            except Exception:
                pass
        return await self._in_memory.delete(key)

    async def exists(self, key: str) -> bool:
        client = await self._get_client()
        if client is not None:
            try:
                res = await client.exists(key)
                return res > 0
            except Exception:
                pass
        return await self._in_memory.exists(key)

    async def expire(self, key: str, ttl_seconds: int) -> bool:
        client = await self._get_client()
        if client is not None:
            try:
                res = await client.expire(key, ttl_seconds)
                return bool(res)
            except Exception:
                pass
        return await self._in_memory.expire(key, ttl_seconds)

    async def ttl(self, key: str) -> int:
        client = await self._get_client()
        if client is not None:
            try:
                return await client.ttl(key)
            except Exception:
                pass
        return await self._in_memory.ttl(key)

    async def close(self) -> None:
        if self._redis_client is not None:
            try:
                await self._redis_client.close()
            except Exception:
                pass
            self._redis_client = None
            self._is_connected = False
