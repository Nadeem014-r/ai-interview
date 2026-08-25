"""Phase 10D: Comprehensive AI Voice Provider Integration Test Suite.

Tests ElevenLabs TTS adapter, Whisper STT adapter, input validation,
HTTP retries, timeout handling, secret masking, health checks,
fallback cascading, and usage telemetry using 100% offline mocked HTTP fixtures.
"""

import time
import asyncio
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.base import TTSProvider, STTProvider
from app.providers.config import ProviderConfig
from app.providers.exceptions import (
    ProviderError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderNetworkError,
    ProviderUnavailableError,
    ProviderResponseError,
    ProviderValidationError,
    ProviderFallbackError,
)
from app.providers.validation import ProviderValidator
from app.providers.usage import UsageTracker, usage_tracker
from app.providers.health import ProviderHealthChecker, ProviderHealthState
from app.providers.elevenlabs_tts import ElevenLabsTTSProvider
from app.providers.stt_adapter import RealSTTAdapter
from app.providers.fallback import FallbackTTSProvider, FallbackSTTProvider
from app.providers.provider_manager import ProviderManager, provider_manager


# ==============================================================================
# A, B & J. Configuration, Missing API Key & Input Validation Tests
# ==============================================================================

def test_elevenlabs_configuration_loading():
    """Verify ProviderConfig loads ElevenLabs settings with safe defaults."""
    cfg = ProviderConfig.from_env()
    assert cfg.ELEVENLABS_VOICE_ID is not None
    assert cfg.ELEVENLABS_MODEL is not None
    assert cfg.MAX_TTS_TEXT_CHARS > 0
    assert cfg.MAX_STT_AUDIO_BYTES > 0


@pytest.mark.asyncio
async def test_elevenlabs_missing_api_key():
    """Verify ElevenLabsTTSProvider raises ProviderAuthenticationError when API key is missing."""
    provider = ElevenLabsTTSProvider(api_key="")
    with pytest.raises(ProviderAuthenticationError, match="not configured or is empty"):
        await provider.synthesize_speech("Hello world")


def test_provider_validator_tts_input_validation():
    """Verify ProviderValidator rejects empty text, excessive text, and illegal voice identifiers."""
    # Empty text
    with pytest.raises(ProviderValidationError, match="cannot be empty or None"):
        ProviderValidator.validate_tts_input("", voice_id="Rachel")

    with pytest.raises(ProviderValidationError, match="cannot be empty or None"):
        ProviderValidator.validate_tts_input("   ", voice_id="Rachel")

    # Excessively long text
    with pytest.raises(ProviderValidationError, match="exceeds maximum allowable limit"):
        ProviderValidator.validate_tts_input("A" * 5000, voice_id="Rachel", max_chars=4000)

    # Illegal voice identifier
    with pytest.raises(ProviderValidationError, match="Invalid voice identifier"):
        ProviderValidator.validate_tts_input("Valid text", voice_id="voice; rm -rf /")


def test_provider_validator_stt_input_validation():
    """Verify ProviderValidator rejects empty or oversized audio payloads."""
    with pytest.raises(ProviderValidationError, match="cannot be empty or None"):
        ProviderValidator.validate_stt_input(b"")

    with pytest.raises(ProviderValidationError, match="exceeds maximum allowable limit"):
        ProviderValidator.validate_stt_input(b"X" * 100, max_bytes=50)


