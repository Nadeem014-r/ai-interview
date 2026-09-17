"""Staff provisioning CLI: creates/promotes staff accounts without opening public registration."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import init_db, AsyncSessionLocal
from app.core.security import verify_password, get_current_user_payload
from scripts.create_staff_user import provision_staff_user, ProvisioningError


PASSWORD = "Staff-Test-Passw0rd!"


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()


def _email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()


def _research_request(client: AsyncClient, token: str):
    return client.post(
        "/api/v1/research/company",
        json={"company_name": f"Prov Co {uuid.uuid4().hex[:6]}", "role_title": "Backend Engineer",
              "source_url": "https://example.com/jd"},
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["admin", "placement_staff"])
async def test_provisioned_staff_can_login_and_call_research(role):
    email = _email(role)
    async with AsyncSessionLocal() as db:
        user = await provision_staff_user(db, email=email, role=role, full_name="Staff", password=PASSWORD)
        assert user.role == role
        assert user.hashed_password != PASSWORD and verify_password(PASSWORD, user.hashed_password)

    source = MagicMock(id=1)
    fake_result = {"source": source, "document": None, "content_hash": "h", "is_cached": False,
                   "status": "ingested_new", "chunks_count": 0}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        data = await _login(client, email, PASSWORD)
        assert data["role"] == role
        claims = await get_current_user_payload(data["access_token"])
        assert claims["role"] == role

        with patch("app.api.v1.research.ResearchPipeline.ingest_company_role_research",
                   new=AsyncMock(return_value=fake_result)):
            res = await _research_request(client, data["access_token"])
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_candidate_still_forbidden_from_research():
    email = _email("cand")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg = await client.post("/api/v1/auth/register",
                                json={"email": email, "password": PASSWORD, "full_name": "Cand"})
        assert reg.status_code == 201 and reg.json()["role"] == "candidate"
        res = await _research_request(client, reg.json()["access_token"])
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_existing_account_requires_explicit_promote():
    email = _email("promo")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg = await client.post("/api/v1/auth/register",
                                json={"email": email, "password": PASSWORD, "full_name": "Cand"})
        assert reg.status_code == 201

    async with AsyncSessionLocal() as db:
        with pytest.raises(ProvisioningError):
            await provision_staff_user(db, email=email, role="admin", full_name="X", password=PASSWORD)
        user = await provision_staff_user(db, email=email.upper(), role="placement_staff", promote=True)
        assert user.role == "placement_staff"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await _login(client, email, PASSWORD))["role"] == "placement_staff"


@pytest.mark.asyncio
async def test_rejects_invalid_role_weak_password_and_missing_promote_target():
    async with AsyncSessionLocal() as db:
        with pytest.raises(ProvisioningError):
            await provision_staff_user(db, email=_email("r"), role="candidate", full_name="X", password=PASSWORD)
        with pytest.raises(ProvisioningError):
            await provision_staff_user(db, email=_email("r"), role="superuser", full_name="X", password=PASSWORD)
        with pytest.raises(ProvisioningError):
            await provision_staff_user(db, email=_email("w"), role="admin", full_name="X", password="short")
        with pytest.raises(ProvisioningError):
            await provision_staff_user(db, email=_email("m"), role="admin", promote=True)
