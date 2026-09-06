"""Test-session database safety.

pytest imports this root conftest before ``tests/conftest.py``. That is the only
window in which ``DATABASE_URL`` can still be redirected: ``app.core.database``
builds its engine at *import* time from ``app.core.config.settings``, and
``tests/conftest.py`` imports that engine at module level.

Without this file a bare ``pytest`` run targets whatever ``DATABASE_URL`` the
developer's ``.env`` points at, and ``pytest_sessionfinish`` then calls
``cleanup_database()``, which issues DELETE cascades against it.

Selection order:

1. ``AI_INTERVIEWER_TEST_DATABASE_URL`` -- use a dedicated test database
   (its name must satisfy :func:`is_safe_test_database_url`).
2. An existing ``DATABASE_URL`` that is already a safe test database.
3. Otherwise a unique throwaway SQLite file, removed when the session ends.

The guard in :func:`pytest_sessionstart` is the fail-safe: whatever the engine
ends up bound to, the session aborts before any test runs unless that database
is recognisably a test database.
"""

from __future__ import annotations

import atexit
import os
import tempfile
import uuid

import pytest

TEST_DATABASE_URL_ENV = "AI_INTERVIEWER_TEST_DATABASE_URL"


def is_safe_test_database_url(url: str) -> bool:
    """True only for databases it is safe to create, mutate and delete data in.

    SQLite is always throwaway. Any server-backed database must name itself a
    test database, so a development or production URL can never qualify.
    """
    if not url:
        return False

    # Parsed rather than string-matched so credentials or hosts containing
    # "test" cannot smuggle an unsafe database past the guard.
    try:
        from sqlalchemy.engine.url import make_url

        parsed = make_url(url)
    except Exception:
        return False

    if parsed.drivername.startswith("sqlite"):
        return True

    database = (parsed.database or "").lower()
    return database.endswith("_test") or database.startswith("test_") or database == "test"


def _provision_test_database_url() -> None:
    explicit = os.environ.get(TEST_DATABASE_URL_ENV, "").strip()
    if explicit:
        os.environ["DATABASE_URL"] = explicit
        return

    current = os.environ.get("DATABASE_URL", "").strip()
    if current and is_safe_test_database_url(current):
        # An already-safe override (e.g. CI) is respected as-is.
        return

    path = os.path.join(
        tempfile.gettempdir(), f"ai_interviewer_test_{uuid.uuid4().hex}.sqlite"
    )
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{path}"

    @atexit.register
    def _remove_throwaway_database() -> None:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


_provision_test_database_url()


def enable_sqlite_foreign_keys(engine) -> bool:
    """Make a SQLite test engine enforce the schema's foreign keys.

    SQLite leaves foreign-key enforcement off on every new connection unless the
    ``foreign_keys`` PRAGMA is set, while PostgreSQL -- for which the same
    ``Base.metadata`` renders ``FOREIGN KEY ... REFERENCES`` DDL -- always
    enforces them. Left off, the throwaway database silently accepts rows the
    production database would reject, so a test asserting a constraint violation
    can never observe one.

    Registered on the *test* engine only: ``app.core.database`` is untouched and
    application runtime behaviour is unchanged. Returns False without doing
    anything for a non-SQLite engine, so a dedicated PostgreSQL test database
    keeps its native behaviour.
    """
    if not engine.url.drivername.startswith("sqlite"):
        return False

    from sqlalchemy import event

    # An AsyncEngine emits pool events through the sync engine it wraps.
    target = getattr(engine, "sync_engine", engine)

    @event.listens_for(target, "connect")
    def _set_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return True


def pytest_sessionstart(session):
    """Abort before any test runs if the engine is not bound to a test database."""
    from app.core.database import engine

    url = engine.url
    if is_safe_test_database_url(url.render_as_string(hide_password=True)):
        # Make the bound database visible in test output; never print credentials.
        print(f"\n[test-db] {url.drivername} :: {url.database}")
        if enable_sqlite_foreign_keys(engine):
            print("[test-db] sqlite foreign-key enforcement: ON")
        return

    pytest.exit(
        "Refusing to run the test suite against a non-test database.\n"
        f"  driver:   {url.drivername}\n"
        f"  host:     {url.host}\n"
        f"  database: {url.database}\n"
        "This suite creates, mutates and deletes rows, and its session teardown\n"
        "runs DELETE cascades. Point it at a dedicated test database via\n"
        f"  {TEST_DATABASE_URL_ENV}=postgresql+asyncpg://.../<name>_test\n"
        "or unset DATABASE_URL to use an automatic throwaway SQLite database.",
        returncode=4,
    )


def pytest_sessionfinish(session, exitstatus):
    """Release the engine's connections so a throwaway file can be deleted.

    On Windows the open SQLite handle otherwise blocks the atexit removal.
    """
    try:
        import asyncio

        from app.core.database import engine

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(engine.dispose())
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    except Exception:
        pass
