"""Phase 10F: Production Redis Resilience & Distributed Coordination Supervisor.

Wraps Phase 10B RedisStore with connection validation, timeouts, health state, and multi-worker safety.
"""

import time
import asyncio
from typing import Optional, Any

from app.realtime.redis_store import RedisStore, InMemoryStore
from app._archive.ops.exceptions import OpsRedisError
from app._archive.ops.metrics import ops_metrics


class RedisResilienceSupervisor:
    """Oversees Redis connection stability and fallback state."""

    def __init__(self, store: Optional[RedisStore] = None):
        self.store = store or RedisStore(use_redis=False)

    async def check_health(self, timeout_seconds: float = 2.0) -> bool:
        """Executes a lightweight Redis ping check."""
        start = time.monotonic()
        try:
            test_key = f"ops:health:ping:{int(time.time())}"
            await asyncio.wait_for(self.store.set(test_key, "pong", ttl_seconds=5), timeout=timeout_seconds)
            val = await asyncio.wait_for(self.store.get(test_key), timeout=timeout_seconds)
            await self.store.delete(test_key)
            ops_metrics.record_latency("redis_latency", (time.monotonic() - start) * 1000.0)
            return val == "pong"
        except Exception:
            return False

    async def get_with_fallback(self, key: str, fallback_val: Any = None) -> Any:
        """Reads key safely with fallback value on error."""
        try:
            val = await self.store.get(key)
            return val if val is not None else fallback_val
        except Exception:
            return fallback_val

    async def set_with_timeout(self, key: str, value: str, ttl_seconds: int = 3600, timeout_seconds: float = 3.0) -> bool:
        """Sets key with strict timeout enforcement."""
        try:
            await asyncio.wait_for(self.store.set(key, value, ttl_seconds=ttl_seconds), timeout=timeout_seconds)
            return True
        except Exception as e:
            raise OpsRedisError(f"Redis set failed for key '{key}'.", raw_error=e)