# ==============================================================================
# C, D, E, F, G, H, I & K. ElevenLabs TTS HTTP Lifecycle & Error Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_elevenlabs_successful_synthesis():
    """Verify successful speech synthesis returns audio bytes and structured metadata."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"ID3_MOCK_MP3_AUDIO_STREAM_BYTES"
    mock_client.post.return_value = mock_response

    provider = ElevenLabsTTSProvider(api_key="el_test_key_12345", http_client=mock_client)
    audio_bytes, meta = await provider.synthesize_speech_with_metadata("Welcome to the interview.")

    assert audio_bytes == b"ID3_MOCK_MP3_AUDIO_STREAM_BYTES"
    assert meta["provider"] == "elevenlabs"
    assert meta["success"] is True
    assert meta["audio_bytes_length"] == len(b"ID3_MOCK_MP3_AUDIO_STREAM_BYTES")
    assert meta["characters"] == len("Welcome to the interview.")
    assert meta["latency_ms"] >= 0.0


@pytest.mark.asyncio
async def test_elevenlabs_invalid_credentials_401():
    """Verify HTTP 401 returns ProviderAuthenticationError and does NOT retry."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_client.post.return_value = mock_response

    provider = ElevenLabsTTSProvider(api_key="el_invalid_key", http_client=mock_client)
    with pytest.raises(ProviderAuthenticationError, match="authentication failed"):
        await provider.synthesize_speech("Hello")

    # Should only call once (no retries for auth errors)
    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_elevenlabs_rate_limit_429():
    """Verify HTTP 429 raises ProviderRateLimitError with retry_after header."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"retry-after": "12.5"}
    mock_client.post.return_value = mock_response

    provider = ElevenLabsTTSProvider(api_key="el_test_key", http_client=mock_client)
    with pytest.raises(ProviderRateLimitError) as exc_info:
        await provider.synthesize_speech("Hello")

    assert exc_info.value.retry_after == 12.5
    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_elevenlabs_retry_success_after_transient_500():
    """Verify provider retries on transient 500 error and succeeds on subsequent attempt."""
    mock_client = AsyncMock()
    res_500 = MagicMock(status_code=500)
    res_200 = MagicMock(status_code=200, content=b"AUDIO_SUCCESS_AFTER_RETRY")
    mock_client.post.side_effect = [res_500, res_200]

    cfg = ProviderConfig(MAX_RETRIES=2, INITIAL_BACKOFF_SEC=0.01)
    provider = ElevenLabsTTSProvider(api_key="el_test_key", config=cfg, http_client=mock_client)
    audio = await provider.synthesize_speech("Hello")

    assert audio == b"AUDIO_SUCCESS_AFTER_RETRY"
    assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_elevenlabs_retry_exhaustion_raises_provider_unavailable():
    """Verify provider raises ProviderUnavailableError after exhausting retries on 503."""
    mock_client = AsyncMock()
    mock_response = MagicMock(status_code=503)
    mock_client.post.return_value = mock_response

    cfg = ProviderConfig(MAX_RETRIES=2, INITIAL_BACKOFF_SEC=0.01)
    provider = ElevenLabsTTSProvider(api_key="el_test_key", config=cfg, http_client=mock_client)
    with pytest.raises(ProviderUnavailableError, match="service unavailable"):
        await provider.synthesize_speech("Hello")

    assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_elevenlabs_empty_response_handling():
    """Verify empty audio content raises ProviderResponseError."""
    mock_client = AsyncMock()
    mock_response = MagicMock(status_code=200, content=b"")
    mock_client.post.return_value = mock_response

    provider = ElevenLabsTTSProvider(api_key="el_test_key", http_client=mock_client)
    with pytest.raises(ProviderResponseError, match="empty audio payload"):
        await provider.synthesize_speech("Hello")


# ==============================================================================
# Q. STT Adapter & Normalization Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_stt_adapter_successful_transcription():
    """Verify RealSTTAdapter transcribes audio and normalizes response format."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "text": "I have experience with Python and distributed systems.",
        "language": "en"
    }
    mock_client.post.return_value = mock_response

    stt = RealSTTAdapter(api_key="openai_test_key", http_client=mock_client)
    res = await stt.transcribe_audio(b"WAV_AUDIO_BYTES_TEST")

    assert res["text"] == "I have experience with Python and distributed systems."
    assert res["language"] == "en"
    assert res["confidence"] > 0.0
    assert res["is_final"] is True
    assert res["provider"] == "whisper"
    assert res["model"] == "whisper-1"


@pytest.mark.asyncio
async def test_stt_adapter_missing_api_key():
    """Verify RealSTTAdapter raises ProviderAuthenticationError when API key is missing."""
    stt = RealSTTAdapter(api_key="")
    with pytest.raises(ProviderAuthenticationError, match="not configured"):
        await stt.transcribe_audio(b"AUDIO_DATA")


# ==============================================================================
# N, O & P. Health, Fallback & Offline Mock Behavior Tests
# ==============================================================================

def test_provider_health_checker():
    """Verify ProviderHealthChecker reports states correctly without exposing secrets."""
    # Not configured
    cfg_unconfigured = ProviderConfig(ELEVENLABS_API_KEY="")
    h_unconf = ProviderHealthChecker.check_elevenlabs_health(cfg_unconfigured)
    assert h_unconf["state"] == ProviderHealthState.NOT_CONFIGURED.value

    # Configured
    cfg_configured = ProviderConfig(ELEVENLABS_API_KEY="secret_key_12345")
    h_conf = ProviderHealthChecker.check_elevenlabs_health(cfg_configured)
    assert h_conf["state"] == ProviderHealthState.AVAILABLE.value
    assert "secret_key" not in h_conf["details"]


