"""Phase 10D: Strongly Typed AI Voice & Audio Provider Configuration.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Robust project-relative .env loading
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)
else:
    load_dotenv(override=False)


@dataclass(frozen=True)
class ProviderConfig:
    """Strongly typed configuration for real voice and audio providers."""

    # ElevenLabs TTS Configuration
    ELEVENLABS_API_KEY: Optional[str] = os.getenv("ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "hqBknhU0QebV576rq8S9")
    ELEVENLABS_MODEL: str = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")
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

    # Phase 5: Real-time Voice & Turn-taking Configuration
    VOICE_SILENCE_TIMEOUT_SEC: float = float(os.getenv("VOICE_SILENCE_TIMEOUT", "2.8"))
    VOICE_MIN_SPEECH_DURATION_SEC: float = float(os.getenv("VOICE_MIN_SPEECH_DURATION", "1.0"))
    VOICE_MAX_RESPONSE_DURATION_SEC: float = float(os.getenv("VOICE_MAX_RESPONSE_DURATION", "120.0"))
    VOICE_BARGE_IN_ENABLED: bool = os.getenv("VOICE_BARGE_IN_ENABLED", "true").lower() in ("true", "1", "yes")

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        """Construct ProviderConfig from active environment."""
        return cls(
            ELEVENLABS_API_KEY=os.getenv("ELEVENLABS_API_KEY"),
            ELEVENLABS_VOICE_ID=os.getenv("ELEVENLABS_VOICE_ID", "hqBknhU0QebV576rq8S9"),
            ELEVENLABS_MODEL=os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5"),
            VOICE_SILENCE_TIMEOUT_SEC=float(os.getenv("VOICE_SILENCE_TIMEOUT", "2.8")),
            VOICE_MIN_SPEECH_DURATION_SEC=float(os.getenv("VOICE_MIN_SPEECH_DURATION", "1.0")),
            VOICE_MAX_RESPONSE_DURATION_SEC=float(os.getenv("VOICE_MAX_RESPONSE_DURATION", "120.0")),
            VOICE_BARGE_IN_ENABLED=os.getenv("VOICE_BARGE_IN_ENABLED", "true").lower() in ("true", "1", "yes"),
        )


# Default provider config instance
provider_config = ProviderConfig.from_env()

