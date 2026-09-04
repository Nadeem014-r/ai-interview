"""Phase 10H: Production System Diagnostics & Telemetry Snapshot Collector.

Aggregates operational metrics, health indicators, alert histories, and cost summaries with zero secret leaks.
"""

import time
from typing import Dict, Any, Optional

from app._archive.ops.secrets import redact_secrets
from app._archive.operations.health import OperationalHealthService
from app._archive.operations.metrics import op_metrics
from app._archive.operations.cost_monitor import cost_monitor
from app._archive.operations.alerts import alert_engine


class ProductionDiagnosticsCollector:
    """Collects an integrated operational diagnostic bundle."""

    @staticmethod
    def generate_diagnostic_snapshot(environment: str = "production") -> Dict[str, Any]:
        """Generates a complete, secret-safe diagnostic snapshot."""
        liveness = OperationalHealthService.get_liveness()
        metrics_snap = op_metrics.export_metrics()
        recent_alerts = alert_engine.get_recent_alerts(limit=10)
        total_cost = cost_monitor.get_total_cost_usd()

        bundle = {
            "service": "ai_interviewer",
            "environment": environment,
            "timestamp": time.time(),
            "liveness": liveness,
            "counters": metrics_snap.get("counters", {}),
            "gauges": metrics_snap.get("gauges", {}),
            "percentiles": metrics_snap.get("percentiles", {}),
            "recent_alerts": recent_alerts,
            "cost_summary": {
                "total_estimated_usd": total_cost
            }
        }

        return redact_secrets(bundle)
