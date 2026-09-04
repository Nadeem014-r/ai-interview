"""Phase 10C: Production Lifecycle Manager & Graceful Shutdown.

Coordinates application startup verification, background worker initialization,
and idempotent graceful shutdown with bounded timeouts.
"""

import asyncio
from typing import Optional

from app._archive.production.config import production_config, ProductionConfig
from app._archive.production.environment import ProductionEnvironmentValidator
from app._archive.production.storage.local import ProductionLocalStorage
from app._archive.production.jobs.manager import ProductionJobManager
from app._archive.production.jobs.worker import ProductionJobWorker
from app._archive.production.observability.logging import StructuredProductionLogger


class ProductionLifecycleManager:
    """Manages lifecycle hooks, pre-flight readiness, and graceful shutdown."""

    def __init__(
        self,
        config: Optional[ProductionConfig] = None,
        job_manager: Optional[ProductionJobManager] = None,
        storage: Optional[ProductionLocalStorage] = None
    ):
        self.config = config or production_config
        self.job_manager = job_manager or ProductionJobManager()
        self.storage = storage or ProductionLocalStorage(base_path=self.config.STORAGE_LOCAL_PATH)
        self.worker: Optional[ProductionJobWorker] = None
        self._is_started = False
        self._is_shut_down = False
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        """Executes pre-flight startup initialization."""
        async with self._lock:
            if self._is_started:
                return

            StructuredProductionLogger.log_event("lifecycle.startup.starting", environment=self.config.ENVIRONMENT)

            # 1. Enforce environment readiness
            ProductionEnvironmentValidator.enforce_production_readiness(self.config)

            # 2. Ensure storage path exists
            self.storage.base_path.mkdir(parents=True, exist_ok=True)

            # 3. Start background job worker
            self.worker = ProductionJobWorker(
                manager=self.job_manager,
                concurrency=self.config.WORKER_CONCURRENCY
            )
            await self.worker.start()

            self._is_started = True
            StructuredProductionLogger.log_event("lifecycle.startup.completed")

    async def shutdown(self, timeout_seconds: Optional[float] = None) -> None:
        """Gracefully and idempotently shuts down all running workers and resources."""
        async with self._lock:
            if self._is_shut_down:
                return

            timeout = timeout_seconds or self.config.GRACEFUL_SHUTDOWN_TIMEOUT
            StructuredProductionLogger.log_event("lifecycle.shutdown.starting", timeout_seconds=timeout)

            # Stop worker
            if self.worker:
                try:
                    await asyncio.wait_for(self.worker.stop(timeout_seconds=timeout), timeout=timeout)
                except Exception as e:
                    StructuredProductionLogger.log_event("lifecycle.shutdown.worker_error", error=str(e), level="warning")

            self._is_shut_down = True
            self._is_started = False
            StructuredProductionLogger.log_event("lifecycle.shutdown.completed")
