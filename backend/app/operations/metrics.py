"""Phase 10H: Operational Metrics Engine with Monotonic Percentile Analytics.

Tracks counters, gauges, and computes bounded P50, P95, and P99 latency distributions.
"""

import math
import time
import threading
from typing import Dict, List, Any


class OperationalMetricsEngine:
    """Thread-safe operational telemetry collector for production monitoring."""

    def __init__(self):
        self._lock = threading.Lock()
        self.counters: Dict[str, int] = {
            "http_requests_total": 0,
            "http_errors_total": 0,
            "websocket_connections_total": 0,
            "websocket_disconnects_total": 0,
            "reconnect_attempts_total": 0,
            "interviews_started_total": 0,
            "interviews_completed_total": 0,
            "interviews_failed_total": 0,
            "llm_calls_total": 0,
            "llm_failures_total": 0,
            "stt_calls_total": 0,
            "tts_calls_total": 0,
            "background_jobs_total": 0,
            "background_job_failures_total": 0,
            "rate_limit_events_total": 0,
            "security_events_total": 0
        }
        self.gauges: Dict[str, float] = {
            "active_interviews": 0.0,
            "active_websocket_connections": 0.0,
            "queue_depth": 0.0
        }
        self._timings: Dict[str, List[float]] = {
            "http_latency": [],
            "llm_latency": [],
            "stt_latency": [],
            "tts_latency": [],
            "db_latency": [],
            "redis_latency": [],
            "storage_latency": []
        }

    def increment_counter(self, name: str, value: int = 1) -> None:
        """Increments a monotonic counter."""
        with self._lock:
            self.counters[name] = self.counters.get(name, 0) + value

    def set_gauge(self, name: str, value: float) -> None:
        """Sets a point-in-time gauge value."""
        with self._lock:
            self.gauges[name] = float(value)

    def record_timing(self, category: str, duration_ms: float) -> None:
        """Records a timing measurement with bounded memory eviction."""
        with self._lock:
            if category not in self._timings:
                self._timings[category] = []
            samples = self._timings[category]
            samples.append(round(duration_ms, 2))
            if len(samples) > 2000:
                del samples[:1000]

    def get_percentiles(self, category: str) -> Dict[str, float]:
        """Calculates P50, P95, and P99 percentiles."""
        with self._lock:
            samples = sorted(self._timings.get(category, []))

        if not samples:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}

        n = len(samples)
        def _pct(p: float) -> float:
            idx = max(0, min(n - 1, math.ceil((p / 100.0) * n) - 1))
            return samples[idx]

        return {
            "p50": _pct(50),
            "p95": _pct(95),
            "p99": _pct(99),
            "count": n
        }

    def export_metrics(self) -> Dict[str, Any]:
        """Exports complete operational metrics summary."""
        with self._lock:
            counters_copy = dict(self.counters)
            gauges_copy = dict(self.gauges)
            categories = list(self._timings.keys())

        return {
            "counters": counters_copy,
            "gauges": gauges_copy,
            "percentiles": {cat: self.get_percentiles(cat) for cat in categories},
            "timestamp": time.time()
        }


# Global operational metrics instance
op_metrics = OperationalMetricsEngine()
