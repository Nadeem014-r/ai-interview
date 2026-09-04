"""Phase 10G: Production Observability & Secret-Safe Telemetry Engine.

Calculates monotonic P50, P95, P99 latency percentiles and tracks error distributions with zero secret leaks.
"""

import math
import time
import threading
from typing import Dict, List, Any

from app._archive.ops.secrets import redact_secrets


class HardenedTelemetryEngine:
    """Thread-safe telemetry collector with bounded percentile computation."""

    def __init__(self):
        self._lock = threading.Lock()
        self.counters: Dict[str, int] = {
            "auth_failures": 0,
            "rate_limit_events": 0,
            "circuit_breaker_trips": 0,
            "dropped_messages": 0,
            "rejected_payloads": 0,
            "reconnect_events": 0,
            "job_failures": 0,
            "storage_failures": 0,
            "redis_failures": 0
        }
        self._latencies: Dict[str, List[float]] = {
            "request_latency": [],
            "llm_latency": [],
            "stt_latency": [],
            "tts_latency": [],
            "redis_latency": [],
            "storage_latency": []
        }

    def increment(self, counter: str, delta: int = 1) -> None:
        """Increments a counter safely."""
        with self._lock:
            self.counters[counter] = self.counters.get(counter, 0) + delta

    def record_latency(self, category: str, duration_ms: float) -> None:
        """Records a monotonic timing observation."""
        with self._lock:
            if category not in self._latencies:
                self._latencies[category] = []
            samples = self._latencies[category]
            samples.append(round(duration_ms, 2))
            if len(samples) > 2000:
                del samples[:1000]

    def get_percentiles(self, category: str) -> Dict[str, float]:
        """Computes exact P50, P95, and P99 percentiles."""
        with self._lock:
            samples = sorted(self._latencies.get(category, []))

        if not samples:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}

        n = len(samples)
        def _p(pct: float) -> float:
            idx = max(0, min(n - 1, math.ceil((pct / 100.0) * n) - 1))
            return samples[idx]

        return {
            "p50": _p(50),
            "p95": _p(95),
            "p99": _p(99),
            "count": n
        }

    def export_sanitized_snapshot(self) -> Dict[str, Any]:
        """Exports sanitized operational snapshot."""
        with self._lock:
            counters_copy = dict(self.counters)
            cats = list(self._latencies.keys())

        snapshot = {
            "counters": counters_copy,
            "latencies": {cat: self.get_percentiles(cat) for cat in cats},
            "timestamp": time.time()
        }
        return redact_secrets(snapshot)


hardened_telemetry = HardenedTelemetryEngine()
