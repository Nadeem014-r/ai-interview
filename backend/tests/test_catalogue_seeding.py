"""Regression cover for test-catalogue provisioning and cold-start seeding.

The suite used to provision a minimal catalogue -- the ten approved companies
with one "Software Engineer (Backend)" role each -- so no frontend, ML, cloud or
mobile role existed at all. A test asserting on a specialised match could then
only pass if an unrelated module happened to leak such a role into the shared
session database first, which is exactly how
test_two_different_resumes_produce_different_role_matches became order
dependent. tests/conftest.py now seeds app.db.seed_data.seed_database(), the
repository's authoritative catalogue.

Investigating that also surfaced a production cold-start defect: the seeding
branch of GET /companies imported a name (`seed_all_companies_and_roles`) that
app.db.seed_data never defined, so the first request against a fresh
deployment's empty database raised ImportError -> 500 rather than seeding.

Database safety: the session-scoped tests use the guarded throwaway SQLite
database from backend/conftest.py; the cold-start test builds its own separate
throwaway SQLite file and overrides get_db. Nothing here touches the configured
PostgreSQL database.
"""

import os
import tempfile
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, Base, get_db
from app.db.models import Company, Role
from app.db.seed_data import COMPANIES

# Skills that only exist on specialised roles. Read from the catalogue itself so
# this never hardcodes a policy the seed data does not actually hold.
FRONTEND_SKILL = "React"
ML_SKILL = "PyTorch"


async def _roles_requiring(skill):
    async with AsyncSessionLocal() as session:
        roles = (await session.execute(select(Role))).scalars().all()
    return [r.title for r in roles if skill in (r.required_skills or [])]


# ======================================================================
# The session catalogue is the real one, available to every test
# ======================================================================

@pytest.mark.asyncio
async def test_session_catalogue_matches_the_repository_seed_data():
    """One definition of the catalogue -- conftest must not fork its own."""
    async with AsyncSessionLocal() as session:
        companies = (await session.execute(
            select(Company).options(selectinload(Company.roles))
        )).scalars().all()

    by_slug = {c.slug: c for c in companies}
    for entry in COMPANIES:
        company = by_slug.get(entry["slug"])
        assert company is not None, f"approved company '{entry['slug']}' was not seeded"
        seeded_titles = {r.title for r in company.roles}
        expected_titles = {r["title"] for r in entry["roles"]}
        assert expected_titles <= seeded_titles, (
            f"{entry['slug']} is missing roles {sorted(expected_titles - seeded_titles)}"
        )


@pytest.mark.asyncio
async def test_specialised_roles_exist_without_any_donor_test():
    """The failure mode directly: no leaked row, yet both specialisms present.

    If conftest reverts to a one-role-per-company catalogue these lists go empty
    and the order-dependent class of failure becomes possible again.
    """
    assert await _roles_requiring(FRONTEND_SKILL), (
        f"no role requires {FRONTEND_SKILL}; a frontend match can only pass on leaked state"
    )
    assert await _roles_requiring(ML_SKILL), (
        f"no role requires {ML_SKILL}; an ML match can only pass on leaked state"
    )


@pytest.mark.asyncio
async def test_provisioning_is_idempotent():
    """Re-running the seeder must not duplicate companies or roles."""
    from app.db.seed_data import seed_database

    async with AsyncSessionLocal() as session:
        before = (
            len((await session.execute(select(Company))).scalars().all()),
            len((await session.execute(select(Role))).scalars().all()),
        )

    await seed_database()

    async with AsyncSessionLocal() as session:
        after = (
            len((await session.execute(select(Company))).scalars().all()),
            len((await session.execute(select(Role))).scalars().all()),
        )

    assert before == after


# ======================================================================
# Production cold start: an empty database must seed itself, not 500
# ======================================================================

@pytest_asyncio.fixture
async def empty_db_client(monkeypatch):
    """App client bound to its own empty throwaway SQLite database.

    seed_database() opens a session of its own rather than taking the request's.
    In production that is the same database, so the route's re-query sees the
    rows it commits; here the sessionmaker inside app.db.seed_data is redirected
    at this fixture's database to reproduce that single-database reality.
    """
    from app.db import seed_data
    from app.main import api_v1, app

    path = os.path.join(tempfile.gettempdir(), f"catalogue_{uuid.uuid4().hex}.sqlite")
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    assert engine.dialect.name == "sqlite"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db():
        async with maker() as session:
            yield session

    monkeypatch.setattr(seed_data, "AsyncSessionLocal", maker)
    api_v1.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_db] = _get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, maker
    finally:
        api_v1.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()
        if os.path.exists(path):
            os.remove(path)


@pytest.mark.asyncio
async def test_cold_start_seeds_the_catalogue_instead_of_erroring(empty_db_client):
    """GET /companies against an empty database seeds it and returns the catalogue.

    Before the fix this raised ImportError inside the seeding branch, so a fresh
    deployment's very first catalogue request returned 500 and no company or
    role was ever created.
    """
    client, maker = empty_db_client

    async with maker() as session:
        assert (await session.execute(select(Company))).scalars().all() == []

    response = await client.get("/api/v1/companies")
    assert response.status_code == 200, response.text

    body = response.json()
    assert len(body) == len(COMPANIES)
    assert {c["slug"] for c in body} == {entry["slug"] for entry in COMPANIES}
