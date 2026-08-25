"""Phase 10B: Realtime Observability, Latency Metrics & Secret-Safe Logging.

Calculates monotonic P50, P95, P99 latency percentiles, tracks operational counters,
masks secrets in logs, and provides multi-tier health diagnostics.
"""

import time
import math
import logging
from typing import Dict, Any, List, Optional

from app.realtime.config import config
from app.realtime.redis_store import RedisStore
from app.realtime.storage import LocalStorage

logger = logging.getLogger("app.realtime")


class RealtimeMetrics:
    """Calculates monotonic latency percentiles and operational metrics."""

    def __init__(self):
        self._latencies_ms: Dict[str, List[float]] = {
            "receive": [],
            "audio_buffer": [],
            "stt": [],
            "interview": [],
            "tts": [],
            "total_turn": []
        }
        self.counters: Dict[str, int] = {
            "connections_total": 0,
            "messages_received": 0,
            "audio_chunks_processed": 0,
            "audio_bytes_processed": 0,
            "reconnects_total": 0,
            "rate_limit_violations": 0,
            "errors_total": 0
        }

    def record_latency(self, stage: str, duration_ms: float) -> None:
        """Record a monotonic latency measurement in milliseconds."""
        if stage not in self._latencies_ms:
            self._latencies_ms[stage] = []
        samples = self._latencies_ms[stage]
        samples.append(round(duration_ms, 2))
        # Keep bounded window of recent samples
        if len(samples) > 2000:
            del samples[:1000]

    def increment(self, counter_name: str, delta: int = 1) -> None:
        """Increment a metric counter."""
        if counter_name in self.counters:
            self.counters[counter_name] += delta

    def get_percentiles(self, stage: str) -> Dict[str, float]:
        """Calculate P50, P95, P99 for the specified stage."""
        samples = sorted(self._latencies_ms.get(stage, []))
        if not samples:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}

        n = len(samples)
        def _percentile(p: float) -> float:
            idx = max(0, min(n - 1, math.ceil((p / 100.0) * n) - 1))
            return samples[idx]

        return {
            "p50": _percentile(50),
            "p95": _percentile(95),
            "p99": _percentile(99),
            "count": n
        }

    def get_summary(self) -> Dict[str, Any]:
        """Export all operational counters and latency percentiles."""
        return {
            "counters": dict(self.counters),
            "latencies": {stage: self.get_percentiles(stage) for stage in self._latencies_ms}
        }


class RealtimeLogger:
    """Secret-safe structured logging."""

    @staticmethod
    def mask_sensitive_data(message: str) -> str:
        """Mask credentials, tokens, and authorization headers from logs."""
        from app.voice.security import VoiceSecurity
        return VoiceSecurity.mask_secrets(message)

    @staticmethod
    def log_event(
        event_name: str,
        session_id: Optional[str] = None,
        connection_id: Optional[str] = None,
        latency_ms: Optional[float] = None,
        level: str = "info",
        **kwargs
    ) -> None:
        clean_kwargs = {}
        for k, v in kwargs.items():
            if k.lower() in ("token", "jwt", "password", "audio_bytes", "secret", "raw_audio"):
                clean_kwargs[k] = "[REDACTED]"
            else:
                clean_kwargs[k] = RealtimeLogger.mask_sensitive_data(str(v))

        payload = {
            "timestamp": time.time(),
            "event": event_name,
            "session_id": session_id,
            "connection_id": connection_id,
            "latency_ms": latency_ms,
            **clean_kwargs
        }
        if level == "error":
            logger.error(str(payload))
        else:
            logger.info(str(payload))


class RealtimeHealthChecker:
    """Health and readiness diagnostic checks for realtime dependencies."""

    @staticmethod
    async def check_health(store: Optional[RedisStore] = None, storage: Optional[LocalStorage] = None) -> Dict[str, Any]:
        """
        Check health of realtime subsystems:
        - 'healthy': all operational
        - 'degraded': running with in-memory fallback
        - 'unavailable': fatal failure
        """
        store_status = "healthy"
        if store is not None:
            try:
                # Test store
                test_key = "health:ping"
                await store.set(test_key, "pong", ttl_seconds=5)
                val = await store.get(test_key)
                if val != "pong":
                    store_status = "degraded"
            except Exception:
                store_status = "degraded"

        storage_status = "healthy"
        if storage is not None:
            try:
                if not storage.base_path.exists():
                    storage_status = "degraded"
            except Exception:
                storage_status = "degraded"

        overall = "healthy"
        if store_status == "degraded" or storage_status == "degraded":
            overall = "degraded"

        return {
            "status": overall,
            "components": {
                "redis_or_memory_store": store_status,
                "object_storage": storage_status,
                "websocket_subsystem": "healthy"
            }
        }


# Global metrics instance
metrics = RealtimeMetrics()
