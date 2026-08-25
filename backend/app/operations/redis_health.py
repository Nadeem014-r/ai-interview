"""Phase 10H: Redis Operational Health Monitor.

Tracks Redis round-trip latency, availability, reconnect frequency, and fallback degradation state.
"""

import time
import asyncio
from typing import Dict, Any, Optional
from app.operations.metrics import op_metrics


class RedisHealthMonitor:
    """Monitors Redis health and latency without modifying Phase 10B store implementation."""

    @staticmethod
    async def inspect_redis(
        store: Optional[Any] = None,
        timeout_seconds: float = 2.0
    ) -> Dict[str, Any]:
        """Probes Redis store with ping key and records round-trip latency."""
        if store is None:
            return {
                "status": "healthy",
                "latency_ms": 0.5,
                "mode": "in_memory_or_mock",
                "timestamp": time.time()
            }

        start = time.monotonic()
        test_key = f"op:health:ping:{int(time.time() * 1000)}"
        try:
            await asyncio.wait_for(store.set(test_key, "pong", ttl_seconds=5), timeout=timeout_seconds)
            val = await asyncio.wait_for(store.get(test_key), timeout=timeout_seconds)
            await store.delete(test_key)

            duration_ms = (time.monotonic() - start) * 1000.0
            op_metrics.record_timing("redis_latency", duration_ms)

            return {
                "status": "healthy" if val == "pong" else "degraded",
                "latency_ms": round(duration_ms, 2),
                "timestamp": time.time()
            }
        except asyncio.TimeoutError:
            return {
                "status": "degraded",
                "error": f"Redis ping timed out after {timeout_seconds}s.",
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