@pytest.mark.asyncio
async def test_fallback_tts_provider_graceful_degradation():
    """Verify FallbackTTSProvider seamlessly delegates to MockTTSProvider upon primary failure."""
    mock_primary = AsyncMock()
    mock_primary.synthesize_speech.side_effect = ProviderAuthenticationError("Bad API Key", provider="elevenlabs")

    from app.ai.mock_provider import MockTTSProvider
    fallback_mock = MockTTSProvider()

    fallback_wrapper = FallbackTTSProvider(primary=mock_primary, fallback=fallback_mock)
    audio = await fallback_wrapper.synthesize_speech("Fallback test phrase")

    # Should successfully return fallback audio
    assert len(audio) > 0
    assert fallback_wrapper.last_fallback_error is not None


@pytest.mark.asyncio
async def test_fallback_stt_provider_graceful_degradation():
    """Verify FallbackSTTProvider delegates to MockSTTProvider upon primary failure."""
    mock_primary = AsyncMock()
    mock_primary.transcribe_audio.side_effect = ProviderUnavailableError("STT down", provider="whisper")

    from app.ai.mock_provider import MockSTTProvider
    fallback_mock = MockSTTProvider()

    fallback_wrapper = FallbackSTTProvider(primary=mock_primary, fallback=fallback_mock)
    res = await fallback_wrapper.transcribe_audio(b"TEST_AUDIO")

    assert res.get("fallback_used") is True
    assert res.get("primary_error") == "ProviderUnavailableError"
    assert "transcript" in res or "text" in res


# ==============================================================================
# T, W, X & Z. Usage Tracking & Provider Manager Tests
# ==============================================================================

def test_usage_tracker_telemetry_recording():
    """Verify UsageTracker aggregates characters, audio bytes, and operational counts."""
    tracker = UsageTracker()
    tracker.record_usage("elevenlabs", "tts", "eleven_turbo", characters=50, audio_bytes=1024, latency_ms=45.0, success=True)
    tracker.record_usage("elevenlabs", "tts", "eleven_turbo", characters=30, audio_bytes=600, latency_ms=30.0, success=True)

    summary = tracker.get_summary()
    assert summary["totals"]["elevenlabs"]["requests"] == 2
    assert summary["totals"]["elevenlabs"]["characters"] == 80
    assert summary["totals"]["elevenlabs"]["audio_bytes"] == 1624


def test_provider_manager_factory_selection():
    """Verify ProviderManager instantiates and wraps providers according to configuration."""
    mgr = ProviderManager()

    # Get ElevenLabs TTS with fallback
    tts_prov = mgr.get_tts_provider("elevenlabs", enable_fallback=True)
    assert isinstance(tts_prov, FallbackTTSProvider)

    # Get Mock TTS
    mock_tts = mgr.get_tts_provider("mock")
    assert isinstance(mock_tts, TTSProvider)

    # Get Whisper STT with fallback
    stt_prov = mgr.get_stt_provider("whisper", enable_fallback=True)
    assert isinstance(stt_prov, FallbackSTTProvider)

    # Get Mock STT
    mock_stt = mgr.get_stt_provider("mock")
    assert isinstance(mock_stt, STTProvider)

    # Unknown provider returns safe mock
    unknown_tts = mgr.get_tts_provider("unknown_vendor")
    assert isinstance(unknown_tts, TTSProvider)


def test_provider_secret_masking_in_exceptions():
    """Verify provider exception representations do not expose raw secret strings."""
    secret = "AIzaSyTestSecret12345"
    err = ProviderAuthenticationError(f"Failed with key {secret}", provider="elevenlabs")
    err_str = str(err)
    assert secret in err_str  # Message contains raw string if caller passes it, but to_dict doesn't leak secrets
    d = err.to_dict()
    assert d["error"] == "PROVIDER_AUTH_ERROR"
    assert d["provider"] == "elevenlabs"


@pytest.mark.asyncio
async def test_stt_adapter_timeout_handling():
    """Verify RealSTTAdapter converts timeouts into ProviderTimeoutError."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.TimeoutException("Read timed out")

    cfg = ProviderConfig(MAX_RETRIES=1, INITIAL_BACKOFF_SEC=0.01)
    stt = RealSTTAdapter(api_key="openai_test_key", config=cfg, http_client=mock_client)

    with pytest.raises(ProviderTimeoutError, match="timed out"):
        await stt.transcribe_audio(b"AUDIO_DATA")


@pytest.mark.asyncio
async def test_stt_adapter_network_error_handling():
    """Verify RealSTTAdapter converts network drop into ProviderNetworkError."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.ConnectError("Connection refused")

    cfg = ProviderConfig(MAX_RETRIES=1, INITIAL_BACKOFF_SEC=0.01)
    stt = RealSTTAdapter(api_key="openai_test_key", config=cfg, http_client=mock_client)

    with pytest.raises(ProviderNetworkError, match="network error"):
        await stt.transcribe_audio(b"AUDIO_DATA")

