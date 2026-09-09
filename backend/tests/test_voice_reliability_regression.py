"""Regression tests for the voice reliability fixes.

Three defects are pinned here:

1. Whisper invents a fluent sentence for audio that holds no speech. Eight
   seconds of room tone transcribed as a complete sentence, which is not
   repetitive and so slipped past the silence-hallucination filter in
   app/voice/stt.py -- it was stored and scored as the candidate's own answer.
2. Fed a cough, Whisper spent its full 448-token budget on a repetition loop:
   48.3 s of CPU for five seconds of audio, all of it thrown away afterwards.
3. A line long enough to need more than 30 s of synthesis timed out, the
   endpoint answered 503 and the browser spoke that one question in its own
   voice -- so the interviewer changed person mid-session and changed back.

Every test here is local: no model is loaded and no provider is called.
"""

import numpy as np
import pytest

from app.providers.whisper_stt import (
    WhisperSmallSTTProvider,
    measure_speech_activity_ms,
    whisper_token_budget,
    _MIN_SPEECH_MS,
)
from app.voice.tts import (
    TextToSpeechService,
    timeout_for_text,
    _TTS_MIN_TIMEOUT_SECONDS,
    _TTS_MAX_TIMEOUT_SECONDS,
)


SR = 16000


def _room_tone(seconds: float, amplitude: float = 0.004, seed: int = 7) -> np.ndarray:
    """Steady background hiss at roughly -48 dBFS, as a quiet room records."""
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(int(seconds * SR)) * amplitude).astype(np.float32)


def _speech_like(seconds: float, amplitude: float = 0.3, seed: int = 3) -> np.ndarray:
    """Syllable-rate amplitude modulation over a quiet floor.

    Not real speech, but it carries the property the detector actually tests:
    energy that rises well above the recording's own noise floor and stays
    there for hundreds of milliseconds at a time.
    """
    n = int(seconds * SR)
    rng = np.random.default_rng(seed)
    carrier = rng.standard_normal(n).astype(np.float32)
    t = np.arange(n) / SR
    envelope = (0.5 + 0.5 * np.sin(2 * np.pi * 4.0 * t)).astype(np.float32) ** 2
    return (carrier * envelope * amplitude + _room_tone(seconds, 0.002, seed + 1)).astype(np.float32)


# -- 1. Speech-activity detection --------------------------------------------

def test_room_tone_carries_no_speech_activity():
    assert measure_speech_activity_ms(_room_tone(8.0)) < _MIN_SPEECH_MS


def test_digital_silence_carries_no_speech_activity():
    assert measure_speech_activity_ms(np.zeros(SR * 5, dtype=np.float32)) < _MIN_SPEECH_MS


def test_loud_steady_noise_is_still_not_speech():
    """Loudness alone must not read as speech: the floor is measured per clip."""
    assert measure_speech_activity_ms(_room_tone(8.0, amplitude=0.05, seed=21)) < _MIN_SPEECH_MS


def test_speech_is_detected():
    assert measure_speech_activity_ms(_speech_like(4.0)) >= _MIN_SPEECH_MS


def test_quiet_speech_is_detected():
    """A softly spoken answer is judged against its own floor, not an absolute
    loudness, so a quiet candidate is not silently discarded."""
    quiet = (_speech_like(4.0) * 0.03).astype(np.float32)
    assert float(np.max(np.abs(quiet))) < 0.05  # ~-26 dBFS: a soft speaker
    assert measure_speech_activity_ms(quiet) >= _MIN_SPEECH_MS


def test_brief_answer_is_detected():
    """Real answers can be one word. 600 ms of speech must survive."""
    assert measure_speech_activity_ms(_speech_like(0.6)) >= _MIN_SPEECH_MS


def test_clip_too_short_to_judge_returns_none():
    """Below the analysis window there is no noise floor to compare against,
    so the detector reports "no opinion" rather than rejecting the audio."""
    assert measure_speech_activity_ms(np.zeros(int(0.2 * SR), dtype=np.float32)) is None


# -- 2. The gate is wired into the provider ----------------------------------

