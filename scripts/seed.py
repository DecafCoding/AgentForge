"""
Seed script — populate initial YouTube channel data.

Inserts one or more YouTube channels into the database so the collector
has something to work with. Channel names are resolved via the YouTube
Data API if YOUTUBE_API_KEY is configured; otherwise the channel ID is
used as a placeholder name.

Usage:
    uv run python scripts/seed.py UCxxxxxx UCyyyyyy
    uv run python scripts/seed.py UCxxxxxx --name "My Channel"

Run from the project root directory.
"""

import argparse
import asyncio
import logging
import sys

import asyncpg

# Ensure src/ is importable when running from the project root.
sys.path.insert(0, ".")

from src.config import DATABASE_URL, YOUTUBE_API_KEY
from src.db.queries import upsert_channel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def resolve_channel_name(channel_id: str) -> str:
    """Look up a channel's display name via the YouTube Data API.

    Falls back to the channel_id if the API key is missing or the lookup
    fails — the name can always be corrected by re-running seed.py.

    Args:
        channel_id: YouTube channel identifier (e.g. ``UCxxxxxx``).

    Returns:
        Display name, or the channel_id if resolution is not possible.
    """
    if not YOUTUBE_API_KEY:
        return channel_id

    try:
        import asyncio

        from googleapiclient.discovery import build

        def _fetch() -> str:
            client = build(
                "youtube", "v3", developerKey=YOUTUBE_API_KEY, cache_discovery=False
            )
            response = (
                client.channels().list(part="snippet", id=channel_id).execute()
            )
            items = response.get("items", [])
            if not items:
                return channel_id
            return items[0]["snippet"]["title"]

        return await asyncio.to_thread(_fetch)
    except Exception as exc:
        logger.warning(
            "Could not resolve name for %s (%s) — using channel_id as name.",
            channel_id,
            exc,
        )
        return channel_id


async def main(channel_ids: list[str], override_name: str | None) -> None:
    """Seed channels into the database.

    Args:
        channel_ids: List of YouTube channel identifiers to insert.
        override_name: If provided, used as the name for every channel
                       (only makes sense when seeding a single channel).
    """
    if not channel_ids:
        logger.error("No channel IDs provided. Pass at least one channel ID.")
        sys.exit(1)

    pool: asyncpg.Pool = await asyncpg.create_pool(DATABASE_URL)

    try:
        for channel_id in channel_ids:
            name = override_name or await resolve_channel_name(channel_id)
            await upsert_channel(pool, channel_id=channel_id, channel_name=name)
            print(f"  ✓ {channel_id}  →  {name}")

        print(f"\nSeeded {len(channel_ids)} channel(s) successfully.")
    finally:
        await pool.close()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Seed YouTube channel IDs into the AgentForge database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run python scripts/seed.py UCxxxxxx\n"
            "  uv run python scripts/seed.py UCxxxxxx UCyyyyyy\n"
            "  uv run python scripts/seed.py UCxxxxxx --name 'My Channel'\n"
        ),
    )
    parser.add_argument(
        "channel_ids",
        nargs="+",
        metavar="CHANNEL_ID",
        help="YouTube channel ID(s) to seed (e.g. UCxxxxxx).",
    )
    parser.add_argument(
        "--name",
        metavar="NAME",
        default=None,
        help=(
            "Override the channel display name. Useful when seeding a single "
            "channel without a YouTube API key configured."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(f"\nSeeding {len(args.channel_ids)} channel(s) into {DATABASE_URL!r}...\n")
    asyncio.run(main(args.channel_ids, args.name))
