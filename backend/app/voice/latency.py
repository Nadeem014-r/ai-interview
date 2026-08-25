"""Phase 10A: Monotonic Voice Latency Monitoring.

Provides high-precision, monotonic latency measurement for audio validation,
STT transcription, TTS synthesis, and end-to-end voice turns with clock injection for deterministic testing.
"""

import time
from typing import Callable, Optional, Dict, Any


class LatencyTracker:
    """Tracks latency across voice lifecycle stages using monotonic time."""

    def __init__(self, timer_fn: Optional[Callable[[], float]] = None):
        self._timer: Callable[[], float] = timer_fn or time.perf_counter
        self._start_time: float = self._timer()
        self._stage_starts: Dict[str, float] = {}
        self._stage_durations_ms: Dict[str, float] = {}

    def start_stage(self, stage_name: str) -> None:
        """Start tracking duration for a specific stage."""
        self._stage_starts[stage_name] = self._timer()

    def stop_stage(self, stage_name: str) -> float:
        """
        Stop tracking stage and record elapsed time in milliseconds.
        Returns elapsed duration in milliseconds.
        """
        start = self._stage_starts.get(stage_name, self._timer())
        duration_sec = self._timer() - start
        duration_ms = round(duration_sec * 1000.0, 2)
        self._stage_durations_ms[stage_name] = duration_ms
        return duration_ms

    def get_stage_latency_ms(self, stage_name: str) -> float:
        """Get recorded duration for stage in milliseconds (0.0 if not stopped)."""
        return self._stage_durations_ms.get(stage_name, 0.0)

    def get_total_latency_ms(self) -> float:
        """Get total elapsed time since tracker initialization in milliseconds."""
        total_sec = self._timer() - self._start_time
        return round(total_sec * 1000.0, 2)

    def to_dict(self) -> Dict[str, Any]:
        """Export all latency metrics."""
        return {
            "stages_ms": dict(self._stage_durations_ms),
            "total_ms": self.get_total_latency_ms()
        }
