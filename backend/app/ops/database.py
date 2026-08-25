"""Phase 10F: Production Database Resilience & Reliability Layer.

Provides connection pre-ping, health verification, pool configuration, and safe read-retry boundaries.
"""

import time
import asyncio
from typing import Optional, Callable, Any, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.ops.exceptions import OpsDatabaseError
from app.ops.metrics import ops_metrics


class DatabaseResilience:
    """Production database supervisor and health checker."""

    @staticmethod
    async def check_health(session: Optional[AsyncSession] = None, timeout_seconds: float = 3.0) -> bool:
        """Executes a lightweight connection pre-ping."""
        if session is None:
            return True  # Offline / mock testing mode

        start = time.monotonic()
        try:
            res = await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=timeout_seconds)
            duration_ms = (time.monotonic() - start) * 1000.0
            ops_metrics.record_latency("database_latency", duration_ms)
            return res.scalar() == 1
        except Exception:
            return False

    @staticmethod
    async def execute_safe_read_with_retry(
        query_fn: Callable[[], Awaitable[Any]],
        max_attempts: int = 2,
        backoff_sec: float = 0.2
    ) -> Any:
        """
        Executes an idempotent read query with bounded retry on transient connection drops.
        NEVER use for arbitrary writes or transaction commits.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                start = time.monotonic()
                result = await query_fn()
                ops_metrics.record_latency("database_latency", (time.monotonic() - start) * 1000.0)
                return result
            except Exception as e:
                last_exc = e
                if attempt < max_attempts:
                    await asyncio.sleep(backoff_sec * (2 ** (attempt - 1)))

        raise OpsDatabaseError(f"Database read query failed after {max_attempts} attempts.", raw_error=last_exc)
