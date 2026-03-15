"""
Manual collection trigger.

Runs a single YouTube collection cycle outside of the APScheduler schedule.
Useful for testing the collector locally, populating data immediately after
seeding, or debugging collection issues.

Usage:
    uv run python scripts/collect.py

Run from the project root directory. Requires DATABASE_URL and
YOUTUBE_API_KEY to be set (either in .env or the environment).
"""

import asyncio
import logging
import sys
import time

import asyncpg

# Ensure src/ is importable when running from the project root.
sys.path.insert(0, ".")

from src.config import DATABASE_URL, YOUTUBE_API_KEY
from src.collector.youtube import YouTubeCollector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run one full collection cycle and report results."""
    if not YOUTUBE_API_KEY:
        print(
            "\nWARNING: YOUTUBE_API_KEY is not set.\n"
            "The collector will run but skip all API calls.\n"
            "Set YOUTUBE_API_KEY in your .env file to collect real data.\n"
        )

    print(f"\nConnecting to database: {DATABASE_URL!r}")
    pool: asyncpg.Pool = await asyncpg.create_pool(DATABASE_URL)

    try:
        collector = YouTubeCollector(pool=pool, api_key=YOUTUBE_API_KEY)

        print("Starting collection cycle...\n")
        start = time.monotonic()

        try:
            count = await collector.collect()
        except Exception as exc:
            logger.error("Collection cycle failed: %s", exc)
            sys.exit(1)

        elapsed = time.monotonic() - start

        print(f"\n{'─' * 40}")
        print(f"  Videos collected : {count}")
        print(f"  Elapsed          : {elapsed:.1f}s")
        print(f"{'─' * 40}\n")

        if count == 0:
            print(
                "No videos were collected. Possible reasons:\n"
                "  • No channels have been seeded yet  →  run scripts/seed.py\n"
                "  • YOUTUBE_API_KEY is missing or invalid\n"
                "  • The configured channels have no recent uploads\n"
            )

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
