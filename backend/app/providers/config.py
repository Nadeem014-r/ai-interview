"""Phase 10D: Strongly Typed AI Voice & Audio Provider Configuration.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ProviderConfig:
    """Strongly typed configuration for real voice and audio providers."""

    # ElevenLabs TTS Configuration
    ELEVENLABS_API_KEY: Optional[str] = os.getenv("ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel / Default
    ELEVENLABS_MODEL: str = os.getenv("ELEVENLABS_MODEL", "eleven_monolingual_v1")
    ELEVENLABS_TIMEOUT_SECONDS: float = float(os.getenv("ELEVENLABS_TIMEOUT_SECONDS", "15.0"))
    ELEVENLABS_OUTPUT_FORMAT: str = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128")
    ELEVENLABS_BASE_URL: str = os.getenv("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io/v1")

    # STT / Whisper Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_STT_MODEL: str = os.getenv("OPENAI_STT_MODEL", "whisper-1")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    STT_TIMEOUT_SECONDS: float = float(os.getenv("STT_TIMEOUT_SECONDS", "30.0"))

    # Provider Selection
    DEFAULT_TTS_PROVIDER: str = os.getenv("DEFAULT_TTS_PROVIDER", "elevenlabs").lower()
    DEFAULT_STT_PROVIDER: str = os.getenv("DEFAULT_STT_PROVIDER", "mock").lower()

    # Safety & Operational Bounds
    MAX_TTS_TEXT_CHARS: int = int(os.getenv("MAX_TTS_TEXT_CHARS", "4000"))
    MAX_STT_AUDIO_BYTES: int = int(os.getenv("MAX_STT_AUDIO_BYTES", str(25 * 1024 * 1024)))  # 25 MB
    MAX_RETRIES: int = int(os.getenv("PROVIDER_MAX_RETRIES", "2"))
    INITIAL_BACKOFF_SEC: float = float(os.getenv("PROVIDER_INITIAL_BACKOFF_SEC", "0.5"))

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        """Construct ProviderConfig from active environment."""
        return cls()


# Default provider config instance
provider_config = ProviderConfig.from_env()
