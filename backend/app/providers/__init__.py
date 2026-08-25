"""Phase 10D: AI Voice & Audio Providers Module Exports.
"""

from app.providers.config import ProviderConfig, provider_config
from app.providers.exceptions import (
    ProviderError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderNetworkError,
    ProviderUnavailableError,
    ProviderResponseError,
    ProviderValidationError,
    ProviderFallbackError,
)
from app.providers.validation import ProviderValidator
from app.providers.usage import UsageTracker, usage_tracker, UsageRecord
from app.providers.health import ProviderHealthChecker, ProviderHealthState
from app.providers.elevenlabs_tts import ElevenLabsTTSProvider
from app.providers.stt_adapter import RealSTTAdapter
from app.providers.fallback import FallbackTTSProvider, FallbackSTTProvider
from app.providers.provider_manager import ProviderManager, provider_manager

__all__ = [
    "ProviderConfig",
    "provider_config",
    "ProviderError",
    "ProviderAuthenticationError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "ProviderNetworkError",
    "ProviderUnavailableError",
    "ProviderResponseError",
    "ProviderValidationError",
    "ProviderFallbackError",
    "ProviderValidator",
    "UsageTracker",
    "usage_tracker",
    "UsageRecord",
    "ProviderHealthChecker",
    "ProviderHealthState",
    "ElevenLabsTTSProvider",
    "RealSTTAdapter",
    "FallbackTTSProvider",
    "FallbackSTTProvider",
    "ProviderManager",
    "provider_manager",
]
