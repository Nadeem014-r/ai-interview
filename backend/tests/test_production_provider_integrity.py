"""Regression cover for Batch 5: no simulated provider may pass as a real one.

Four active runtime paths silently substituted a mock when a real provider was
missing or failing, and every one of them returned HTTP success:

  * AIFactory.get_llm_provider   -- missing API key -> MockLLMProvider
  * AIFactory.get_llm_provider   -- RoutedLLMProvider(fallback=MockLLMProvider),
                                    so a Gemini timeout returned mock JSON
  * AIFactory.get_stt_provider   -- engine unavailable -> MockSTTProvider, whose
                                    canned transcript would be stored and scored
                                    as the candidate's own spoken answer
  * POST /voice/tts              -- route-level MockTTSProvider fallback

Mock selected *explicitly* in configuration stays fully supported -- the whole
suite depends on it. Only the implicit swap is refused, and only in production.

No test here performs a real provider call: primaries are monkeypatched to fail,
and every assertion is about which object the factory returns or which error it
raises. Database work uses the guarded throwaway SQLite database.
"""

import pytest

from app.ai.exceptions import AIAuthenticationError, AIProviderError
from app.ai.factory import AIFactory, _implicit_mock_allowed
from app.ai.mock_provider import (
    MockEmbeddingProvider,
    MockLLMProvider,
    MockSTTProvider,
    MockTTSProvider,
)
from app.ai.router import RoutedLLMProvider
from app.core.config import settings


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "DEBUG", False)
    return monkeypatch


