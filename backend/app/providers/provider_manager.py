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


from app.core.config import settings
from app.providers.kokoro_tts import KokoroTTSProvider
from app.providers.whisper_stt import WhisperSmallSTTProvider


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
        target_name = (name or getattr(settings, "DEFAULT_TTS_PROVIDER", None) or self.config.DEFAULT_TTS_PROVIDER).lower()

        if target_name in ("mock", "mock_tts", "mock_provider"):
            return MockTTSProvider()
        elif target_name in ("kokoro", "kokoro_tts", "local_kokoro"):
            primary = KokoroTTSProvider(config=self.config)
            if enable_fallback:
                return FallbackTTSProvider(primary=primary, fallback=MockTTSProvider())
            return primary
        elif target_name in ("elevenlabs", "eleven_labs"):
            primary = ElevenLabsTTSProvider(config=self.config)
            if enable_fallback:
                return FallbackTTSProvider(primary=primary, fallback=MockTTSProvider())
            return primary

        # Default / fallback to Kokoro then mock
        primary = KokoroTTSProvider(config=self.config)
        if enable_fallback:
            return FallbackTTSProvider(primary=primary, fallback=MockTTSProvider())
        return primary

    def get_stt_provider(
        self,
        name: Optional[str] = None,
        enable_fallback: bool = True
    ) -> STTProvider:
        """
        Returns configured or named STT provider.
        If enable_fallback is True, wraps real provider in a fallback layer.
        """
        target_name = (name or getattr(settings, "DEFAULT_STT_PROVIDER", None) or self.config.DEFAULT_STT_PROVIDER).lower()

        if target_name in ("mock", "mock_stt", "mock_provider"):
            return MockSTTProvider()
        elif target_name in ("whisper", "whisper_small", "whisper_stt", "local_whisper"):
            primary = WhisperSmallSTTProvider(config=self.config)
            if enable_fallback:
                return FallbackSTTProvider(primary=primary, fallback=MockSTTProvider())
            return primary
        elif target_name in ("openai", "openai_whisper", "real_stt"):
            primary = RealSTTAdapter(config=self.config)
            if enable_fallback:
                return FallbackSTTProvider(primary=primary, fallback=MockSTTProvider())
            return primary

        # Default to Whisper Small
        primary = WhisperSmallSTTProvider(config=self.config)
        if enable_fallback:
            return FallbackSTTProvider(primary=primary, fallback=MockSTTProvider())
        return primary

    def get_health_status(self) -> Dict[str, Any]:
        """Collects operational health diagnostics."""
        return ProviderHealthChecker.get_all_provider_health(self.config)


# Global provider manager instance
provider_manager = ProviderManager()
