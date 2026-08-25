"""Phase 10D: AI Voice & Audio Provider Registry & Manager.

Provides dynamic provider selection, fallback resolution, and health diagnostics
without modifying earlier phase abstractions.
"""

from typing import Optional, Dict, Any

from app.ai.base import TTSProvider, STTProvider
from app.ai.mock_provider import MockTTSProvider, MockSTTProvider
from app.providers.config import provider_config, ProviderConfig
from app.providers.elevenlabs_tts import ElevenLabsTTSProvider
from app.providers.stt_adapter import RealSTTAdapter
from app.providers.fallback import FallbackTTSProvider, FallbackSTTProvider
from app.providers.health import ProviderHealthChecker


class ProviderManager:
    """Central registry and factory for Voice TTS and Audio STT providers."""

    def __init__(self, config: Optional[ProviderConfig] = None):
        self.config = config or provider_config

    def get_tts_provider(
        self,
        name: Optional[str] = None,
        enable_fallback: bool = True
    ) -> TTSProvider:
        """
        Returns configured or named TTS provider.
        If enable_fallback is True, wraps real provider in a fallback layer.
        """
        target_name = (name or self.config.DEFAULT_TTS_PROVIDER).lower()

        if target_name in ("elevenlabs", "eleven_labs"):
            primary = ElevenLabsTTSProvider(config=self.config)
            if enable_fallback:
                return FallbackTTSProvider(primary=primary, fallback=MockTTSProvider())
            return primary

        # Default / mock
        return MockTTSProvider()

    def get_stt_provider(
        self,
        name: Optional[str] = None,
        enable_fallback: bool = True
    ) -> STTProvider:
        """
        Returns configured or named STT provider.
        If enable_fallback is True, wraps real provider in a fallback layer.
        """
        target_name = (name or self.config.DEFAULT_STT_PROVIDER).lower()

        if target_name in ("whisper", "openai", "openai_whisper"):
            primary = RealSTTAdapter(config=self.config)
            if enable_fallback:
                return FallbackSTTProvider(primary=primary, fallback=MockSTTProvider())
            return primary

        # Default / mock
        return MockSTTProvider()

    def get_health_status(self) -> Dict[str, Any]:
        """Collects operational health diagnostics."""
        return ProviderHealthChecker.get_all_provider_health(self.config)


# Global provider manager instance
provider_manager = ProviderManager()
