"""Phase 10H: Graceful Startup Orchestrator.

Sequences pre-flight configuration validation, dependency health probes, and metrics initialization.
"""

import asyncio
from typing import Dict, Any, Optional

from app._archive.operations.config import ProductionConfigValidator, ValidationStatus
from app._archive.operations.readiness import OperationalReadinessService
from app._archive.operations.logging import OperationalLogger


class StartupOrchestrator:
    """Coordinates deterministic, safe service initialization."""

    @staticmethod
    async def run_startup_sequence(
        env_vars: Optional[Dict[str, str]] = None,
        db_session: Optional[Any] = None,
        redis_store: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Executes the complete multi-step startup sequence."""
        OperationalLogger.log("service.startup.initiating", component="lifecycle", operation="startup")

        # 1. Config Validation
        config_res = ProductionConfigValidator.validate_environment(env_vars)
        if config_res.status == ValidationStatus.INVALID:
            OperationalLogger.log(
                "service.startup.config_invalid",
                level="ERROR",
                component="lifecycle",
                operation="startup",
                data={"errors": config_res.errors}
            )
            return {
                "ready": False,
                "reason": "Configuration validation failed.",
                "errors": config_res.errors
            }

        # 2. Dependency Readiness Probe
        readiness = await OperationalReadinessService.evaluate_readiness(
            db_session=db_session,
            redis_store=redis_store
        )

        is_ready = readiness["status"] in ("healthy", "degraded")

        OperationalLogger.log(
            "service.startup.completed",
            component="lifecycle",
            operation="startup",
            status="ready" if is_ready else "failed",
            data={"readiness": readiness["status"]}
        )

        return {
            "ready": is_ready,
            "readiness_status": readiness["status"],
            "components": readiness["components"],
            "config_status": config_res.status.value
        }
