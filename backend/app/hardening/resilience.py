"""Phase 10G: Production Retry Policy & Backoff Resilience Engine.

Provides bounded exponential backoff with jitter and non-retryable error filtering.
"""

import time
import random
import asyncio
from typing import Callable, Awaitable, Any, Optional, Set, Type

from app.hardening.exceptions import (
    ProductionError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    CircuitOpenError,
    TimeoutError
)


class ResiliencePolicy:
    """Configurable async retry runner with exponential backoff and non-retryable exception guards."""

    NON_RETRYABLE_EXCEPTIONS: Set[Type[Exception]] = {
        ValidationError,
        AuthenticationError,
        AuthorizationError,
        CircuitOpenError
    }

    def __init__(
        self,
        max_attempts: int = 3,
        initial_backoff_sec: float = 0.1,
        max_backoff_sec: float = 5.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = False,
        sleep_fn: Optional[Callable[[float], Awaitable[None]]] = None,
        clock_fn: Optional[Callable[[], float]] = None
    ):
        self.max_attempts = max(1, max_attempts)
        self.initial_backoff_sec = initial_backoff_sec
        self.max_backoff_sec = max_backoff_sec
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self.sleep_fn = sleep_fn or asyncio.sleep
        self.clock_fn = clock_fn or time.monotonic

    def is_retryable(self, exc: Exception) -> bool:
        """Checks if exception is eligible for retry."""
        if any(isinstance(exc, cls) for cls in self.NON_RETRYABLE_EXCEPTIONS):
            return False
        if isinstance(exc, ProductionError) and not exc.retryable:
            return False
        return True

    def calculate_backoff(self, attempt: int) -> float:
        """Computes exponential backoff with optional jitter."""
        delay = min(self.max_backoff_sec, self.initial_backoff_sec * (self.backoff_multiplier ** (attempt - 1)))
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        return round(delay, 4)

    async def execute(self, coro_fn: Callable[[], Awaitable[Any]]) -> Any:
        """Executes coroutine function with bounded retries."""
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                return await coro_fn()
            except Exception as e:
                last_exc = e
                if not self.is_retryable(e) or attempt >= self.max_attempts:
                    raise e

                delay = self.calculate_backoff(attempt)
                await self.sleep_fn(delay)

        if last_exc:
            raise last_exc
        raise RuntimeError("Resilience execution completed without result or exception.")
