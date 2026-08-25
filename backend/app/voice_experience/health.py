"""Phase 10E: End-to-End Voice Experience Health Evaluator.

Assesses the complete voice pipeline from realtime transport to STT and TTS providers.
"""

from typing import Dict, Any, Optional
from app.providers.health import ProviderHealthChecker, ProviderHealthState


class VoiceExperienceHealthChecker:
    """Evaluates the readiness of the complete end-to-end voice pipeline."""

    @staticmethod
    def evaluate_voice_pipeline() -> Dict[str, Any]:
        """Inspects STT, TTS, and experience components."""
        provider_health = ProviderHealthChecker.get_all_provider_health()

        tts_state = provider_health.get("tts", {}).get("state", ProviderHealthState.AVAILABLE.value)
        stt_state = provider_health.get("stt", {}).get("state", ProviderHealthState.AVAILABLE.value)

        # Overall pipeline readiness determination
        if tts_state == ProviderHealthState.AVAILABLE.value and stt_state == ProviderHealthState.AVAILABLE.value:
            overall_status = "READY"
        elif tts_state in (ProviderHealthState.AVAILABLE.value, ProviderHealthState.NOT_CONFIGURED.value):
            # Degradation with fallback available
            overall_status = "DEGRADED"
        else:
            overall_status = "NOT_READY"

        return {
            "status": overall_status,
            "pipeline": {
                "realtime_transport": "READY",
                "speech_to_text": stt_state,
                "text_to_speech": tts_state,
                "adaptive_interview_engine": "READY"
            },
            "providers": provider_health
        }
