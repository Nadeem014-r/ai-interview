"""Phase 10E: Voice Turn Diagnostics & Monotonic Latency Classification.

Calculates stage-by-stage latencies, compares against configured targets,
and generates secret-safe structured turn telemetry.
"""

from typing import Dict, Any, Optional
from app._archive.voice_experience.config import experience_config, VoiceExperienceConfig
from app._archive.voice_experience.models import VoiceTurn, LatencyClassification


class VoiceDiagnostics:
    """Evaluates turn performance metrics and produces structured telemetry."""

    @staticmethod
    def classify_latency(latency_ms: float, target_ms: float) -> LatencyClassification:
        """Categorizes latency duration relative to operational targets."""
        if latency_ms <= (target_ms * 0.75):
            return LatencyClassification.FAST
        if latency_ms <= (target_ms * 1.25):
            return LatencyClassification.NORMAL
        if latency_ms <= (target_ms * 2.0):
            return LatencyClassification.SLOW
        return LatencyClassification.TIMEOUT

    @classmethod
    def generate_turn_diagnostics(
        cls,
        turn: VoiceTurn,
        session_id: str,
        correlation_id: Optional[str] = None,
        config: Optional[VoiceExperienceConfig] = None
    ) -> Dict[str, Any]:
        """Generates comprehensive turn telemetry without leaking secrets."""
        cfg = config or experience_config

        stt_ms = turn.get_stt_latency_ms()
        interview_ms = turn.get_interview_latency_ms()
        tts_ms = turn.get_tts_latency_ms()
        total_ms = turn.get_total_turn_latency_ms()

        return {
            "session_id": session_id,
            "turn_id": turn.turn_id,
            "turn_index": turn.turn_index,
            "correlation_id": correlation_id,
            "state": turn.state.value,
            "is_interrupted": turn.is_interrupted,
            "error": turn.error,
            "latencies_ms": {
                "stt": stt_ms,
                "interview": interview_ms,
                "tts": tts_ms,
                "total": total_ms
            },
            "classifications": {
                "stt": cls.classify_latency(stt_ms, cfg.STT_TARGET_LATENCY_MS).value,
                "interview": cls.classify_latency(interview_ms, cfg.INTERVIEW_TARGET_LATENCY_MS).value,
                "tts": cls.classify_latency(tts_ms, cfg.TTS_TARGET_LATENCY_MS).value,
                "total": cls.classify_latency(total_ms, cfg.TOTAL_TURN_TARGET_LATENCY_MS).value
            },
            "metadata": turn.metadata
        }
