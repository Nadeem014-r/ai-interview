"""Phase 10G: Advanced Production Multi-Tier Rate Limiting.

Provides granular, key-isolated token bucket rate limiters with burst allowance, cooldowns, and retry-after calculation.
"""

import time
import threading
from typing import Dict, Tuple, Optional, Callable
from app.hardening.exceptions import RateLimitError


class TokenBucketLimiter:
    """Thread-safe Token Bucket rate limiter with clock injection for deterministic testing."""

    def __init__(
        self,
        rate_per_second: float,
        burst_capacity: int,
        clock_fn: Optional[Callable[[], float]] = None
    ):
        self.rate_per_second = rate_per_second
        self.burst_capacity = burst_capacity
        self.clock_fn = clock_fn or time.monotonic
        self._buckets: Dict[str, Tuple[float, float]] = {}  # key -> (tokens, last_update)
        self._lock = threading.Lock()

    def acquire(self, key: str, tokens_required: float = 1.0) -> Tuple[bool, float]:
        """
        Attempts to acquire tokens for the specified key.
        Returns (is_allowed, retry_after_seconds).
        """
        with self._lock:
            now = self.clock_fn()
            current_tokens, last_update = self._buckets.get(key, (float(self.burst_capacity), now))

            # Replenish tokens based on elapsed time
            elapsed = max(0.0, now - last_update)
            current_tokens = min(float(self.burst_capacity), current_tokens + (elapsed * self.rate_per_second))

            if current_tokens >= tokens_required:
                current_tokens -= tokens_required
                self._buckets[key] = (current_tokens, now)
                return True, 0.0
            else:
                # Calculate wait time needed to accumulate required tokens
                missing_tokens = tokens_required - current_tokens
                retry_after = missing_tokens / self.rate_per_second if self.rate_per_second > 0 else 1.0
                self._buckets[key] = (current_tokens, now)
                return False, round(retry_after, 2)

    def enforce(self, key: str, tokens_required: float = 1.0) -> None:
        """Enforces rate limit, raising RateLimitError if exceeded."""
        allowed, retry_after = self.acquire(key, tokens_required)
        if not allowed:
            raise RateLimitError(
                message=f"Rate limit exceeded for key '{key}'. Please retry after {retry_after} seconds.",
                retry_after_sec=retry_after
            )


class MultiTierRateLimiter:
    """Manages segregated rate limiters for auth, HTTP requests, WebSockets, audio chunks, and reconnects."""

    def __init__(self, clock_fn: Optional[Callable[[], float]] = None):
        self.clock_fn = clock_fn or time.monotonic
        # HTTP Requests: 2.0/s sustained, burst of 20
        self.http_limiter = TokenBucketLimiter(rate_per_second=2.0, burst_capacity=20, clock_fn=self.clock_fn)
        # Auth Attempts: 0.2/s sustained (1 per 5s), burst of 5
        self.auth_limiter = TokenBucketLimiter(rate_per_second=0.2, burst_capacity=5, clock_fn=self.clock_fn)
        # WebSocket Messages: 30.0/s sustained, burst of 60
        self.ws_msg_limiter = TokenBucketLimiter(rate_per_second=30.0, burst_capacity=60, clock_fn=self.clock_fn)
        # Reconnects: 0.15/s sustained, burst of 3
        self.reconnect_limiter = TokenBucketLimiter(rate_per_second=0.15, burst_capacity=3, clock_fn=self.clock_fn)
        # Audio Chunks: 10.0/s sustained, burst of 20
        self.audio_chunk_limiter = TokenBucketLimiter(rate_per_second=10.0, burst_capacity=20, clock_fn=self.clock_fn)
