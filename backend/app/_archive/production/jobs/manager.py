"""Phase 10C: Background Job Manager & Registry.

Enqueues, tracks, cancels, and lists background maintenance and archival tasks.
"""

import asyncio
from typing import Dict, Any, Optional, List, Callable, Awaitable

from app._archive.production.config import production_config
from app._archive.production.jobs.models import Job, JobStatus
from app._archive.production.exceptions import JobError


class ProductionJobManager:
    """Manages asynchronous job registration, status tracking, and dispatching."""

    def __init__(self, max_queue_size: int = 1000):
        self.max_queue_size = max_queue_size
        self._jobs: Dict[str, Job] = {}
        self._executors: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._lock = asyncio.Lock()

    async def enqueue_job(
        self,
        name: str,
        executor_fn: Callable[..., Awaitable[Any]],
        payload: Optional[Dict[str, Any]] = None,
        max_retries: int = production_config.WORKER_MAX_RETRIES,
        timeout_seconds: float = 30.0
    ) -> Job:
        """Enqueues a new background job."""
        async with self._lock:
            if self._queue.full():
                raise JobError("Background job queue is full. Saturated worker.")

            job = Job(
                name=name,
                payload=payload or {},
                status=JobStatus.PENDING,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds
            )
            self._jobs[job.job_id] = job
            self._executors[job.job_id] = executor_fn
            await self._queue.put(job.job_id)
            return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Fetch job state by ID."""
        async with self._lock:
            return self._jobs.get(job_id)

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status == JobStatus.PENDING:
                job.status = JobStatus.CANCELLED
                return True
            return False

    async def list_jobs(self, status: Optional[JobStatus] = None) -> List[Job]:
        """List jobs matching the specified status filter."""
        async with self._lock:
            if status is None:
                return list(self._jobs.values())
            return [j for j in self._jobs.values() if j.status == status]
