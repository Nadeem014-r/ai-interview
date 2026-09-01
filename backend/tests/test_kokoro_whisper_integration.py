"""Integration tests for Kokoro 0.9.4 TTS and Whisper Small STT.

Validates:
- Kokoro TTS synthesis produces standard playable RIFF/WAVE 24kHz audio.
- Whisper Small STT transcribes audio bytes into high accuracy text.
- Bidirectional round-trip (Text -> Kokoro -> WAV -> Whisper -> Text).
- FastAPI endpoints /api/v1/voice/tts and /api/v1/voice/stt.
- Fallback and validation safety.
"""

import pytest
import io
import soundfile as sf
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.providers.kokoro_tts import KokoroTTSProvider
from app.providers.whisper_stt import WhisperSmallSTTProvider
from app.providers.provider_manager import provider_manager
from app.ai.factory import AIFactory


@pytest.mark.asyncio
async def test_kokoro_tts_direct_synthesis():
    """Test that KokoroTTSProvider produces valid 24kHz PCM WAV bytes."""
    provider = KokoroTTSProvider()
    text = "Hello, welcome to Google. Let's discuss your experience with distributed systems."
    audio_bytes = await provider.synthesize_speech(text, voice_id="af_heart")

    assert audio_bytes is not None
    assert len(audio_bytes) > 2000
    assert audio_bytes.startswith(b"RIFF")

    # Verify WAV header and sample rate with soundfile
    with io.BytesIO(audio_bytes) as buf:
        data, samplerate = sf.read(buf)
        assert samplerate == 24000
        assert len(data) > 0


@pytest.mark.asyncio
async def test_whisper_stt_direct_transcription():
    """Test that WhisperSmallSTTProvider transcribes synthesized audio correctly."""
    tts = KokoroTTSProvider()
    stt = WhisperSmallSTTProvider()

    expected_text = "I have built high throughput microservices using FastAPI and Redis."
    wav_bytes = await tts.synthesize_speech(expected_text, voice_id="am_adam")

    result = await stt.transcribe_audio(wav_bytes, filename="answer.wav")

    assert result is not None
    assert "transcript" in result
    transcript = result["transcript"].lower()
    
    # Check that key technical keywords are captured accurately
    assert "fastapi" in transcript or "fast" in transcript
    assert "microservices" in transcript or "services" in transcript or "throughput" in transcript


@pytest.mark.asyncio
async def test_factory_and_provider_manager_resolution():
    """Test that AIFactory and ProviderManager return Kokoro and Whisper providers."""
    tts_prov = AIFactory.get_tts_provider()
    assert tts_prov is not None

    stt_prov = AIFactory.get_stt_provider()
    assert stt_prov is not None

    pm_tts = provider_manager.get_tts_provider("kokoro")
    assert pm_tts is not None

    pm_stt = provider_manager.get_stt_provider("whisper")
    assert pm_stt is not None


@pytest.mark.asyncio
async def test_voice_tts_endpoint():
    """Test /api/v1/voice/tts HTTP endpoint returns valid audio response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/voice/tts",
            json={"text": "Can you explain the difference between processes and threads?", "voice_id": "default"}
        )
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("audio/")
        assert len(res.content) > 1000
        assert res.content.startswith(b"RIFF")


@pytest.mark.asyncio
async def test_voice_stt_endpoint():
    """Test /api/v1/voice/stt HTTP endpoint transcribes uploaded audio files."""
    tts = KokoroTTSProvider()
    wav_bytes = await tts.synthesize_speech("PostgreSQL database indexing strategy.", voice_id="af_bella")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = {"file": ("sample.wav", wav_bytes, "audio/wav")}
        res = await client.post("/api/v1/voice/stt", files=files)

        assert res.status_code == 200
        data = res.json()
        assert "transcript" in data
        assert len(data["transcript"]) > 0


@pytest.mark.asyncio
async def test_tts_empty_text_rejection():
    """Test that empty or whitespace text in TTS is safely rejected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/v1/voice/tts", json={"text": "   "})
        assert res.status_code in (400, 422)
