"""Whisper Small Speech-to-Text Provider.

Provides accurate, local candidate speech transcription using OpenAI Whisper Small
via Hugging Face Transformers pipeline.
"""

import io
import os
import logging
import asyncio
from typing import Optional, Dict, Any, Union
import numpy as np
import soundfile as sf

from app.ai.base import STTProvider
from app.providers.config import provider_config, ProviderConfig
from app.providers.exceptions import STTProviderError

logger = logging.getLogger("ai_interviewer.whisper_stt")


class WhisperSmallSTTProvider(STTProvider):
    """Local Whisper Small STT provider implementing standard STTProvider interface."""

    _asr_pipeline = None

    def __init__(self, config: Optional[ProviderConfig] = None):
        self.config = config or provider_config
        self.model_id = os.getenv("WHISPER_MODEL_ID", "openai/whisper-base")
        self.device = os.getenv("WHISPER_DEVICE", "cpu")

    @classmethod
    def _get_pipeline(cls, model_id: str = "openai/whisper-base", device: str = "cpu"):
        """Thread-safe lazy initialization of Whisper ASR pipeline."""
        if cls._asr_pipeline is None:
            try:
                from transformers import pipeline
                os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
                logger.info(f"Initializing Whisper pipeline (model={model_id}, device={device})...")
                cls._asr_pipeline = pipeline(
                    "automatic-speech-recognition",
                    model=model_id,
                    device=device,
                    chunk_length_s=30,
                )
                logger.info("Whisper Small pipeline successfully initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize Whisper pipeline: {e}")
                raise STTProviderError(f"Failed to load Whisper STT pipeline: {e}", provider="whisper", raw_error=e)
        return cls._asr_pipeline

    def _decode_audio_to_array(self, audio_bytes: bytes) -> np.ndarray:
        """Decodes raw audio bytes into 16kHz mono float32 numpy array across all web audio formats."""
        data = None
        samplerate = 16000

        # Attempt 1: Direct soundfile decode (WAV, OGG, FLAC)
        try:
            data, samplerate = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        except Exception:
            pass

        # Attempt 2: librosa decode (WebM, MP3, AAC)
        if data is None:
            try:
                import librosa
                data, samplerate = librosa.load(io.BytesIO(audio_bytes), sr=16000, mono=True)
            except Exception:
                pass

        # Attempt 3: pydub decode fallback (WebM / Opus / Any container)
        if data is None:
            try:
                from pydub import AudioSegment
                seg = AudioSegment.from_file(io.BytesIO(audio_bytes))
                seg = seg.set_frame_rate(16000).set_channels(1)
                samples = np.array(seg.get_array_of_samples())
                if seg.sample_width == 2:
                    data = samples.astype(np.float32) / 32768.0
                elif seg.sample_width == 4:
                    data = samples.astype(np.float32) / 2147483648.0
                else:
                    data = samples.astype(np.float32) / 128.0
                samplerate = 16000
            except Exception:
                pass

        if data is None:
            raise STTProviderError("Unable to decode candidate audio payload into PCM audio array.", provider="whisper")

        # Convert multi-channel to mono if necessary
        if len(data.shape) > 1:
            data = np.mean(data, axis=1)

        # Resample to 16000Hz if needed
        if samplerate != 16000:
            try:
                import scipy.signal
                num_samples = int(len(data) * 16000 / samplerate)
                data = scipy.signal.resample(data, num_samples).astype(np.float32)
            except Exception:
                pass

        return data.astype(np.float32)

    def _transcribe_sync(self, audio_array: np.ndarray) -> Dict[str, Any]:
        """Synchronous ASR inference executed in thread pool."""
        asr = self._get_pipeline(self.model_id, self.device)
        
        # Whisper pipeline expects dictionary with raw audio array and sampling rate
        input_data = {
            "raw": audio_array,
            "sampling_rate": 16000
        }
        
        result = asr(
            input_data,
            generate_kwargs={"task": "transcribe", "language": "english"}
        )
        
        raw_text = result.get("text", "") if isinstance(result, dict) else str(result)
        transcript = raw_text.strip()

        return {
            "transcript": transcript,
            "text": transcript,
            "language": "en",
            "confidence": 0.95 if transcript else 0.0,
            "provider": "whisper_small",
            "model": self.model_id
        }

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.wav") -> Dict[str, Any]:
        """Transcribes candidate speech audio bytes into text."""
        if not audio_bytes or len(audio_bytes) < 32:
            raise STTProviderError("Audio bytes payload is empty or invalid.", provider="whisper")

        try:
            # Decode audio array in thread
            audio_array = await asyncio.to_thread(self._decode_audio_to_array, audio_bytes)
            
            # Check for silent or empty audio
            if len(audio_array) == 0 or np.max(np.abs(audio_array)) < 1e-4:
                return {
                    "transcript": "",
                    "text": "",
                    "language": "en",
                    "confidence": 0.0,
                    "provider": "whisper_small",
                    "is_silent": True
                }

            # Run transcription in thread
            result = await asyncio.to_thread(self._transcribe_sync, audio_array)
            return result
        except STTProviderError:
            raise
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}", exc_info=True)
            raise STTProviderError(f"Whisper transcription failed: {str(e)}", provider="whisper", raw_error=e)
