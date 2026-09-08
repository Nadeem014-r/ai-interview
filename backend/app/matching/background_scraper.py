"""Module 2C: Background JD Refresh Scheduler.

Registers an asyncio background task on FastAPI startup that refreshes
JD cache entries every 24 hours for the company/role combinations stored in
the database.

Registration: call `start_background_scraper(app, db_factory)` in main.py startup.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import logging
from typing import Callable, Optional, Any

logger = logging.getLogger("ai_interviewer.background_scraper")

_scraper_task: Optional[asyncio.Task] = None  # module-level handle for graceful shutdown
_lock_handle = None  # held for the process lifetime while this worker owns the loop

# Source.source_type values that denote a job description. "official_job_desc"
# is what app/research/pipeline.py records; "job_desc" is the value documented
# on the Source model itself.
_JD_SOURCE_TYPES = ("official_job_desc", "job_desc")


async def _scrape_all_active_roles(db_factory: Callable) -> None:
    """Fetch roles from DB and refresh their JD cache entries.

    The Role model carries no activity flag, so every stored role is refreshed.
    """
    try:
        from app.matching.jd_scraper import JDScrapingService
        from sqlalchemy import select
        from app.db.models import Role, Company, Source

        async with db_factory() as db:
            stmt = (
                select(Role, Company)
                .join(Company, Role.company_id == Company.id)
            )
            result = await db.execute(stmt)
            rows = result.all()

            # Role has no jd_url column; job-description URLs live in the
            # sources table. Resolve them in one query keyed by role, keeping
            # the most recently fetched URL per role.
            jd_rows = (
                await db.execute(
                    select(Source.role_id, Source.source_url)
                    .where(Source.role_id.is_not(None))
                    .where(Source.source_type.in_(_JD_SOURCE_TYPES))
                    .order_by(Source.fetched_at.asc())
                )
            ).all()
            jd_urls = {role_id: url for role_id, url in jd_rows}

        if not rows:
            logger.info("BackgroundScraper: no roles found, skipping cycle.")
            return

        logger.info(f"BackgroundScraper: refreshing JD cache for {len(rows)} roles.")
        for role, company in rows:
            try:
                await JDScrapingService.scrape(
                    company_name=company.name,
                    role_title=role.title,
                    jd_url=jd_urls.get(role.id),
                )
                logger.debug(f"BackgroundScraper: refreshed '{company.name} / {role.title}'")
            except Exception as exc:
                logger.warning(
                    f"BackgroundScraper: failed to scrape '{company.name} / {role.title}': {exc}"
                )

    except Exception as exc:
        logger.error(f"BackgroundScraper: cycle failed: {exc}", exc_info=True)


async def _run_scraper_loop(db_factory: Callable, interval_hours: float = 24.0) -> None:
    """Infinite loop that runs the scraper cycle every `interval_hours`."""
    interval_seconds = interval_hours * 3600
    logger.info(
        f"BackgroundScraper started. Refresh interval: {interval_hours}h."
    )

    # Initial run after a short startup delay to avoid blocking
    await asyncio.sleep(30)

    while True:
        await _scrape_all_active_roles(db_factory)
        logger.info(
            f"BackgroundScraper: cycle complete. Next refresh in {interval_hours}h."
        )
        await asyncio.sleep(interval_seconds)


def _scraper_enabled() -> bool:
    """Whether periodic JD scraping should run at all.

    A demo or offline deployment can set ENABLE_BACKGROUND_SCRAPER=false to skip
    the recurring outbound HTTP traffic and database writes entirely.
    """
    return os.getenv("ENABLE_BACKGROUND_SCRAPER", "true").strip().lower() not in ("0", "false", "no")


def _acquire_single_instance_lock() -> bool:
    """True when this process should own the scrape loop.

    The loop was started from the FastAPI startup event, so every Uvicorn worker
    ran its own copy: N workers meant N identical scrape cycles, N times the
    outbound requests and N times the writes for the same rows. An advisory file
    lock held for the process lifetime keeps exactly one owner per host, and the
    OS releases it automatically if that process dies.

    Fails open (returns True) where no lock is available, so behaviour is never
    worse than before.
    """
    global _lock_handle
    try:
        import fcntl  # POSIX only; Windows development falls through to fail-open
    except ImportError:
        return True

    lock_path = os.getenv(
        "BACKGROUND_SCRAPER_LOCK",
        os.path.join(tempfile.gettempdir(), "ai_interviewer_jd_scraper.lock"),
    )
    try:
        handle = open(lock_path, "w")
    except OSError as exc:
        logger.warning(f"BackgroundScraper: cannot open lock file ({exc}); running unguarded.")
        return True

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False          # held by another worker -- expected, stay quiet
    except Exception as exc:  # pragma: no cover - unexpected platform behaviour
        handle.close()
        logger.warning(f"BackgroundScraper: lock unavailable ({exc}); running unguarded.")
        return True

    _lock_handle = handle
    return True


def start_background_scraper(db_factory: Callable, interval_hours: float = 24.0) -> None:
    """
    Start the background JD scraper as an asyncio Task.
    Call this from the FastAPI startup event handler.

    Args:
        db_factory: Async context-manager factory for DB sessions
                    (e.g., AsyncSessionLocal from app.core.database).
        interval_hours: How often to refresh (default: 24h).
    """
    global _scraper_task

    if not _scraper_enabled():
        logger.info(
            "BackgroundScraper: disabled via ENABLE_BACKGROUND_SCRAPER; "
            "no periodic JD scraping will run."
        )
        return

    if not _acquire_single_instance_lock():
        logger.info(
            "BackgroundScraper: another worker on this host already owns the "
            "scrape loop; not starting a duplicate."
        )
        return

    try:
        loop = asyncio.get_event_loop()
        _scraper_task = loop.create_task(
            _run_scraper_loop(db_factory, interval_hours),
            name="jd_background_scraper",
        )
        logger.info("BackgroundScraper: asyncio task created.")
    except Exception as exc:
        logger.warning(f"BackgroundScraper: could not start task: {exc}")


def stop_background_scraper() -> None:
    """Cancel the background scraper task on shutdown."""
    global _scraper_task
    if _scraper_task and not _scraper_task.done():
        _scraper_task.cancel()
        logger.info("BackgroundScraper: task cancelled.")
