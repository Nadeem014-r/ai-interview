"""Kokoro 0.9.4 Text-to-Speech Provider.

Provides high-fidelity, local neural TTS synthesis using Kokoro 0.9.4
and outputs standard RIFF/WAVE (24kHz PCM) audio bytes.
"""

import io
import os
import logging
import asyncio
import threading
import weakref
from typing import Optional, Dict, Any, List
import numpy as np
import soundfile as sf
import torch

from app.ai.base import TTSProvider
from app.providers.config import (
    provider_config,
    ProviderConfig,
    INTERVIEWER_VOICE_ID,
    TTS_MAX_CONCURRENCY,
)
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
    # A threading lock, not an asyncio one: _get_pipeline() runs inside the
    # worker thread that asyncio.to_thread() hands the synthesis to, where an
    # asyncio.Lock has no meaning. The previous asyncio.Lock was never acquired
    # at all, so the "thread-safe lazy initialization" below was not: a request
    # arriving while the startup pre-warm was still importing kokoro repeated
    # the whole ~60 s import instead of waiting on it.
    _lock = threading.Lock()
    _warm_lock = threading.Lock()
    # Keyed weakly by event loop so a finished loop's semaphore is collected.
    _sem_by_loop: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()
    # Set once the pipeline has produced audio at least once. Loading the model
    # is not the whole cold cost -- the first synthesis also pulls the voice
    # tensor and initialises the g2p frontend -- so readiness means "has spoken",
    # not "has imported".
    _warm = False

    def __init__(self, config: Optional[ProviderConfig] = None):
        self.config = config or provider_config
        self.lang_code = os.getenv("KOKORO_LANG_CODE", "a")
        self.repo_id = os.getenv("KOKORO_REPO_ID", "hexgrad/Kokoro-82M")
        self.sample_rate = 24000

    @classmethod
    def _get_pipeline(cls, lang_code: str = "a", repo_id: str = "hexgrad/Kokoro-82M"):
        """Thread-safe lazy initialization of Kokoro KPipeline."""
        if cls._pipeline is not None:
            return cls._pipeline
        with cls._lock:
            # Re-check under the lock: whoever held it may have finished the load.
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

    @classmethod
    def is_warm(cls) -> bool:
        return cls._warm

    @classmethod
    def _slots(cls) -> asyncio.Semaphore:
        """Bound on concurrent synthesis, created lazily per event loop.

        Synthesis is CPU-bound work handed to asyncio.to_thread, whose default
        executor allows ~20 threads. Nothing stopped twenty candidates starting
        twenty Kokoro jobs on the same cores at once, which does not just slow
        every one of them down proportionally -- it pushes them past the
        per-request synthesis timeout, and a timed-out line is a line the
        interviewer does not speak. Bounding the work keeps each synthesis at
        roughly its single-job speed and makes the queue wait explicit instead.

        Built per running loop, and never at import time, so a process that
        imports this module without an event loop (a test collector, a CLI)
        does not bind a semaphore to a loop that will never run.
        """
        loop = asyncio.get_running_loop()
        sem = cls._sem_by_loop.get(loop)
        if sem is None:
            sem = asyncio.Semaphore(TTS_MAX_CONCURRENCY)
            cls._sem_by_loop[loop] = sem
        return sem

    @classmethod
    def inference_slot(cls) -> asyncio.Semaphore:
        """One synthesis slot, used as `async with provider.inference_slot():`."""
        return cls._slots()

    async def ensure_ready(self) -> None:
        """Load the model and speak one throwaway line, once per process.

        Cold start measured ~67 s on CPU (60 s to import kokoro, 6 s to build
        the pipeline, the rest the first synthesis), which is far past any
        sensible per-request synthesis timeout. Callers await this *outside*
        their timeout window so the first question of an interview waits for a
        warm engine instead of timing out and being spoken by something else.
        Concurrent callers all wait on the same load rather than repeating it.
        """
        if type(self)._warm:
            return
        await asyncio.to_thread(self._warm_up_sync)

    def _warm_up_sync(self) -> None:
        cls = type(self)
        if cls._warm:
            return
        with cls._warm_lock:
            if cls._warm:
                return
            self._synthesize_sync("Ready.", self._resolve_voice(INTERVIEWER_VOICE_ID), 1.0)
            cls._warm = True
            logger.info("Kokoro TTS warm: first synthesis complete.")

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
            # A real synthesis warms the engine just as the pre-warm does, so a
            # request that beat the pre-warm does not leave it to run again.
            type(self)._warm = True
            return wav_bytes
        except TTSProviderError:
            raise
        except Exception as e:
            logger.error(f"Kokoro synthesis failed: {e}", exc_info=True)
            raise TTSProviderError(f"Kokoro synthesis failed: {str(e)}", provider="kokoro", raw_error=e)