@pytest.mark.asyncio
async def test_room_tone_never_reaches_the_model(monkeypatch):
    """The fabricated-transcript bug: room tone must be rejected before Whisper
    ever decodes it, so there is nothing for it to hallucinate from."""
    provider = WhisperSmallSTTProvider()

    def _explode(*_args, **_kwargs):
        raise AssertionError("Whisper was invoked on audio that holds no speech.")

    monkeypatch.setattr(provider, "_decode_audio_to_array", lambda _b: _room_tone(8.0))
    monkeypatch.setattr(provider, "_transcribe_sync", _explode)

    result = await provider.transcribe_audio(b"\x00" * 4096, filename="answer_turn.wav")

    assert result["is_silent"] is True
    assert result["text"] == ""
    assert result["transcript"] == ""


@pytest.mark.asyncio
async def test_speech_still_reaches_the_model(monkeypatch):
    provider = WhisperSmallSTTProvider()
    seen = {}

    def _fake_transcribe(audio_array):
        seen["samples"] = len(audio_array)
        return {
            "transcript": "Because it hashes to a bucket.",
            "text": "Because it hashes to a bucket.",
            "language": "en",
            "confidence": 0.95,
            "provider": "whisper_small",
        }

    monkeypatch.setattr(provider, "_decode_audio_to_array", lambda _b: _speech_like(3.0))
    monkeypatch.setattr(provider, "_transcribe_sync", _fake_transcribe)

    result = await provider.transcribe_audio(b"\x00" * 4096, filename="answer_turn.wav")

    assert seen["samples"] > 0
    assert result["text"] == "Because it hashes to a bucket."
    assert not result.get("is_silent")


# -- 3. Bounded decoding -----------------------------------------------------

def test_token_budget_is_generous_for_real_speech():
    """Natural speech runs about 3-4 tokens per second. The budget must sit far
    above that at every duration, so no real answer is ever truncated."""
    for seconds, spoken_tokens in [(2.0, 8), (10.0, 40), (30.0, 120), (120.0, 120)]:
        assert whisper_token_budget(seconds) >= spoken_tokens * 2


def test_token_budget_bounds_a_runaway_loop():
    """Five seconds of coughing used to decode 448 tokens of repetition."""
    assert whisper_token_budget(5.0) < 448
    assert whisper_token_budget(0.5) >= 40


def test_token_budget_never_exceeds_the_model_limit():
    """The budget is per 30 s window, so a long answer is chunked, not cut."""
    assert whisper_token_budget(600.0) <= 448


def test_decode_is_capped_per_call(monkeypatch):
    captured = {}

    class _FakePipeline:
        def __call__(self, _inputs, generate_kwargs=None):
            captured.update(generate_kwargs or {})
            return {"text": " a short answer "}

    monkeypatch.setattr(
        WhisperSmallSTTProvider,
        "_get_pipeline",
        classmethod(lambda cls, *a, **k: _FakePipeline()),
    )

    provider = WhisperSmallSTTProvider()
    result = provider._transcribe_sync(_speech_like(5.0))

    assert captured["max_new_tokens"] == whisper_token_budget(5.0)
    assert captured["task"] == "transcribe"
    assert result["transcript"] == "a short answer"


# -- 4. One voice for the whole session --------------------------------------

def test_short_line_keeps_the_original_budget():
    assert timeout_for_text("Can you explain how a hash map works?") == _TTS_MIN_TIMEOUT_SECONDS


def test_long_line_gets_a_longer_budget():
    """A line this long needs more than 30 s of local synthesis. Timing out sent
    it to the browser voice, which is what made the interviewer change person."""
    long_line = "word " * 200
    assert timeout_for_text(long_line) > _TTS_MIN_TIMEOUT_SECONDS


def test_budget_is_bounded():
    assert timeout_for_text("x" * 100_000) == _TTS_MAX_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_derived_budget_is_applied(monkeypatch):
    class _FakeTTS:
        async def synthesize_speech(self, text, voice_id="default"):
            return b"RIFF" + b"\x00" * 128

    monkeypatch.setattr(
        "app.ai.factory.AIFactory.get_tts_provider", lambda *a, **k: _FakeTTS()
    )

    long_line = "word " * 200
    _audio, meta = await TextToSpeechService.synthesize_with_metadata(long_line)
    assert meta["timeout_seconds"] == timeout_for_text(long_line)

    _audio, meta = await TextToSpeechService.synthesize_with_metadata(
        "Hello.", timeout_seconds=7.5
    )
    assert meta["timeout_seconds"] == 7.5
