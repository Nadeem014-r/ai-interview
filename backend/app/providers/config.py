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


# The one voice the interviewer speaks with, for the whole of every session.
#
# Callers name this explicitly rather than sending "default" and trusting it to
# resolve here, so the session's voice is a stated choice visible in the request
# and the logs instead of a fallback that drifts if a mapping changes. It lives
# in this module, not in the Kokoro provider, so naming the voice does not drag
# torch into the import graph of every module that needs the name.
INTERVIEWER_VOICE_ID = os.getenv("INTERVIEWER_VOICE_ID", "en_us_female_senior")

# How many Kokoro / Whisper jobs may run at once.
#
# Both are CPU-bound and are dispatched with asyncio.to_thread, whose default
# executor permits roughly cpu_count+4 threads -- so N simultaneous candidates
# previously started N inference jobs on the same cores. That does not degrade
# gracefully: each job gets slower in proportion, and past a point every one of
# them exceeds its request timeout, turning a busy minute into a minute of
# failed transcriptions and unspoken questions.
#
# Small numbers on purpose. torch already parallelises a single job across
# cores, so the throughput gain from a second concurrent job is modest while
# the latency cost to both is not. The bounds are separate per engine so a
# queue of TTS work cannot delay transcription, or the reverse.
def _positive_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


TTS_MAX_CONCURRENCY = _positive_int("TTS_MAX_CONCURRENCY", 2)
STT_MAX_CONCURRENCY = _positive_int("STT_MAX_CONCURRENCY", 2)


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

    # Provider Selection (Defaulting to Kokoro 0.9.4 TTS and Whisper Small STT)
    DEFAULT_TTS_PROVIDER: str = os.getenv("DEFAULT_TTS_PROVIDER", "kokoro").lower()
    DEFAULT_STT_PROVIDER: str = os.getenv("DEFAULT_STT_PROVIDER", "whisper").lower()

    # Kokoro TTS Configuration
    KOKORO_LANG_CODE: str = os.getenv("KOKORO_LANG_CODE", "a")
    KOKORO_REPO_ID: str = os.getenv("KOKORO_REPO_ID", "hexgrad/Kokoro-82M")

    # Whisper STT Configuration
    WHISPER_MODEL_ID: str = os.getenv("WHISPER_MODEL_ID", "openai/whisper-small")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")

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
            DEFAULT_TTS_PROVIDER=os.getenv("DEFAULT_TTS_PROVIDER", "kokoro").lower(),
            DEFAULT_STT_PROVIDER=os.getenv("DEFAULT_STT_PROVIDER", "whisper").lower(),
            KOKORO_LANG_CODE=os.getenv("KOKORO_LANG_CODE", "a"),
            KOKORO_REPO_ID=os.getenv("KOKORO_REPO_ID", "hexgrad/Kokoro-82M"),
            WHISPER_MODEL_ID=os.getenv("WHISPER_MODEL_ID", "openai/whisper-small"),
            WHISPER_DEVICE=os.getenv("WHISPER_DEVICE", "cpu"),
            VOICE_SILENCE_TIMEOUT_SEC=float(os.getenv("VOICE_SILENCE_TIMEOUT", "2.8")),
            VOICE_MIN_SPEECH_DURATION_SEC=float(os.getenv("VOICE_MIN_SPEECH_DURATION", "1.0")),
            VOICE_MAX_RESPONSE_DURATION_SEC=float(os.getenv("VOICE_MAX_RESPONSE_DURATION", "120.0")),
            VOICE_BARGE_IN_ENABLED=os.getenv("VOICE_BARGE_IN_ENABLED", "true").lower() in ("true", "1", "yes"),
        )


# Default provider config instance
provider_config = ProviderConfig.from_env()

