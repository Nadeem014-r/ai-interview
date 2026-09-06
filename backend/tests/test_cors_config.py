"""Audit C5: credentialed CORS must be granted only to explicitly configured origins.

The previous configuration was allow_origins=["*"] together with
allow_credentials=True, which is both insecure in intent and rejected by
browsers. These tests pin the corrected behaviour.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import Settings, settings
from app.core.security import create_access_token

APPROVED = "http://localhost:3000"
UNAPPROVED = "https://evil.example.com"


def test_configured_origins_are_explicit():
    """No wildcard may reach CORSMiddleware while credentials are enabled."""
    origins = settings.cors_origins
    assert origins, "CORS_ORIGINS must not be empty"
    assert "*" not in origins
    assert all(o.startswith(("http://", "https://")) for o in origins), origins


def test_cors_origins_parses_comma_separated_environment_value():
    """.env.example and docker-compose supply a comma-separated list."""
    s = Settings(
        _env_file=None,
        SECRET_KEY="a" * 40,
        CORS_ORIGINS="https://interview.example.edu, https://app.example.edu/ ",
    )
    # whitespace trimmed, trailing slash removed so values match the browser's Origin header
    assert s.cors_origins == ["https://interview.example.edu", "https://app.example.edu"]


def test_default_origins_cover_local_frontend_development():
    s = Settings(_env_file=None, SECRET_KEY="a" * 40)
    assert APPROVED in s.cors_origins


@pytest.mark.asyncio
async def test_approved_origin_receives_credentialed_cors_headers():
    token = create_access_token(subject=1, role="candidate")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(
            "/health", headers={"Origin": APPROVED, "Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == APPROVED
        assert res.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_unapproved_origin_is_not_granted_cors_access():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health", headers={"Origin": UNAPPROVED})
        # Without an Access-Control-Allow-Origin header the browser blocks the read.
        assert res.headers.get("access-control-allow-origin") is None

        preflight = await client.options(
            "/api/v1/interviews",
            headers={
                "Origin": UNAPPROVED,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert preflight.status_code == 400
        assert preflight.headers.get("access-control-allow-origin") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,request_headers",
    [
        ("POST", "/api/v1/auth/login", "content-type"),
        ("POST", "/api/v1/interviews", "authorization,content-type"),
        ("POST", "/api/v1/voice/tts", "authorization,content-type"),
        ("POST", "/api/v1/voice/stt", "authorization"),
    ],
)
async def test_preflight_succeeds_for_approved_origin(method, path, request_headers):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.options(
            path,
            headers={
                "Origin": APPROVED,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": request_headers,
            },
        )
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == APPROVED
        assert res.headers.get("access-control-allow-credentials") == "true"
        allowed = res.headers.get("access-control-allow-headers", "").lower()
        for header in request_headers.split(","):
            assert header in allowed


@pytest.mark.asyncio
async def test_cors_does_not_alter_authentication_behaviour():
    """CORS is a browser control; server-side auth must be unaffected by Origin."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for origin in (APPROVED, UNAPPROVED):
            res = await client.get("/api/v1/profile", headers={"Origin": origin})
            assert res.status_code == 401
