"""Phase 10H: Operational Health & Anomaly Monitoring Loop.

Evaluates metric streams against operational thresholds and triggers deduplicated alerts.
"""

from typing import Dict, Any, List
from app.operations.metrics import op_metrics, OperationalMetricsEngine
from app.operations.alerts import alert_engine, AlertEngine, AlertSeverity


class OperationalMonitor:
    """Monitors live metric counters and timings to surface actionable alarms."""

    def __init__(
        self,
        metrics_engine: OperationalMetricsEngine = op_metrics,
        engine_alerts: AlertEngine = alert_engine,
        error_rate_threshold: float = 0.05,
        p95_latency_threshold_ms: float = 3000.0
    ):
        self.metrics = metrics_engine
        self.alerts = engine_alerts
        self.error_rate_threshold = error_rate_threshold
        self.p95_latency_threshold_ms = p95_latency_threshold_ms

    def evaluate_system_state(self) -> List[Dict[str, Any]]:
        """Scans metrics and fires alerts for anomalies."""
        triggered = []
        snap = self.metrics.export_metrics()
        counters = snap.get("counters", {})
        percentiles = snap.get("percentiles", {})

        # 1. Error Rate Check
        reqs = counters.get("http_requests_total", 0)
        errs = counters.get("http_errors_total", 0)
        if reqs >= 20:
            rate = errs / float(reqs)
            if rate >= self.error_rate_threshold:
                al = self.alerts.trigger_alert(
                    alert_code="HIGH_ERROR_RATE",
                    severity=AlertSeverity.ERROR,
                    message=f"HTTP error rate is {rate:.1%}, exceeding threshold {self.error_rate_threshold:.1%}",
                    observed_value=round(rate, 4),
                    threshold_value=self.error_rate_threshold,
                    component="http_gateway"
                )
                if al:
                    triggered.append({"alert": al.alert_code, "severity": al.severity.value})

        # 2. P95 HTTP Latency Check
        http_p95 = percentiles.get("http_latency", {}).get("p95", 0.0)
        if http_p95 >= self.p95_latency_threshold_ms:
            al = self.alerts.trigger_alert(
                alert_code="HIGH_LATENCY",
                severity=AlertSeverity.WARNING,
                message=f"P95 HTTP latency is {http_p95}ms, exceeding threshold {self.p95_latency_threshold_ms}ms",
                observed_value=http_p95,
                threshold_value=self.p95_latency_threshold_ms,
                component="http_gateway"
            )
            if al:
                triggered.append({"alert": al.alert_code, "severity": al.severity.value})

        return triggered
