"""Phase 10H: Graceful Shutdown Coordinator.

Flushes operational telemetry, drains active jobs, cancels expired work, and closes connections within a bounded timeout.
"""

import asyncio
from typing import List, Callable, Awaitable, Dict, Any, Optional
from app._archive.operations.logging import OperationalLogger


class ShutdownCoordinator:
    """Manages graceful service termination without data loss or hung processes."""

    def __init__(self, default_timeout_sec: float = 15.0):
        self.default_timeout_sec = default_timeout_sec
        self._hooks: List[Callable[[], Awaitable[None]]] = []
        self._is_shutting_down = False
        self._lock = asyncio.Lock()

    def register_hook(self, hook: Callable[[], Awaitable[None]]) -> None:
        """Registers an asynchronous teardown handler."""
        self._hooks.append(hook)

    async def execute_shutdown(self, timeout_sec: Optional[float] = None) -> Dict[str, Any]:
        """Executes all teardown hooks in order, bounded by timeout."""
        timeout = timeout_sec or self.default_timeout_sec
        async with self._lock:
            if self._is_shutting_down:
                return {"status": "already_shutting_down"}
            self._is_shutting_down = True

        OperationalLogger.log("service.shutdown.initiating", component="lifecycle", operation="shutdown")

        hook_count = len(self._hooks)
        failed_hooks = 0

        for hook in self._hooks:
            try:
                per_hook_timeout = max(1.0, timeout / max(1, hook_count))
                await asyncio.wait_for(hook(), timeout=per_hook_timeout)
            except Exception as e:
                failed_hooks += 1
                OperationalLogger.log(
                    "service.shutdown.hook_failed",
                    level="WARNING",
                    component="lifecycle",
                    operation="shutdown",
                    data={"error": str(e)}
                )

        OperationalLogger.log("service.shutdown.completed", component="lifecycle", operation="shutdown")

        return {
            "status": "completed",
            "hooks_executed": hook_count,
            "failed_hooks": failed_hooks
        }
