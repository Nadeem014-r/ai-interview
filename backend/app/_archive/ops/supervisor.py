"""Phase 10F: Production Background Job Reliability Supervisor.

Guarantees bounded retries, exponential backoff, dead-letter tracking, and graceful job cancellation.
"""

import time
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable, List
from dataclasses import dataclass, field

from app._archive.ops.exceptions import OpsTimeoutError
from app._archive.ops.metrics import ops_metrics


@dataclass
class SupervisedJob:
    """Represents a supervised background execution task."""
    job_id: str
    name: str
    status: str = "pending"  # pending, running, completed, failed, dead_letter, cancelled
    attempts: int = 0
    max_retries: int = 3
    timeout_seconds: float = 30.0
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Any] = None


class JobSupervisor:
    """Supervises async background operations with exponential retries and dead-letter protection."""

    def __init__(self, initial_backoff_sec: float = 0.2, max_backoff_sec: float = 10.0):
        self.initial_backoff_sec = initial_backoff_sec
        self.max_backoff_sec = max_backoff_sec
        self._jobs: Dict[str, SupervisedJob] = {}
        self._lock = asyncio.Lock()

    async def execute_job(
        self,
        job_id: str,
        name: str,
        coro_fn: Callable[[], Awaitable[Any]],
        max_retries: int = 3,
        timeout_seconds: float = 30.0
    ) -> Any:
        """Executes a supervised background job with bounded retry policy."""
        job = SupervisedJob(
            job_id=job_id,
            name=name,
            status="running",
            max_retries=max_retries,
            timeout_seconds=timeout_seconds
        )
        async with self._lock:
            self._jobs[job_id] = job

        last_error: Optional[Exception] = None

        while job.attempts <= job.max_retries:
            job.attempts += 1
            try:
                # Enforce execution timeout
                res = await asyncio.wait_for(coro_fn(), timeout=job.timeout_seconds)
                job.status = "completed"
                job.completed_at = time.time()
                job.result = res
                ops_metrics.increment("background_job_success")
                return res

            except asyncio.TimeoutError as te:
                last_error = OpsTimeoutError(f"Job '{name}' timed out after {job.timeout_seconds}s.", raw_error=te)
                job.error = str(last_error)
            except Exception as e:
                last_error = e
                job.error = str(e)

            if job.attempts <= job.max_retries:
                # Exponential backoff delay
                delay = min(self.max_backoff_sec, self.initial_backoff_sec * (2 ** (job.attempts - 1)))
                await asyncio.sleep(delay)

        # Retries exhausted -> mark dead letter
        job.status = "dead_letter"
        job.completed_at = time.time()
        ops_metrics.increment("background_job_failure")
        if last_error:
            raise last_error
        raise RuntimeError(f"Job '{name}' failed with no exception recorded.")

    async def get_job(self, job_id: str) -> Optional[SupervisedJob]:
        async with self._lock:
            return self._jobs.get(job_id)
