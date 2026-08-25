"""Phase 10G: Production Idempotency Engine.

Caches idempotent operational results to prevent duplicate execution of critical operations.
"""

import time
import threading
from typing import Dict, Tuple, Any, Optional, Callable, Awaitable


class IdempotencyEngine:
    """Thread-safe in-memory idempotency store with TTL expiration."""

    def __init__(self, default_ttl_sec: float = 300.0):
        self.default_ttl_sec = default_ttl_sec
        self._cache: Dict[str, Tuple[Any, float]] = {}  # key -> (result, expiry_timestamp)
        self._inflight: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def _cleanup_expired(self, now: float) -> None:
        """Purges expired entries."""
        expired = [k for k, (res, exp) in self._cache.items() if now > exp]
        for k in expired:
            self._cache.pop(k, None)

    async def execute_idempotent(
        self,
        idempotency_key: str,
        coro_fn: Callable[[], Awaitable[Any]],
        ttl_sec: Optional[float] = None
    ) -> Any:
        """
        Executes coro_fn only if idempotency_key has not been processed.
        Subsequent calls return the cached result until TTL expiry.
        """
        now = time.monotonic()
        ttl = ttl_sec or self.default_ttl_sec

        with self._global_lock:
            self._cleanup_expired(now)
            if idempotency_key in self._cache:
                result, exp = self._cache[idempotency_key]
                if now <= exp:
                    return result

        # Execute once
        result = await coro_fn()

        with self._global_lock:
            self._cache[idempotency_key] = (result, time.monotonic() + ttl)

        return result
