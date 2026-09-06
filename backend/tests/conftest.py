import asyncio
import pytest
from app.core.config import settings
from app.core.database import Base, engine, AsyncSessionLocal
from scripts.cleanup_unwanted_companies import APPROVED_SLUGS, cleanup_database


def _is_dedicated_postgres_test_db() -> bool:
    """cleanup_database() issues Postgres-only DELETE cascades.

    It may therefore run only against a dedicated Postgres *test* database.
    Throwaway SQLite needs no cleanup -- the file is discarded with the session.
    """
    url = engine.url
    if not url.drivername.startswith("postgresql"):
        return False
    database = (url.database or "").lower()
    return database.endswith("_test") or database.startswith("test_") or database == "test"


@pytest.fixture(autouse=True, scope="session")
def provision_test_database():
    """Create the schema and reference data the suite expects.

    The root conftest binds the engine to a throwaway database, which starts
    empty. Several tests require the approved companies that previously existed
    only in the developer's own database, so they are seeded here instead.
    """
    async def _provision():
        # Import the models BEFORE create_all: they register themselves on
        # Base.metadata at import time. Without this, a session whose selected
        # test modules never import app.db.models creates no tables at all, and
        # every test in that session fails with "no such table: companies".
        from sqlalchemy import select
        from app.db.models import Company  # noqa: F401  (registers metadata)
        from app.db.seed_data import seed_database

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Seed the repository's authoritative catalogue rather than a minimal
        # stand-in. This fixture used to insert the approved companies with one
        # "Software Engineer (Backend)" role each, which left the suite with no
        # frontend, ML, cloud or mobile role at all -- so a test asserting on a
        # specialised match could only pass if an unrelated module happened to
        # leak such a role into the shared session database first. Reusing
        # seed_database() removes that trap at the source and keeps a single
        # definition of the catalogue: it is idempotent (matched on company slug
        # and on (company_id, role title)) and covers exactly the ten approved
        # slugs cleanup_database() expects.
        await seed_database()

        async with AsyncSessionLocal() as db:
            seeded = {c.slug for c in (await db.execute(select(Company))).scalars().all()}
        missing = set(APPROVED_SLUGS) - seeded
        assert not missing, f"seed catalogue is missing approved companies: {sorted(missing)}"

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_provision())
    finally:
        loop.close()
        asyncio.set_event_loop(None)

    yield


@pytest.fixture(autouse=True, scope="session")
def setup_test_environment():
    """Ensure tests default to mock provider to prevent quota exhaustion and ensure determinism."""
    original_llm = settings.DEFAULT_LLM_PROVIDER
    original_tts = getattr(settings, "DEFAULT_TTS_PROVIDER", "mock")
    original_stt = getattr(settings, "DEFAULT_STT_PROVIDER", "mock")

    settings.DEFAULT_LLM_PROVIDER = "mock"
    settings.DEFAULT_TTS_PROVIDER = "mock"
    settings.DEFAULT_STT_PROVIDER = "mock"

    yield

    settings.DEFAULT_LLM_PROVIDER = original_llm
    settings.DEFAULT_TTS_PROVIDER = original_tts
    settings.DEFAULT_STT_PROVIDER = original_stt

def pytest_sessionfinish(session, exitstatus):
    """Post-test session hook to safely clean up any temporary test records."""
    if not _is_dedicated_postgres_test_db():
        # Never run DELETE cascades against a database that is not a dedicated
        # Postgres test database. A throwaway SQLite file needs no cleanup.
        return
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def _cleanup():
            await engine.dispose()
            await cleanup_database()
            await engine.dispose()

        loop.run_until_complete(_cleanup())
        loop.close()
    except Exception as e:
        print(f"[conftest] Cleanup error: {e}")
