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

# ---------------------------------------------------------------------------
# Speech-activity gate
#
# Whisper does not report "there was nothing to transcribe". Fed a recording
# that holds only room tone it emits a fluent, confident sentence -- measured
# here, eight seconds of -48 dBFS noise transcribed as "I'll see you next
# time." That string is not repetitive, so the silence-hallucination filter in
# app/voice/stt.py cannot catch it, and it was stored and scored as the
# candidate's own spoken answer.
#
# The previous guard only caught digitally perfect silence (peak < 1e-4), which
# a real microphone never produces. This one measures energy against the
# recording's *own* noise floor instead of an absolute loudness, so a quiet
# speaker is judged the same as a loud one: measured over Kokoro speech
# attenuated to -30 dBFS, 33-87% of frames still clear the threshold, while
# room tone clears 0%.
# ---------------------------------------------------------------------------
_FRAME_SAMPLES = 512                # 32 ms at 16 kHz
_SPEECH_FLOOR_MULTIPLE = 3.0        # how far above the clip's own noise floor
_SPEECH_ABS_FLOOR_RMS = 3e-4        # ~-70 dBFS; below this nothing is audible
_MIN_SPEECH_MS = 150.0              # shorter than the briefest real word
_MIN_ANALYSABLE_SECONDS = 0.4       # below this there is no floor to estimate

# Whisper decodes autoregressively up to 448 tokens per 30 s window. On a cough
# or a door slam it fills that budget with a repetition loop -- 48.3 s of CPU
# for five seconds of audio, all of it discarded afterwards as silence. Real
# speech runs about 3-4 tokens per second, so a budget of twelve tokens per
# second of audio is far above anything a candidate can say while still
# terminating a loop early: the same cough returns in 3.9 s, and transcripts of
# real answers up to 37 s long are byte-identical with and without the cap.
_MAX_TOKENS_PER_AUDIO_SECOND = 12
_MIN_TOKEN_BUDGET = 40
_WHISPER_WINDOW_SECONDS = 30        # matches chunk_length_s below


def measure_speech_activity_ms(audio_array: np.ndarray, sample_rate: int = 16000) -> Optional[float]:
    """Milliseconds of audio whose energy rises above the clip's own noise floor.

    Returns None when the clip is too short to estimate a floor from, in which
    case the caller must not draw any conclusion and should transcribe it.
    """
    if audio_array is None or len(audio_array) == 0:
        return 0.0
    if len(audio_array) / float(sample_rate) < _MIN_ANALYSABLE_SECONDS:
        return None

    usable = (len(audio_array) // _FRAME_SAMPLES) * _FRAME_SAMPLES
    frames = audio_array[:usable].astype(np.float64).reshape(-1, _FRAME_SAMPLES)
    frame_rms = np.sqrt((frames ** 2).mean(axis=1))

    noise_floor = float(np.percentile(frame_rms, 10))
    threshold = max(noise_floor * _SPEECH_FLOOR_MULTIPLE, _SPEECH_ABS_FLOOR_RMS)
    speech_frames = int((frame_rms > threshold).sum())
    return speech_frames * (_FRAME_SAMPLES / float(sample_rate)) * 1000.0


def whisper_token_budget(audio_seconds: float) -> int:
    """Per-window generation cap that bounds hallucination loops."""
    window = min(max(audio_seconds, 0.0), _WHISPER_WINDOW_SECONDS)
    return int(max(_MIN_TOKEN_BUDGET, min(448, _MAX_TOKENS_PER_AUDIO_SECOND * window)))


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
            generate_kwargs={
                "task": "transcribe",
                "language": "english",
                # Bounds a runaway repetition loop on non-speech audio without
                # truncating any real answer -- see _MAX_TOKENS_PER_AUDIO_SECOND.
                "max_new_tokens": whisper_token_budget(len(audio_array) / 16000.0),
            }
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
            
            # Reject audio that holds no speech before Whisper ever sees it.
            # This is both a correctness guard (Whisper invents a sentence for
            # pure noise) and the fast path: room tone is rejected in about a
            # millisecond instead of the 1.7 s a full decode of it costs.
            speech_ms = measure_speech_activity_ms(audio_array, 16000)
            if len(audio_array) == 0 or (speech_ms is not None and speech_ms < _MIN_SPEECH_MS):
                return {
                    "transcript": "",
                    "text": "",
                    "language": "en",
                    "confidence": 0.0,
                    "provider": "whisper_small",
                    "is_silent": True,
                    "speech_activity_ms": 0.0 if speech_ms is None else round(speech_ms, 1),
                }

            # Run transcription in thread
            result = await asyncio.to_thread(self._transcribe_sync, audio_array)
            return result
        except STTProviderError:
            raise
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}", exc_info=True)
            raise STTProviderError(f"Whisper transcription failed: {str(e)}", provider="whisper", raw_error=e)
