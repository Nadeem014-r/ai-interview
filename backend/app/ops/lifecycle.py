"""Phase 10F: Production Startup & Graceful Shutdown Coordinator.

Manages clean pre-flight initialization and idempotent graceful service termination.
"""

import asyncio
from typing import Optional, Callable, List, Awaitable

from app.ops.config import ProductionOpsConfig, ops_config
from app.ops.validator import DeploymentValidator
from app.ops.logging import ProductionLogger
from app.ops.exceptions import OpsConfigurationError


class ProductionLifecycleCoordinator:
    """Coordinates lifecycle stages from startup pre-flight to graceful teardown."""

    def __init__(self, config: Optional[ProductionOpsConfig] = None):
        self.config = config or ops_config
        self._is_started = False
        self._is_shut_down = False
        self._shutdown_hooks: List[Callable[[], Awaitable[None]]] = []
        self._lock = asyncio.Lock()

    def register_shutdown_hook(self, hook_fn: Callable[[], Awaitable[None]]) -> None:
        """Registers an asynchronous cleanup hook to execute upon shutdown."""
        self._shutdown_hooks.append(hook_fn)

    async def execute_startup(self) -> bool:
        """Performs structured pre-flight validation and startup initialization."""
        async with self._lock:
            if self._is_started:
                return True

            ProductionLogger.log("ops.startup.initiating", data={"environment": self.config.ENVIRONMENT})

            # 1. Validate deployment configuration
            is_valid, errors, warnings = DeploymentValidator.validate_deployment(self.config)
            if not is_valid and self.config.ENVIRONMENT == "production":
                err_msg = f"Startup blocked by validation errors: {'; '.join(errors)}"
                ProductionLogger.log("ops.startup.failed", level="ERROR", data={"errors": errors})
                raise OpsConfigurationError(err_msg)

            self._is_started = True
            ProductionLogger.log("ops.startup.ready", status="ready")
            return True

    async def execute_shutdown(self, timeout_seconds: Optional[float] = None) -> bool:
        """Executes registered shutdown hooks within a bounded timeout."""
        async with self._lock:
            if self._is_shut_down:
                return True

            timeout = timeout_seconds or self.config.GRACEFUL_SHUTDOWN_TIMEOUT
            ProductionLogger.log("ops.shutdown.initiating", data={"timeout_seconds": timeout})

            for hook in self._shutdown_hooks:
                try:
                    await asyncio.wait_for(hook(), timeout=timeout / max(1, len(self._shutdown_hooks)))
                except Exception as e:
                    ProductionLogger.log("ops.shutdown.hook_failed", level="WARNING", data={"error": str(e)})

            self._is_shut_down = True
            self._is_started = False
            ProductionLogger.log("ops.shutdown.completed", status="shutdown")
            return True
