"""Phase 10C: Production Metrics & Monotonic Latency Calculations.

Computes P50, P95, P99 percentile distributions and tracks system telemetry.
"""

import time
import math
from typing import Dict, List, Any


class ProductionMetrics:
    """Telemetry collector and latency percentile calculator."""

    def __init__(self):
        self._latencies: Dict[str, List[float]] = {
            "http_request": [],
            "background_job": [],
            "storage_io": [],
            "database_query": [],
            "total_turn": []
        }
        self.counters: Dict[str, int] = {
            "requests_total": 0,
            "jobs_enqueued": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "storage_uploads": 0,
            "storage_deletions": 0,
            "errors_total": 0
        }

    def record_latency(self, category: str, duration_ms: float) -> None:
        """Record a monotonic latency sample in milliseconds."""
        if category not in self._latencies:
            self._latencies[category] = []
        samples = self._latencies[category]
        samples.append(round(duration_ms, 2))
        # Keep bounded recent samples window
        if len(samples) > 2000:
            del samples[:1000]

    def increment(self, counter: str, delta: int = 1) -> None:
        """Increment a telemetry counter."""
        if counter in self.counters:
            self.counters[counter] += delta

    def get_percentiles(self, category: str) -> Dict[str, float]:
        """Compute P50, P95, and P99 percentiles."""
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

    def get_summary(self) -> Dict[str, Any]:
        """Export snapshot of operational metrics."""
        return {
            "counters": dict(self.counters),
            "latencies": {cat: self.get_percentiles(cat) for cat in self._latencies}
        }


# Global metrics instance
production_metrics = ProductionMetrics()
