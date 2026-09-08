"""Batch 8 regression coverage for production security hardening.

Each test pins a defect that was reproduced and fixed in Batch 8 and that would
otherwise regress silently.
"""

import httpx
import pytest

from app.core.config import Settings


def test_debug_defaults_to_false():
    """DEBUG drives SQLAlchemy `echo`, which logs every statement *and its bound
    parameters* -- user emails and password hashes included. A True default meant
    docker-compose.yml (ENVIRONMENT=production, DEBUG unset) leaked that to logs.
    """
    assert Settings.model_fields["DEBUG"].default is False


def test_allowed_hosts_accepts_comma_separated_environment_value(monkeypatch):
    """ALLOWED_HOSTS must parse the comma-separated form used by .env.example and
    docker-compose.production.yml. As a List[str], pydantic-settings JSON-decoded
    it from the environment and raised SettingsError before the app could serve.
    """
    monkeypatch.setenv("SECRET_KEY", "batch8-regression-secret-key-with-enough-entropy")
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1")

    settings = Settings()

    assert settings.allowed_hosts == ["localhost", "127.0.0.1"]


async def test_gemini_api_key_is_sent_as_header_not_in_url():
    """The key used to travel in the query string, so httpx errors chained onto a
    provider exception -- and any traceback logged from them -- carried the live
    credential into the logs.
    """
    from app.ai.gemini_provider import GeminiLLMProvider

    fake_key = "FAKEKEY_not_a_real_credential_1234567890"
    captured = {}

    class CapturingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            captured["url"] = str(request.url)
            captured["header"] = request.headers.get("x-goog-api-key")
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
                request=request,
            )

    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = CapturingTransport()
        original_init(self, *args, **kwargs)

    httpx.AsyncClient.__init__ = patched_init
    try:
        await GeminiLLMProvider(api_key=fake_key).generate_text("hello")
    finally:
        httpx.AsyncClient.__init__ = original_init

    assert captured["header"] == fake_key
    assert fake_key not in captured["url"]
    assert "key=" not in captured["url"]
