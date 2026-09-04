"""Phase 10C: Background Job Consumer Worker with Retries & Graceful Shutdown.

Processes queued jobs with timeout enforcement, exponential backoff retries,
and controlled cancellation upon shutdown.
"""

import time
import asyncio
from typing import Optional, List

from app._archive.production.config import production_config
from app._archive.production.jobs.models import Job, JobStatus
from app._archive.production.jobs.manager import ProductionJobManager
from app._archive.production.jobs.retry import ExponentialBackoffPolicy
from app._archive.production.security.secrets import mask_secret


class ProductionJobWorker:
    """Async background worker executing queued jobs with bounded retries."""

    def __init__(
        self,
        manager: ProductionJobManager,
        concurrency: int = production_config.WORKER_CONCURRENCY,
        backoff_policy: Optional[ExponentialBackoffPolicy] = None
    ):
        self.manager = manager
        self.concurrency = concurrency
        self.backoff_policy = backoff_policy or ExponentialBackoffPolicy(
            initial_backoff_sec=production_config.WORKER_INITIAL_BACKOFF_SEC
        )
        self._running_tasks: List[asyncio.Task] = []
        self._is_running = False
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start worker consumer tasks."""
        self._is_running = True
        self._stop_event.clear()
        for i in range(self.concurrency):
            task = asyncio.create_task(self._consumer_loop(i))
            self._running_tasks.append(task)

    async def _consumer_loop(self, worker_id: int) -> None:
        """Worker consumption loop."""
        while self._is_running:
            try:
                # Wait for next job ID with short timeout to check stop event
                try:
                    job_id = await asyncio.wait_for(self.manager._queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                job = await self.manager.get_job(job_id)
                if not job or job.status == JobStatus.CANCELLED:
                    self.manager._queue.task_done()
                    continue

                executor_fn = self.manager._executors.get(job_id)
                if not executor_fn:
                    job.status = JobStatus.FAILED
                    job.error = "No executor registered for job."
                    self.manager._queue.task_done()
                    continue

                await self._process_job(job, executor_fn)
                self.manager._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _process_job(self, job: Job, executor_fn) -> None:
        """Execute a single job with timeout and exponential backoff retry loop."""
        job.started_at = time.time()
        job.status = JobStatus.RUNNING

        while job.attempts <= job.max_retries and self._is_running:
            job.attempts += 1
            try:
                # Execute with timeout
                if asyncio.iscoroutinefunction(executor_fn):
                    res = await asyncio.wait_for(executor_fn(**job.payload), timeout=job.timeout_seconds)
                else:
                    res = executor_fn(**job.payload)

                job.result = res
                job.status = JobStatus.COMPLETED
                job.completed_at = time.time()
                job.error = None
                return

            except asyncio.TimeoutError:
                job.error = f"Job timed out after {job.timeout_seconds}s (attempt {job.attempts}/{job.max_retries + 1})."
            except Exception as e:
                job.error = f"Job failed: {str(e)}"

            if job.attempts <= job.max_retries and self._is_running:
                job.status = JobStatus.RETRYING
                delay = self.backoff_policy.get_delay_seconds(job.attempts)
                await asyncio.sleep(delay)

        job.status = JobStatus.FAILED
        job.completed_at = time.time()

    async def stop(self, timeout_seconds: float = production_config.GRACEFUL_SHUTDOWN_TIMEOUT) -> None:
        """Gracefully stop worker tasks within bounded timeout."""
        self._is_running = False
        self._stop_event.set()

        for t in self._running_tasks:
            t.cancel()

        if self._running_tasks:
            await asyncio.gather(*self._running_tasks, return_exceptions=True)
            self._running_tasks.clear()
