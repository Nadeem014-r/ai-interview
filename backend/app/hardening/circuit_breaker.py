"""Phase 10G: Production Circuit Breaker.

Provides fast-failure state tracking (CLOSED, OPEN, HALF_OPEN) for external provider protection.
"""

import time
import threading
from enum import Enum
from typing import Optional, Callable, Awaitable, Any

from app.hardening.exceptions import CircuitOpenError


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Thread-safe circuit breaker protecting downstream dependencies from cascading failure."""

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout_sec: float = 30.0,
        half_open_max_probes: int = 2,
        clock_fn: Optional[Callable[[], float]] = None
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.half_open_max_probes = half_open_max_probes
        self.clock_fn = clock_fn or time.monotonic

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = self.clock_fn()
        self._lock = threading.Lock()

    def record_success(self) -> None:
        """Records a successful operation."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.half_open_max_probes:
                    # Successfully recovered -> close circuit
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    self.last_state_change = self.clock_fn()
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def record_failure(self) -> None:
        """Records a failed operation."""
        with self._lock:
            now = self.clock_fn()
            if self.state == CircuitState.HALF_OPEN:
                # Probe failed -> trip back to OPEN
                self.state = CircuitState.OPEN
                self.last_state_change = now
                self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.last_state_change = now

    def before_call(self) -> None:
        """Evaluates circuit state before executing a dependency call."""
        with self._lock:
            now = self.clock_fn()
            if self.state == CircuitState.OPEN:
                elapsed = now - self.last_state_change
                if elapsed >= self.recovery_timeout_sec:
                    # Transition to HALF_OPEN probe state
                    self.state = CircuitState.HALF_OPEN
                    self.last_state_change = now
                    self.success_count = 0
                else:
                    cooldown_remaining = self.recovery_timeout_sec - elapsed
                    raise CircuitOpenError(self.service_name, cooldown_remaining=cooldown_remaining)

    async def call(self, coro_fn: Callable[[], Awaitable[Any]]) -> Any:
        """Executes a coroutine guarded by this circuit breaker."""
        self.before_call()
        try:
            res = await coro_fn()
            self.record_success()
            return res
        except Exception as e:
            self.record_failure()
            raise e