@pytest.fixture
def development(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    return monkeypatch


# ======================================================================
# The gate itself
# ======================================================================

@pytest.mark.parametrize("environment,allowed", [
    ("production", False),
    ("PRODUCTION", False),
    ("prod", False),
    ("development", True),
    ("staging", True),
    ("", True),
])
def test_implicit_mock_is_allowed_only_outside_production(monkeypatch, environment, allowed):
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    assert _implicit_mock_allowed() is allowed


# ======================================================================
# LLM: missing credentials
# ======================================================================

def test_production_refuses_mock_llm_when_api_key_is_missing(production):
    production.setattr(settings, "DEFAULT_LLM_PROVIDER", "gemini")
    production.setattr(settings, "GEMINI_API_KEY", "")

    with pytest.raises(AIAuthenticationError, match="GEMINI_API_KEY"):
        AIFactory.get_llm_provider()


def test_development_still_falls_back_to_mock_when_api_key_is_missing(development):
    """Offline development must keep working -- this is the behaviour being kept."""
    development.setattr(settings, "DEFAULT_LLM_PROVIDER", "gemini")
    development.setattr(settings, "GEMINI_API_KEY", "")

    assert isinstance(AIFactory.get_llm_provider(), MockLLMProvider)


def test_explicitly_configured_mock_is_honoured_in_production(production):
    """Selecting mock on purpose is configuration, not substitution."""
    production.setattr(settings, "DEFAULT_LLM_PROVIDER", "mock")
    assert isinstance(AIFactory.get_llm_provider(), MockLLMProvider)


# ======================================================================
# LLM: real provider fails at runtime
# ======================================================================

def test_production_does_not_wire_a_mock_fallback_behind_a_real_provider(production):
    production.setattr(settings, "DEFAULT_LLM_PROVIDER", "gemini")
    production.setattr(settings, "GEMINI_API_KEY", "test-key-never-called")
    production.setattr(settings, "LLM_ENABLE_FALLBACK", True)
    production.setattr(settings, "LLM_FALLBACK_PROVIDER", "mock")

    provider = AIFactory.get_llm_provider()
    assert not isinstance(provider, RoutedLLMProvider), (
        "a mock fallback behind the real provider turns an outage into fabricated success"
    )
    assert not isinstance(provider, MockLLMProvider)


@pytest.mark.asyncio
async def test_production_surfaces_the_real_failure_instead_of_mock_output(production):
    """The end-to-end shape of the leak: timeout must not become a JSON answer."""
    production.setattr(settings, "DEFAULT_LLM_PROVIDER", "gemini")
    production.setattr(settings, "GEMINI_API_KEY", "test-key-never-called")

    provider = AIFactory.get_llm_provider()

    async def _timeout(*args, **kwargs):
        raise TimeoutError("gemini request timed out")

    production.setattr(provider, "generate_json", _timeout, raising=False)

    with pytest.raises(TimeoutError):
        await provider.generate_json("interview overall score: 82, candidate assessment report")


@pytest.mark.asyncio
async def test_development_fallback_to_mock_still_works(development):
    """The designed offline failover is unchanged outside production."""
    development.setattr(settings, "DEFAULT_LLM_PROVIDER", "gemini")
    development.setattr(settings, "GEMINI_API_KEY", "test-key-never-called")
    development.setattr(settings, "LLM_ENABLE_FALLBACK", True)
    development.setattr(settings, "LLM_FALLBACK_PROVIDER", "mock")

    provider = AIFactory.get_llm_provider()
    assert isinstance(provider, RoutedLLMProvider)
    assert isinstance(provider.fallback, MockLLMProvider)

    async def _timeout(*args, **kwargs):
        raise TimeoutError("gemini request timed out")

    development.setattr(provider.primary, "generate_json", _timeout)
    result = await provider.generate_json("interview overall score: 82, candidate assessment report")
    assert isinstance(result, dict)
    assert provider.last_provider_used == "mock"


# ======================================================================
# Embeddings
# ======================================================================

def test_production_refuses_mock_embeddings_when_api_key_is_missing(production):
    production.setattr(settings, "DEFAULT_EMBEDDING_PROVIDER", "gemini")
    production.setattr(settings, "GEMINI_API_KEY", "")

    with pytest.raises(AIAuthenticationError, match="GEMINI_API_KEY"):
        AIFactory.get_embedding_provider()


def test_explicitly_configured_mock_embeddings_are_honoured(production):
    production.setattr(settings, "DEFAULT_EMBEDDING_PROVIDER", "mock")
    assert isinstance(AIFactory.get_embedding_provider(), MockEmbeddingProvider)


# ======================================================================
# STT -- the most damaging leak: a fabricated candidate answer
# ======================================================================

def test_production_refuses_a_fabricated_transcript_when_stt_is_unavailable(production):
    from app.providers import whisper_stt

    def _boom(self, *args, **kwargs):
        raise RuntimeError("whisper model weights unavailable on this host")

    production.setattr(settings, "DEFAULT_STT_PROVIDER", "whisper")
    production.setattr(whisper_stt.WhisperSmallSTTProvider, "__init__", _boom)

    with pytest.raises(AIProviderError, match="Speech-to-text is unavailable"):
        AIFactory.get_stt_provider()


def test_development_still_falls_back_to_mock_stt(development):
    from app.providers import whisper_stt

    def _boom(self, *args, **kwargs):
        raise RuntimeError("whisper model weights unavailable on this host")

    development.setattr(settings, "DEFAULT_STT_PROVIDER", "whisper")
    development.setattr(whisper_stt.WhisperSmallSTTProvider, "__init__", _boom)

    assert isinstance(AIFactory.get_stt_provider(), MockSTTProvider)


def test_explicitly_configured_mock_stt_is_honoured_in_production(production):
    production.setattr(settings, "DEFAULT_STT_PROVIDER", "mock")
    assert isinstance(AIFactory.get_stt_provider(), MockSTTProvider)


# ======================================================================
# TTS
# ======================================================================

def test_production_refuses_simulated_audio_when_the_engine_is_unavailable(production):
    production.setattr(settings, "DEFAULT_TTS_PROVIDER", "kokoro")

    # Force the engine construction to fail the way a missing model would.
    from app.providers import kokoro_tts

    def _init_boom(self, *args, **kwargs):
        raise RuntimeError("kokoro voice pack missing")

    production.setattr(kokoro_tts.KokoroTTSProvider, "__init__", _init_boom)

    with pytest.raises(AIProviderError, match="Text-to-speech is unavailable"):
        AIFactory.get_tts_provider()


def test_explicitly_configured_mock_tts_is_honoured_in_production(production):
    production.setattr(settings, "DEFAULT_TTS_PROVIDER", "mock")
    assert isinstance(AIFactory.get_tts_provider(), MockTTSProvider)


# ======================================================================
# Health truthfulness
# ======================================================================

@pytest.mark.asyncio
async def test_health_reports_provider_configuration_honestly(monkeypatch):
    """"healthy" must not imply a provider that holds no credentials is usable."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    monkeypatch.setattr(settings, "DEFAULT_LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = (await client.get("/health")).json()

    assert body["status"] == "healthy"
    assert body["llm_provider"] == "gemini"
    assert body["llm_provider_configured"] is False

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "configured-key")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = (await client.get("/health")).json()
    assert body["llm_provider_configured"] is True


@pytest.mark.asyncio
async def test_health_makes_no_external_provider_call(monkeypatch):
    """A deployment probe must never cost a paid API request."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    calls = []

    async def _tripwire(*args, **kwargs):
        calls.append(args)
        raise AssertionError("/health must not call an AI provider")

    monkeypatch.setattr(MockLLMProvider, "generate_text", _tripwire)
    monkeypatch.setattr(MockLLMProvider, "generate_json", _tripwire)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/health/liveness")).status_code == 200

    assert calls == []


# ======================================================================
# The route-level mock fallback (a separate code path from the factory)
# ======================================================================

async def _authenticate(client):
    import uuid

    email = f"prov_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"
    reg = await client.post("/api/v1/auth/register", json={
        "email": email, "password": password,
        "full_name": "Provider Integrity", "role": "candidate",
    })
    assert reg.status_code == 201, reg.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_tts_route_does_not_serve_simulated_audio_in_production(production):
    """POST /voice/tts fell back to MockTTSProvider inside the route itself,
    returning a 440 Hz tone as the interviewer's voice under HTTP 200."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.voice.tts import TextToSpeechService

    async def _boom(*args, **kwargs):
        raise RuntimeError("tts engine offline")

    production.setattr(TextToSpeechService, "synthesize", _boom)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _authenticate(client)
        res = await client.post("/api/v1/voice/tts", json={"text": "Hello"}, headers=headers)

    assert res.status_code == 503, res.text
    assert b"RIFF" not in res.content


@pytest.mark.asyncio
async def test_tts_route_reports_failure_in_every_environment(development):
    """A TTS outage is reported, never papered over with simulated audio.

    This route speaks as the interviewer, and the mock provider's 440 Hz tone
    was previously returned under HTTP 200 in development. The caller could not
    tell that apart from real speech: it cached the tone and played it, or --
    treating the oddity as a failure -- spoke that one line with the browser's
    own voice, so the interviewer changed person mid-session. Reporting the
    outage lets the client retry and get the same voice, which is why the
    development carve-out is gone rather than merely disabled in production.
    """
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.voice.tts import TextToSpeechService

    async def _boom(*args, **kwargs):
        raise RuntimeError("tts engine offline")

    development.setattr(TextToSpeechService, "synthesize", _boom)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _authenticate(client)
        res = await client.post("/api/v1/voice/tts", json={"text": "Hello"}, headers=headers)

    assert res.status_code == 503
    assert "audio" not in res.headers.get("content-type", "")
