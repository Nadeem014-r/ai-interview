"""Phase 10B: Realtime Sliding-Window Rate Limiter.

Protects against connection flooding, message flooding, audio chunk bursts, and reconnect abuse.
"""

import time
import asyncio
from typing import Dict, List, Tuple, Optional

from app.realtime.config import config
from app.realtime.exceptions import RateLimitExceededError


class RealtimeRateLimiter:
    """Sliding-window in-memory rate limiter with bounded memory cleanup."""

    def __init__(self):
        # key -> list of monotonic timestamps
        self._buckets: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        key: str,
        max_events: int,
        window_seconds: float = 1.0
    ) -> Tuple[bool, Optional[float]]:
        """
        Checks whether the key is within the rate limit.
        Returns (is_allowed: bool, retry_after_seconds: Optional[float]).
        """
        now = time.monotonic()
        async with self._lock:
            if key not in self._buckets:
                self._buckets[key] = [now]
                return True, None

            timestamps = self._buckets[key]
            # Prune timestamps older than window
            cutoff = now - window_seconds
            valid_timestamps = [ts for ts in timestamps if ts > cutoff]

            if len(valid_timestamps) >= max_events:
                oldest = valid_timestamps[0]
                retry_after = round(max(0.01, window_seconds - (now - oldest)), 2)
                self._buckets[key] = valid_timestamps
                return False, retry_after

            valid_timestamps.append(now)
            self._buckets[key] = valid_timestamps
            return True, None

    async def enforce(self, key: str, max_events: int, window_seconds: float = 1.0) -> None:
        """Enforces rate limit and raises RateLimitExceededError if limit is breached."""
        allowed, retry_after = await self.check_rate_limit(key, max_events, window_seconds)
        if not allowed:
            raise RateLimitExceededError(
                f"Rate limit of {max_events} events per {window_seconds}s exceeded for key '{key}'.",
                retry_after_seconds=retry_after
            )

    async def cleanup_stale_buckets(self, max_idle_seconds: float = 300.0) -> int:
        """Purge idle keys to prevent memory growth."""
        now = time.monotonic()
        removed = 0
        async with self._lock:
            stale_keys = []
            for k, timestamps in self._buckets.items():
                if not timestamps or (now - timestamps[-1]) > max_idle_seconds:
                    stale_keys.append(k)
            for k in stale_keys:
                del self._buckets[k]
                removed += 1
        return removed


# Global rate limiter instance
rate_limiter = RealtimeRateLimiter()
