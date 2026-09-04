"""Phase 10H: Service Liveness & Overall Health Subsystem.

Provides lightweight, isolated process liveness probes suitable for container orchestrators.
"""

import time
from typing import Dict, Any


class OperationalHealthService:
    """Evaluates process liveness and top-level health state."""

    _process_started_at: float = time.time()

    @classmethod
    def get_liveness(cls) -> Dict[str, Any]:
        """
        Liveness check: confirms process is alive and responsive.
        Does NOT fail due to downstream database or Redis transient blips.
        """
        return {
            "status": "healthy",
            "uptime_seconds": round(time.time() - cls._process_started_at, 2),
            "timestamp": time.time(),
            "service": "ai_interviewer"
        }
