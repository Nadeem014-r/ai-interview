"""Regression cover for SQLite foreign-key enforcement in the test database.

SQLite starts every connection with foreign-key enforcement *off*. The suite's
throwaway database is created from the same ``Base.metadata`` that renders the
PostgreSQL schema, whose ``FOREIGN KEY ... REFERENCES`` constraints the server
always enforces. Without the PRAGMA the SQLite stand-in silently accepted rows
PostgreSQL rejects, so ``test_vector_store_rollback_on_failure`` could never see
the constraint violation it asserts -- VectorStore's rollback path was never
reached, and an orphan chunk row was left behind instead.

``backend/conftest.py::enable_sqlite_foreign_keys`` turns the PRAGMA on for the
test engine only. These tests pin that behaviour, the rollback path it makes
reachable, and the safety architecture it must not weaken.
"""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal, Base, engine
from app.db.models import Document, DocumentChunk, Source
from app.rag.exceptions import VectorStoreError
from app.rag.vector_store import VectorStore

ORPHAN_DOCUMENT_ID = -9999

sqlite_only = pytest.mark.skipif(
    not engine.url.drivername.startswith("sqlite"),
    reason="PRAGMA foreign_keys is SQLite-specific; a Postgres test database enforces natively.",
)

_root_conftest_module = None


def root_conftest():
    """Load ``backend/conftest.py`` under its own module name.

    pytest imports both conftest files as ``conftest`` and the ``tests/`` one
    wins in ``sys.modules``, so the session-safety helpers have to be loaded by
    path. Re-executing the module is inert: its provisioning step returns early
    whenever ``DATABASE_URL`` already names a safe test database, which a
    running session guarantees.
    """
    global _root_conftest_module
    if _root_conftest_module is None:
        path = Path(__file__).resolve().parents[1] / "conftest.py"
        spec = importlib.util.spec_from_file_location("backend_root_conftest", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _root_conftest_module = module
    return _root_conftest_module


async def _make_document(session) -> Document:
    """A real Source + Document so a chunk has a valid parent to point at."""
    source = Source(
        source_type="official_job_desc",
        source_url="https://example.test/fk-regression",
        title="FK Regression Source",
        content_hash="fk_regression_hash",
        trust_level="official_trusted",
    )
    session.add(source)
    await session.flush()
    document = Document(source_id=source.id, title="FK Regression Doc", content="Body")
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


# ======================================================================
# 1. The PRAGMA is actually on for connections the suite uses
# ======================================================================

@sqlite_only
@pytest.mark.asyncio
async def test_sqlite_connections_have_foreign_keys_enabled():
    async with engine.connect() as conn:
        assert (await conn.execute(text("PRAGMA foreign_keys"))).scalar() == 1

    # A pooled ORM session must get the same treatment, not just a raw connect.
    async with AsyncSessionLocal() as session:
        assert (await session.execute(text("PRAGMA foreign_keys"))).scalar() == 1


# ======================================================================
# 2. An invalid foreign key is rejected by the database itself
# ======================================================================

@sqlite_only
@pytest.mark.asyncio
async def test_invalid_foreign_key_insert_is_rejected():
    async with AsyncSessionLocal() as session:
        session.add(DocumentChunk(
            document_id=ORPHAN_DOCUMENT_ID,
            chunk_index=0,
            chunk_text="Points at no document",
            metadata_json={},
            embedding_json=[0.1, 0.2],
        ))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


# ======================================================================
# 3 + 4. VectorStore's rollback path runs and leaves nothing behind
# ======================================================================

@sqlite_only
@pytest.mark.asyncio
async def test_vector_store_rollback_leaves_no_partial_rows():
    async with AsyncSessionLocal() as session:
        vs = VectorStore(session)

        with pytest.raises(VectorStoreError):
            await vs.add_chunk(
                document_id=ORPHAN_DOCUMENT_ID,
                chunk_index=0,
                chunk_text="Will fail",
            )

        # The failed unit of work must not survive as a partial row.
        assert session.in_transaction() is False, "session left inside a dead transaction"

    async with AsyncSessionLocal() as verify:
        orphans = (await verify.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == ORPHAN_DOCUMENT_ID)
        )).scalars().all()
        assert orphans == []


# ======================================================================
# 5. A failure does not poison the session it happened on
# ======================================================================

@sqlite_only
@pytest.mark.asyncio
async def test_valid_write_still_succeeds_after_a_failed_one():
    async with AsyncSessionLocal() as session:
        vs = VectorStore(session)

        with pytest.raises(VectorStoreError):
            await vs.add_chunk(
                document_id=ORPHAN_DOCUMENT_ID,
                chunk_index=0,
                chunk_text="Will fail",
            )

        document = await _make_document(session)
        chunk = await vs.add_chunk(
            document_id=document.id,
            chunk_index=0,
            chunk_text="Valid chunk after a rolled-back failure",
        )
        assert chunk.id is not None
        assert chunk.document_id == document.id

    async with AsyncSessionLocal() as verify:
        stored = (await verify.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk.id)
        )).scalar_one()
        assert stored.chunk_text == "Valid chunk after a rolled-back failure"


# ======================================================================
# 6. PostgreSQL / application-runtime behaviour is untouched
# ======================================================================

def test_pragma_helper_is_a_no_op_for_non_sqlite_engines():
    """A dedicated Postgres test database must keep its native behaviour."""
    from sqlalchemy.engine.url import make_url

    class _FakeEngine:
        url = make_url("postgresql+asyncpg://user:pw@localhost:5432/ai_interviewer_test")

    assert root_conftest().enable_sqlite_foreign_keys(_FakeEngine()) is False


def test_application_database_module_registers_no_pragma():
    """The PRAGMA lives in the test conftest, never in application runtime code."""
    source = (Path(__file__).resolve().parents[1] / "app" / "core" / "database.py").read_text(
        encoding="utf-8"
    )
    assert "PRAGMA" not in source
    assert "listens_for" not in source
    assert "event.listen" not in source


def test_postgres_schema_still_declares_the_foreign_key():
    """Rendered offline from the models -- no connection of any kind."""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    ddl = str(CreateTable(Base.metadata.tables["document_chunks"]).compile(
        dialect=postgresql.dialect()
    ))
    assert "FOREIGN KEY(document_id) REFERENCES documents (id)" in ddl


# ======================================================================
# 7. The database safety guard is unchanged
# ======================================================================

@pytest.mark.parametrize("url", [
    "postgresql+asyncpg://user:pw@localhost:5432/ai_interviewer_db",
    "postgresql://user:pw@prod-host/ai_interviewer",
    "postgresql+asyncpg://test:test@testhost/ai_interviewer_db",
    "",
])
def test_guard_still_rejects_non_test_databases(url):
    assert root_conftest().is_safe_test_database_url(url) is False


@pytest.mark.parametrize("url", [
    "sqlite+aiosqlite:///C:/tmp/throwaway.sqlite",
    "postgresql+asyncpg://user:pw@localhost:5432/ai_interviewer_test",
    "postgresql+asyncpg://user:pw@localhost:5432/test_ai_interviewer",
])
def test_guard_still_accepts_dedicated_test_databases(url):
    assert root_conftest().is_safe_test_database_url(url) is True


def test_session_is_bound_to_an_isolated_test_database():
    assert root_conftest().is_safe_test_database_url(
        engine.url.render_as_string(hide_password=True)
    ) is True
    assert (engine.url.database or "") != "ai_interviewer_db"
