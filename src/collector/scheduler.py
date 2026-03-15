"""
APScheduler integration for the collector layer.

Sets up an AsyncScheduler (APScheduler 4.x) and registers collector jobs.
The scheduler is started and stopped by the FastAPI lifespan hook in
src/api/main.py — nothing else should call these functions directly.

This module must not import pydantic_ai, langfuse, or any LLM dependency.
"""

import logging

from apscheduler import AsyncScheduler
from apscheduler.triggers.interval import IntervalTrigger
from asyncpg import Pool

from src.collector.youtube import YouTubeCollector
from src.config import COLLECTION_INTERVAL_MINUTES, YOUTUBE_API_KEY

logger = logging.getLogger(__name__)

# Module-level scheduler instance, managed by start/shutdown functions.
_scheduler: AsyncScheduler | None = None


async def start_scheduler(pool: Pool) -> None:
    """Start the APScheduler background scheduler and register collector jobs.

    Creates a YouTubeCollector bound to the provided pool and schedules it
    to run at the configured interval. The scheduler runs in the background
    alongside the FastAPI event loop.

    Args:
        pool: asyncpg connection pool passed through from app startup.
    """
    global _scheduler

    collector = YouTubeCollector(pool=pool, api_key=YOUTUBE_API_KEY)

    _scheduler = AsyncScheduler()
    await _scheduler.start_in_background()

    await _scheduler.add_schedule(
        collector.collect,
        IntervalTrigger(minutes=COLLECTION_INTERVAL_MINUTES),
        id="youtube_collector",
    )

    logger.info(
        "Scheduler started",
        extra={"interval_minutes": COLLECTION_INTERVAL_MINUTES},
    )


async def shutdown_scheduler() -> None:
    """Stop the APScheduler background scheduler gracefully."""
    global _scheduler

    if _scheduler is not None:
        await _scheduler.stop()
        _scheduler = None
        logger.info("Scheduler stopped")
