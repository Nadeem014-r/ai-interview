"""One interview session speaks with one voice, from question one onward.

The reported symptom was an interviewer who was male on the first question and
female from the second onward. Only two voices could ever reach the candidate:
Kokoro's af_heart from this service, and the browser's own Web Speech voice --
on Windows a male one -- which the rooms used whenever a line failed to
synthesise. So any per-line TTS failure changed who appeared to be interviewing.

Cold start was the failure. Loading the local engine took far longer than any
single line takes to speak, and that load was being charged to the per-request
synthesis timeout, so the first request of a process timed out while every later
one succeeded. These tests pin the two properties that fix depends on.
"""

import asyncio
import pytest

from app.voice.tts import TextToSpeechService, _TTS_MIN_TIMEOUT_SECONDS
from app.voice.exceptions import TTSTimeoutError


REAL_WAV = (
    b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    b"\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00" + b"\x01" * 256
)


class SlowLoadingProvider:
    """Stands in for a local engine whose model load dwarfs its synthesis."""

    def __init__(self, load_seconds: float):
        self.load_seconds = load_seconds
        self.loaded = False
        self.synth_calls = 0

    async def ensure_ready(self):
        await asyncio.sleep(self.load_seconds)
        self.loaded = True

    async def synthesize_speech(self, text, voice_id="default"):
        assert self.loaded, "synthesis started before the engine was ready"
        self.synth_calls += 1
        await asyncio.sleep(0.01)
        return REAL_WAV


@pytest.mark.asyncio
async def test_model_load_is_not_charged_to_the_synthesis_timeout(monkeypatch):
    """A load longer than the whole timeout must still yield the real voice.

    Before, the load ran inside asyncio.wait_for, so a cold engine produced
    TTSTimeoutError on the first line only -- and that one line was then spoken
    by something else. Readiness is now awaited outside the timeout window, so
    the first line waits for the interviewer's own voice instead of losing it.
    """
    provider = SlowLoadingProvider(load_seconds=_TTS_MIN_TIMEOUT_SECONDS + 5)

    monkeypatch.setattr(
        "app.voice.tts.AIFactory.get_tts_provider",
        lambda *a, **kw: provider,
    )

    # Keep the test quick: the point is that the load is not *inside* the
    # timeout, so a load far longer than a short explicit budget still passes.
    provider.load_seconds = 0.4
    audio, meta = await TextToSpeechService.synthesize_with_metadata(
        "Tell me about yourself.", voice_id="en_us_female_senior", timeout_seconds=0.2
    )

    assert audio == REAL_WAV
    assert provider.synth_calls == 1
    assert meta["voice_id"] == "en_us_female_senior"


@pytest.mark.asyncio
async def test_synthesis_itself_is_still_bounded(monkeypatch):
    """Moving the load out of the window must not remove the window."""

    class HangingProvider(SlowLoadingProvider):
        async def synthesize_speech(self, text, voice_id="default"):
            await asyncio.sleep(5)
            return REAL_WAV

    provider = HangingProvider(load_seconds=0.01)
    monkeypatch.setattr(
        "app.voice.tts.AIFactory.get_tts_provider",
        lambda *a, **kw: provider,
    )

    with pytest.raises(TTSTimeoutError):
        await TextToSpeechService.synthesize_with_metadata(
            "Tell me about yourself.", timeout_seconds=0.2
        )


@pytest.mark.asyncio
async def test_interview_tts_never_falls_back_to_simulated_audio(monkeypatch):
    """The interview path must not be wired to a mock that fakes success.

    A 440 Hz tone returned under HTTP 200 is a failure the caller cannot see:
    it plays a beep as the interviewer, or -- if the caller treats it as broken
    -- swaps in another voice for that line.
    """
    captured = {}

    def fake_get(*args, **kwargs):
        captured.update(kwargs)
        return SlowLoadingProvider(load_seconds=0.0)

    monkeypatch.setattr("app.voice.tts.AIFactory.get_tts_provider", fake_get)
    await TextToSpeechService.synthesize("Hello there.", voice_id="en_us_female_senior")

    assert captured.get("enable_fallback") is False


def test_named_interviewer_voice_resolves_to_one_kokoro_voice():
    """The voice is named explicitly and maps to exactly one engine voice."""
    from app.providers.config import INTERVIEWER_VOICE_ID
    from app.providers.kokoro_tts import KokoroTTSProvider, VOICE_MAP

    assert INTERVIEWER_VOICE_ID in VOICE_MAP
    resolved = KokoroTTSProvider()._resolve_voice(INTERVIEWER_VOICE_ID)
    assert resolved == VOICE_MAP[INTERVIEWER_VOICE_ID]
    # Resolution must be stable: the same name always gives the same speaker.
    assert resolved == KokoroTTSProvider()._resolve_voice(INTERVIEWER_VOICE_ID)
