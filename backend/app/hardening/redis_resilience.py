"""Phase 10G: Production Redis Failure Resilience Adapter.

Wraps Redis commands with timeout enforcement, circuit breakers, and deterministic in-memory fallbacks.
"""

import asyncio
from typing import Optional, Any
from app.hardening.exceptions import RedisError, TimeoutError
from app.hardening.circuit_breaker import CircuitBreaker


class HardenedRedisClient:
    """Provides resilient Redis caching with automatic circuit breaking and fallback."""

    def __init__(self, raw_store: Optional[Any] = None, timeout_sec: float = 2.0):
        self.raw_store = raw_store
        self.timeout_sec = timeout_sec
        self.circuit_breaker = CircuitBreaker("redis_cache", failure_threshold=3, recovery_timeout_sec=15.0)

    async def get_safe(self, key: str, fallback_value: Any = None) -> Any:
        """Reads a key from Redis safely, returning fallback_value on any error or open circuit."""
        if not self.raw_store:
            return fallback_value

        async def _do_get():
            return await asyncio.wait_for(self.raw_store.get(key), timeout=self.timeout_sec)

        try:
            val = await self.circuit_breaker.call(_do_get)
            return val if val is not None else fallback_value
        except Exception:
            return fallback_value

    async def set_safe(self, key: str, value: str, ttl_seconds: int = 3600) -> bool:
        """Sets a key in Redis safely with bounded timeout."""
        if not self.raw_store:
            return False

        async def _do_set():
            await asyncio.wait_for(self.raw_store.set(key, value, ttl_seconds=ttl_seconds), timeout=self.timeout_sec)
            return True

        try:
            return await self.circuit_breaker.call(_do_set)
        except Exception as e:
            raise RedisError(f"Failed to set key '{key}' in Redis.", internal_details=str(e))
