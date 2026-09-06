"""Module 2C: Background JD Refresh Scheduler.

Registers an asyncio background task on FastAPI startup that refreshes
JD cache entries every 24 hours for the company/role combinations stored in
the database.

Registration: call `start_background_scraper(app, db_factory)` in main.py startup.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional, Any

logger = logging.getLogger("ai_interviewer.background_scraper")

_scraper_task: Optional[asyncio.Task] = None  # module-level handle for graceful shutdown

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
