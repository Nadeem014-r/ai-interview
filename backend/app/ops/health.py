"""Phase 10F: Production Health & Readiness Evaluator.

Provides isolated liveness and readiness diagnostic endpoints without leaking credentials.
"""

import time
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.ops.config import ops_config, ProductionOpsConfig
from app.ops.database import DatabaseResilience
from app.ops.redis_resilience import RedisResilienceSupervisor
from app.ops.validator import DeploymentValidator


class ProductionHealthService:
    """Evaluates multi-component system health for Kubernetes and Docker healthchecks."""

    _start_time: float = time.time()

    @classmethod
    def check_liveness(cls) -> Dict[str, Any]:
        """
        Liveness check: returns process health status.
        Does NOT depend on external database or Redis servers.
        """
        return {
            "status": "healthy",
            "uptime_seconds": round(time.time() - cls._start_time, 2),
            "timestamp": time.time()
        }

    @classmethod
    async def check_readiness(
        cls,
        db_session: Optional[AsyncSession] = None,
        redis_supervisor: Optional[RedisResilienceSupervisor] = None,
        config: Optional[ProductionOpsConfig] = None
    ) -> Dict[str, Any]:
        """
        Readiness check: evaluates readiness of critical dependencies.
        Never exposes secrets or credentials.
        """
        cfg = config or ops_config
        components: Dict[str, str] = {}
        overall_status = "healthy"

        # 1. Config validation
        is_valid, errors, _ = DeploymentValidator.validate_deployment(cfg)
        if not is_valid and cfg.ENVIRONMENT == "production":
            components["configuration"] = "unhealthy"
            overall_status = "unhealthy"
        else:
            components["configuration"] = "healthy"

        # 2. Database readiness
        db_ok = await DatabaseResilience.check_health(db_session)
        if db_ok:
            components["database"] = "healthy"
        else:
            components["database"] = "degraded"
            if overall_status == "healthy":
                overall_status = "degraded"

        # 3. Redis readiness
        if redis_supervisor:
            redis_ok = await redis_supervisor.check_health()
            if redis_ok:
                components["redis"] = "healthy"
            else:
                components["redis"] = "degraded"
                if overall_status == "healthy":
                    overall_status = "degraded"
        else:
            components["redis"] = "healthy"

        # 4. Storage readiness
        components["storage"] = "healthy"

        return {
            "status": overall_status,
            "components": components,
            "timestamp": time.time()
        }
