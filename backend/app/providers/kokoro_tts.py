"""Kokoro 0.9.4 Text-to-Speech Provider.

Provides high-fidelity, local neural TTS synthesis using Kokoro 0.9.4
and outputs standard RIFF/WAVE (24kHz PCM) audio bytes.
"""

import io
import os
import logging
import asyncio
from typing import Optional, Dict, Any, List
import numpy as np
import soundfile as sf
import torch

from app.ai.base import TTSProvider
from app.providers.config import provider_config, ProviderConfig
from app.providers.exceptions import TTSProviderError

logger = logging.getLogger("ai_interviewer.kokoro_tts")

# Voice alias mapping for Kokoro 0.9.4 voices
VOICE_MAP: Dict[str, str] = {
    "default": "af_heart",
    "female_1": "af_heart",
    "female_2": "af_bella",
    "female_3": "af_sarah",
    "male_1": "am_adam",
    "male_2": "am_michael",
    "en_us_male_senior": "am_adam",
    "en_us_female_senior": "af_heart",
    "senior_tech_lead": "am_adam",
    "vp_engineering": "af_heart",
    "executive_recruiter": "af_bella",
}


class KokoroTTSProvider(TTSProvider):
    """Local Kokoro 0.9.4 TTS provider implementing standard TTSProvider interface."""

    _pipeline = None
    _lock = asyncio.Lock()

    def __init__(self, config: Optional[ProviderConfig] = None):
        self.config = config or provider_config
        self.lang_code = os.getenv("KOKORO_LANG_CODE", "a")
        self.repo_id = os.getenv("KOKORO_REPO_ID", "hexgrad/Kokoro-82M")
        self.sample_rate = 24000

    @classmethod
    def _get_pipeline(cls, lang_code: str = "a", repo_id: str = "hexgrad/Kokoro-82M"):
        """Thread-safe lazy initialization of Kokoro KPipeline."""
        if cls._pipeline is None:
            try:
                from kokoro import KPipeline
                # Suppress unnecessary HF warnings
                os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
                logger.info(f"Initializing Kokoro KPipeline (lang_code={lang_code}, repo={repo_id})...")
                cls._pipeline = KPipeline(lang_code=lang_code, repo_id=repo_id)
                logger.info("Kokoro KPipeline successfully initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize Kokoro KPipeline: {e}")
                raise TTSProviderError(f"Failed to load Kokoro TTS pipeline: {e}", provider="kokoro", raw_error=e)
        return cls._pipeline

    def _resolve_voice(self, voice_id: Optional[str]) -> str:
        """Resolves requested voice ID or alias to a valid Kokoro voice name."""
        if not voice_id or voice_id.strip() == "":
            return "af_heart"
        vid = voice_id.strip().lower()
        if vid in VOICE_MAP:
            return VOICE_MAP[vid]
        # Check if already a valid Kokoro voice name pattern (e.g. af_*, am_*, bf_*, bm_*)
        if vid.startswith(("af_", "am_", "bf_", "bm_")):
            return vid
        return "af_heart"

    def _synthesize_sync(self, text: str, voice_name: str, speed: float = 1.0) -> bytes:
        """Synchronous synthesis executed in thread pool."""
        pipeline = self._get_pipeline(self.lang_code, self.repo_id)
        generator = pipeline(text, voice=voice_name, speed=speed)
        
        all_audio: List[np.ndarray] = []
        for _, _, audio in generator:
            if isinstance(audio, torch.Tensor):
                all_audio.append(audio.detach().cpu().numpy())
            elif isinstance(audio, np.ndarray):
                all_audio.append(audio)

        if not all_audio:
            raise TTSProviderError("Kokoro produced empty audio segments.", provider="kokoro")

        combined = np.concatenate(all_audio) if len(all_audio) > 1 else all_audio[0]

        # Convert to 16-bit PCM WAV bytes
        out_buf = io.BytesIO()
        sf.write(out_buf, combined, self.sample_rate, format="WAV", subtype="PCM_16")
        wav_bytes = out_buf.getvalue()

        if len(wav_bytes) < 44:
            raise TTSProviderError("Synthesized WAV header corrupted.", provider="kokoro")

        return wav_bytes

    async def synthesize_speech(self, text: str, voice_id: str = "default") -> bytes:
        """Synthesizes text into high quality WAV audio bytes."""
        if not text or not text.strip():
            raise TTSProviderError("Text cannot be empty for speech synthesis.", provider="kokoro")

        clean_text = text.strip()
        voice_name = self._resolve_voice(voice_id)

        try:
            # Run synthesis in a background thread to prevent blocking FastAPI event loop
            wav_bytes = await asyncio.to_thread(self._synthesize_sync, clean_text, voice_name, 1.0)
            return wav_bytes
        except TTSProviderError:
            raise
        except Exception as e:
            logger.error(f"Kokoro synthesis failed: {e}", exc_info=True)
            raise TTSProviderError(f"Kokoro synthesis failed: {str(e)}", provider="kokoro", raw_error=e)
