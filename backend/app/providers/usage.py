"""Phase 10D: AI Voice & Audio Usage, Telemetry & Cost Tracking Hooks.

Records provider operations, input/output volumes, monotonic latencies, and success/failure distributions.
"""

import time
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class UsageRecord:
    """Telemetry record for a single provider invocation."""
    provider: str
    operation: str  # "tts" or "stt"
    model: str
    voice: Optional[str] = None
    characters: int = 0
    audio_bytes: int = 0
    latency_ms: float = 0.0
    success: bool = True
    error_type: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class UsageTracker:
    """Thread-safe usage metrics aggregator."""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: List[UsageRecord] = []
        self._totals: Dict[str, Dict[str, Any]] = {
            "elevenlabs": {"requests": 0, "characters": 0, "audio_bytes": 0, "errors": 0},
            "whisper": {"requests": 0, "characters": 0, "audio_bytes": 0, "errors": 0},
            "mock": {"requests": 0, "characters": 0, "audio_bytes": 0, "errors": 0},
        }

    def record_usage(
        self,
        provider: str,
        operation: str,
        model: str,
        voice: Optional[str] = None,
        characters: int = 0,
        audio_bytes: int = 0,
        latency_ms: float = 0.0,
        success: bool = True,
        error_type: Optional[str] = None
    ) -> None:
        """Records a provider usage event."""
        rec = UsageRecord(
            provider=provider,
            operation=operation,
            model=model,
            voice=voice,
            characters=characters,
            audio_bytes=audio_bytes,
            latency_ms=round(latency_ms, 2),
            success=success,
            error_type=error_type
        )
        with self._lock:
            self._records.append(rec)
            # Bound in-memory records
            if len(self._records) > 2000:
                del self._records[:1000]

            prov_key = provider.lower()
            if prov_key not in self._totals:
                self._totals[prov_key] = {"requests": 0, "characters": 0, "audio_bytes": 0, "errors": 0}

            self._totals[prov_key]["requests"] += 1
            self._totals[prov_key]["characters"] += characters
            self._totals[prov_key]["audio_bytes"] += audio_bytes
            if not success:
                self._totals[prov_key]["errors"] += 1

    def get_summary(self) -> Dict[str, Any]:
        """Returns aggregate usage statistics."""
        with self._lock:
            return {
                "totals": {k: dict(v) for k, v in self._totals.items()},
                "recent_record_count": len(self._records)
            }


# Global usage tracker instance
usage_tracker = UsageTracker()
