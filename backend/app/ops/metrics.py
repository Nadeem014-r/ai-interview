"""Phase 10F: Production Operations Metrics & Monotonic Percentile Calculator.

Tracks operational counters, active sessions, and calculates exact P50, P95, P99 percentiles.
"""

import math
import threading
from typing import Dict, List, Any


class ProductionOpsMetrics:
    """Thread-safe operational telemetry collector."""

    def __init__(self):
        self._lock = threading.Lock()
        self.counters: Dict[str, int] = {
            "request_count": 0,
            "request_errors": 0,
            "websocket_connections": 0,
            "websocket_disconnects": 0,
            "active_sessions": 0,
            "realtime_errors": 0,
            "background_job_success": 0,
            "background_job_failure": 0
        }
        self._latencies: Dict[str, List[float]] = {
            "request_latency": [],
            "stt_latency": [],
            "tts_latency": [],
            "llm_latency": [],
            "database_latency": [],
            "redis_latency": []
        }

    def increment(self, counter: str, delta: int = 1) -> None:
        """Increments a counter."""
        with self._lock:
            if counter not in self.counters:
                self.counters[counter] = 0
            self.counters[counter] += delta

    def decrement(self, counter: str, delta: int = 1) -> None:
        """Decrements a counter."""
        with self._lock:
            if counter not in self.counters:
                self.counters[counter] = 0
            self.counters[counter] = max(0, self.counters[counter] - delta)

    def record_latency(self, category: str, duration_ms: float) -> None:
        """Records a monotonic latency measurement."""
        with self._lock:
            if category not in self._latencies:
                self._latencies[category] = []
            samples = self._latencies[category]
            samples.append(round(duration_ms, 2))
            if len(samples) > 2000:
                del samples[:1000]

    def get_percentiles(self, category: str) -> Dict[str, float]:
        """Calculates P50, P95, and P99 percentiles."""
        with self._lock:
            samples = sorted(self._latencies.get(category, []))

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

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """Exports complete operational metrics."""
        with self._lock:
            counters_copy = dict(self.counters)
            cats = list(self._latencies.keys())

        return {
            "counters": counters_copy,
            "latencies": {cat: self.get_percentiles(cat) for cat in cats}
        }


# Global metrics instance
ops_metrics = ProductionOpsMetrics()
