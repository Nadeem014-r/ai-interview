"""Phase 10B: Lightweight Async Background Job Worker.

Provides bounded asynchronous job execution, retries with backoff,
and graceful shutdown for session cleanup and maintenance tasks.
"""

import asyncio
from typing import Callable, Awaitable, Any, Optional, Dict


class BackgroundJobManager:
    """Async background worker with bounded retries and graceful shutdown."""

    def __init__(self, max_concurrent_jobs: int = 10):
        self.max_concurrent_jobs = max_concurrent_jobs
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._running_tasks: set[asyncio.Task] = set()
        self._is_shutting_down: bool = False

    async def run_job(
        self,
        job_fn: Callable[[], Awaitable[Any]],
        max_retries: int = 3,
        initial_backoff_sec: float = 0.5,
        job_name: str = "background_job"
    ) -> Any:
        """Execute a job with bounded exponential retries."""
        async with self._semaphore:
            attempt = 0
            backoff = initial_backoff_sec
            last_error = None

            while attempt <= max_retries:
                if self._is_shutting_down:
                    return None
                try:
                    return await job_fn()
                except Exception as e:
                    last_error = e
                    attempt += 1
                    if attempt <= max_retries:
                        await asyncio.sleep(backoff)
                        backoff *= 2.0

            # Max retries exhausted
            return None

    def enqueue_job(
        self,
        job_fn: Callable[[], Awaitable[Any]],
        max_retries: int = 2,
        job_name: str = "background_job"
    ) -> asyncio.Task:
        """Enqueue job as non-blocking background task."""
        if self._is_shutting_down:
            # Return a dummy completed task
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            future.set_result(None)
            return future

        task = asyncio.create_task(
            self.run_job(job_fn, max_retries=max_retries, job_name=job_name)
        )
        self._running_tasks.add(task)
        task.add_done_callback(lambda t: self._running_tasks.discard(t))
        return task

    async def shutdown(self, timeout_seconds: float = 5.0) -> None:
        """Gracefully wait for pending background jobs to finish."""
        self._is_shutting_down = True
        if not self._running_tasks:
            return

        tasks = list(self._running_tasks)
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            for t in tasks:
                if not t.done():
                    t.cancel()
        self._running_tasks.clear()
