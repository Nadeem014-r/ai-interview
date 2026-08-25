"""Phase 10E: Strongly Typed Voice Experience Configuration.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceExperienceConfig:
    """Configuration for end-to-end voice interview turn execution and latency targets."""

    MAX_TURN_SECONDS: float = float(os.getenv("MAX_TURN_SECONDS", "120.0"))
    MAX_AUDIO_CHUNK_BYTES: int = int(os.getenv("MAX_AUDIO_CHUNK_BYTES", str(64 * 1024)))
    MAX_TURN_AUDIO_BYTES: int = int(os.getenv("MAX_TURN_AUDIO_BYTES", str(10 * 1024 * 1024)))  # 10 MB
    SILENCE_MIN_CHAR_COUNT: int = int(os.getenv("SILENCE_MIN_CHAR_COUNT", "2"))

    # Latency Target Thresholds (in milliseconds)
    STT_TARGET_LATENCY_MS: float = float(os.getenv("STT_TARGET_LATENCY_MS", "1500.0"))
    INTERVIEW_TARGET_LATENCY_MS: float = float(os.getenv("INTERVIEW_TARGET_LATENCY_MS", "2000.0"))
    TTS_TARGET_LATENCY_MS: float = float(os.getenv("TTS_TARGET_LATENCY_MS", "1500.0"))
    TOTAL_TURN_TARGET_LATENCY_MS: float = float(os.getenv("TOTAL_TURN_TARGET_LATENCY_MS", "5000.0"))

    # Operational Features
    ENABLE_BARGE_IN: bool = os.getenv("ENABLE_BARGE_IN", "true").lower() in ("true", "1", "yes")
    ENABLE_AUTO_CLEANUP: bool = os.getenv("ENABLE_AUTO_CLEANUP", "true").lower() in ("true", "1", "yes")

    @classmethod
    def from_env(cls) -> "VoiceExperienceConfig":
        return cls()


experience_config = VoiceExperienceConfig.from_env()
