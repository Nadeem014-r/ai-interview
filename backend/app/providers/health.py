"""Phase 10D: AI Voice Provider Health Evaluator.

Assesses real and mock provider availability states without leaking API secrets.
"""

from enum import Enum
from typing import Dict, Any, Optional
from app.providers.config import provider_config, ProviderConfig


class ProviderHealthState(str, Enum):
    """Health availability status for an AI voice provider."""
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"


class ProviderHealthChecker:
    """Lightweight, non-intrusive health inspector."""

    @staticmethod
    def check_elevenlabs_health(config: Optional[ProviderConfig] = None) -> Dict[str, Any]:
        """Evaluates ElevenLabs TTS configuration status."""
        cfg = config or provider_config
        if not cfg.ELEVENLABS_API_KEY or not cfg.ELEVENLABS_API_KEY.strip():
            return {
                "provider": "elevenlabs",
                "state": ProviderHealthState.NOT_CONFIGURED.value,
                "details": "ELEVENLABS_API_KEY is not set."
            }

        return {
            "provider": "elevenlabs",
            "state": ProviderHealthState.AVAILABLE.value,
            "details": f"Configured with model '{cfg.ELEVENLABS_MODEL}' and voice '{cfg.ELEVENLABS_VOICE_ID}'."
        }

    @staticmethod
    def check_stt_health(config: Optional[ProviderConfig] = None) -> Dict[str, Any]:
        """Evaluates STT provider configuration status."""
        cfg = config or provider_config
        if cfg.DEFAULT_STT_PROVIDER == "mock":
            return {
                "provider": "mock_stt",
                "state": ProviderHealthState.AVAILABLE.value,
                "details": "Deterministic in-memory mock STT active."
            }

        if not cfg.OPENAI_API_KEY:
            return {
                "provider": "whisper_stt",
                "state": ProviderHealthState.NOT_CONFIGURED.value,
                "details": "OPENAI_API_KEY is not set for real STT."
            }

        return {
            "provider": "whisper_stt",
            "state": ProviderHealthState.AVAILABLE.value,
            "details": f"Configured with model '{cfg.OPENAI_STT_MODEL}'."
        }

    @classmethod
    def get_all_provider_health(cls, config: Optional[ProviderConfig] = None) -> Dict[str, Any]:
        """Collects health status of all voice and audio providers."""
        cfg = config or provider_config
        tts_h = cls.check_elevenlabs_health(cfg)
        stt_h = cls.check_stt_health(cfg)

        return {
            "tts": tts_h,
            "stt": stt_h,
            "default_tts_provider": cfg.DEFAULT_TTS_PROVIDER,
            "default_stt_provider": cfg.DEFAULT_STT_PROVIDER
        }
