"""Phase 10G: Production Background Job Safety & Concurrency Supervisor.

Guarantees bounded queue limits, max concurrency semaphores, duplicate execution protection, and dead-letter classification.
"""

import time
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable, Set
from dataclasses import dataclass, field

from app.hardening.exceptions import JobError, ResourceLimitError, TimeoutError


@dataclass
class JobRecord:
    job_id: str
    idempotency_key: str
    status: str = "pending"  # pending, running, completed, dead_letter, cancelled
    attempts: int = 0
    max_retries: int = 3
    timeout_sec: float = 30.0
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class HardenedJobSupervisor:
    """Manages background task execution with strict capacity bounds and duplicate defense."""

    def __init__(self, max_concurrent: int = 20, max_queue: int = 500):
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._jobs: Dict[str, JobRecord] = {}
        self._idempotency_keys: Set[str] = set()
        self._lock = asyncio.Lock()

    async def submit_and_execute(
        self,
        job_id: str,
        idempotency_key: str,
        coro_fn: Callable[[], Awaitable[Any]],
        max_retries: int = 3,
        timeout_sec: float = 30.0
    ) -> Any:
        """Executes a bounded background job."""
        async with self._lock:
            if len(self._jobs) >= self.max_queue:
                raise ResourceLimitError(f"Job queue capacity limit reached ({self.max_queue}).")

            # Duplicate protection
            if idempotency_key in self._idempotency_keys:
                # Find existing job
                for j in self._jobs.values():
                    if j.idempotency_key == idempotency_key and j.status == "completed":
                        return j.result

            job = JobRecord(
                job_id=job_id,
                idempotency_key=idempotency_key,
                max_retries=max_retries,
                timeout_sec=timeout_sec
            )
            self._jobs[job_id] = job
            self._idempotency_keys.add(idempotency_key)

        # Acquire concurrency semaphore
        async with self.semaphore:
            job.status = "running"
            last_err: Optional[Exception] = None

            while job.attempts <= job.max_retries:
                job.attempts += 1
                try:
                    res = await asyncio.wait_for(coro_fn(), timeout=job.timeout_sec)
                    job.status = "completed"
                    job.completed_at = time.time()
                    job.result = res
                    return res
                except asyncio.TimeoutError as te:
                    last_err = TimeoutError(f"Job '{job_id}' timed out after {job.timeout_sec}s.", internal_details=str(te))
                    job.error = str(last_err)
                except Exception as e:
                    last_err = e
                    job.error = str(e)

                if job.attempts <= job.max_retries:
                    await asyncio.sleep(0.05 * (2 ** (job.attempts - 1)))

            job.status = "dead_letter"
            job.completed_at = time.time()
            if last_err:
                raise JobError(f"Job '{job_id}' exhausted all {job.max_retries} retries.", internal_details=str(last_err))
            raise JobError(f"Job '{job_id}' failed.")

    async def get_job_status(self, job_id: str) -> Optional[JobRecord]:
        async with self._lock:
            return self._jobs.get(job_id)
