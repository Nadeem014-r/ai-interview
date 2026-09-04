"""Phase 10H: Database Operational Health Monitor.

Inspects database connection latency, availability, and failure patterns without modifying SQLAlchemy models.
"""

import time
import asyncio
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app._archive.operations.metrics import op_metrics


class DatabaseHealthMonitor:
    """Monitors database connection latency and availability for operational dashboards."""

    @staticmethod
    async def inspect_database(
        session: Optional[AsyncSession] = None,
        timeout_seconds: float = 3.0
    ) -> Dict[str, Any]:
        """Performs connection latency and query execution health probe."""
        if session is None:
            return {
                "status": "healthy",
                "latency_ms": 0.5,
                "mode": "standalone_or_mock",
                "timestamp": time.time()
            }

        start = time.monotonic()
        try:
            res = await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=timeout_seconds)
            duration_ms = (time.monotonic() - start) * 1000.0
            op_metrics.record_timing("db_latency", duration_ms)
            is_ok = res.scalar() == 1

            return {
                "status": "healthy" if is_ok else "degraded",
                "latency_ms": round(duration_ms, 2),
                "timestamp": time.time()
            }
        except asyncio.TimeoutError:
            return {
                "status": "degraded",
                "error": f"Database health check timed out after {timeout_seconds}s.",
                "timestamp": time.time()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
