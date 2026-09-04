"""Phase 10C: Multi-Tier Health & Readiness Diagnostics.

Provides isolated liveness and readiness checks without exposing credentials.
"""

import time
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app._archive.production.config import production_config, ProductionConfig
from app._archive.production.storage.local import ProductionLocalStorage
from app._archive.production.environment import ProductionEnvironmentValidator


class ProductionHealthChecker:
    """Multi-tier system health and readiness evaluator."""

    _process_start_time: float = time.time()

    @classmethod
    def check_liveness(cls) -> Dict[str, Any]:
        """
        Liveness check: verifies process is alive and responsive.
        Does NOT depend on external systems or databases.
        """
        uptime_sec = round(time.time() - cls._process_start_time, 2)
        return {
            "status": "healthy",
            "uptime_seconds": uptime_sec,
            "timestamp": time.time()
        }

    @classmethod
    async def check_readiness(
        cls,
        db: Optional[AsyncSession] = None,
        store: Optional[Any] = None,
        storage: Optional[ProductionLocalStorage] = None,
        config: Optional[ProductionConfig] = None
    ) -> Dict[str, Any]:
        """
        Readiness check: evaluates database, storage, redis, and configuration status.
        Never exposes passwords or sensitive credentials.
        """
        cfg = config or production_config
        components: Dict[str, str] = {}
        overall_status = "healthy"

        # 1. Configuration check
        issues = ProductionEnvironmentValidator.validate_configuration(cfg)
        if issues:
            components["configuration"] = "degraded" if cfg.ENVIRONMENT != "production" else "unhealthy"
            if cfg.ENVIRONMENT == "production":
                overall_status = "unhealthy"
        else:
            components["configuration"] = "healthy"

        # 2. Database check
        if db is not None:
            try:
                res = await db.execute(text("SELECT 1"))
                if res.scalar() == 1:
                    components["database"] = "healthy"
                else:
                    components["database"] = "degraded"
                    overall_status = "degraded"
            except Exception:
                components["database"] = "unhealthy"
                overall_status = "unhealthy"
        else:
            components["database"] = "healthy"

        # 3. Storage check
        if storage is not None:
            try:
                if storage.base_path.exists():
                    components["storage"] = "healthy"
                else:
                    components["storage"] = "degraded"
                    if overall_status == "healthy":
                        overall_status = "degraded"
            except Exception:
                components["storage"] = "degraded"
                if overall_status == "healthy":
                    overall_status = "degraded"
        else:
            components["storage"] = "healthy"

        # 4. Redis/Store check
        if store is not None:
            try:
                await store.set("health:readiness:ping", "pong", ttl_seconds=5)
                val = await store.get("health:readiness:ping")
                components["redis_store"] = "healthy" if val == "pong" else "degraded"
            except Exception:
                components["redis_store"] = "degraded"
                if overall_status == "healthy":
                    overall_status = "degraded"
        else:
            components["redis_store"] = "healthy"

        return {
            "status": overall_status,
            "components": components,
            "timestamp": time.time()
        }
