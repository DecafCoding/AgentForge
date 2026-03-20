"""
Seed script — populate initial YouTube channel data.

Inserts one or more YouTube channels into the database so the collector
has something to work with. Accepts channel IDs (``UCxxxxxx``) or YouTube
handles (``@NathsServer``). Handles are resolved to channel IDs via the
YouTube Data API. Channel names are resolved from the API if
YOUTUBE_API_KEY is configured; otherwise the channel ID is used as a
placeholder name.

Usage:
    uv run python scripts/seed.py UCxxxxxx UCyyyyyy
    uv run python scripts/seed.py @NathsServer @Fireship
    uv run python scripts/seed.py UCxxxxxx @NathsServer
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


async def resolve_handle(handle: str) -> str | None:
    """Resolve a YouTube handle (e.g. ``@NathsServer``) to a channel ID.

    Uses the YouTube Data API v3 ``channels.list`` endpoint with the
    ``forHandle`` parameter. Requires YOUTUBE_API_KEY to be set.

    Args:
        handle: YouTube handle including the ``@`` prefix.

    Returns:
        The ``UCxxxxxx`` channel ID, or None if resolution fails.
    """
    if not YOUTUBE_API_KEY:
        logger.error(
            "YOUTUBE_API_KEY is required to resolve handles. "
            "Set it in your .env or pass a UC-prefixed channel ID directly."
        )
        return None

    try:
        from googleapiclient.discovery import build

        # Strip leading @ for the API — it accepts both forms but is more
        # reliable without it.
        handle_param = handle.lstrip("@")

        def _fetch() -> str | None:
            client = build(
                "youtube", "v3", developerKey=YOUTUBE_API_KEY, cache_discovery=False
            )
            response = (
                client.channels().list(part="snippet", forHandle=handle_param).execute()
            )
            items = response.get("items", [])
            if not items:
                return None
            return items[0]["id"]

        return await asyncio.to_thread(_fetch)
    except Exception as exc:
        logger.error("Failed to resolve handle %s: %s", handle, exc)
        return None


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
        from googleapiclient.discovery import build

        def _fetch() -> str:
            client = build(
                "youtube", "v3", developerKey=YOUTUBE_API_KEY, cache_discovery=False
            )
            response = client.channels().list(part="snippet", id=channel_id).execute()
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


async def resolve_input(raw: str) -> tuple[str, str] | None:
    """Resolve a raw user input to a (channel_id, channel_name) pair.

    Accepts either a UC-prefixed channel ID or an @-prefixed handle.
    Returns None if resolution fails so the caller can skip the entry.

    Args:
        raw: A channel ID (``UCxxxxxx``) or handle (``@NathsServer``).

    Returns:
        Tuple of (channel_id, channel_name), or None on failure.
    """
    if raw.startswith("@"):
        print(f"  Resolving handle {raw!r} ...")
        channel_id = await resolve_handle(raw)
        if channel_id is None:
            logger.error("Could not resolve handle %r — skipping.", raw)
            return None
    else:
        channel_id = raw

    channel_name = await resolve_channel_name(channel_id)
    return channel_id, channel_name


async def main(inputs: list[str], override_name: str | None) -> None:
    """Seed channels into the database.

    Args:
        inputs: List of channel IDs or handles to insert.
        override_name: If provided, used as the name for every channel
                       (only makes sense when seeding a single channel).
    """
    if not inputs:
        logger.error("No channel IDs or handles provided.")
        sys.exit(1)

    pool: asyncpg.Pool = await asyncpg.create_pool(DATABASE_URL)

    seeded = 0
    try:
        for raw in inputs:
            resolved = await resolve_input(raw)
            if resolved is None:
                continue
            channel_id, channel_name = resolved
            name = override_name or channel_name
            await upsert_channel(pool, channel_id=channel_id, channel_name=name)
            print(f"  ✓ {raw}  →  {channel_id}  ({name})")
            seeded += 1

        print(f"\nSeeded {seeded} of {len(inputs)} channel(s) successfully.")
    finally:
        await pool.close()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Seed YouTube channels into the AgentForge database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run python scripts/seed.py UCxxxxxx\n"
            "  uv run python scripts/seed.py @NathsServer\n"
            "  uv run python scripts/seed.py UCxxxxxx @NathsServer\n"
            "  uv run python scripts/seed.py UCxxxxxx --name 'My Channel'\n"
        ),
    )
    parser.add_argument(
        "channels",
        nargs="+",
        metavar="CHANNEL",
        help="Channel ID (UCxxxxxx) or handle (@name) to seed.",
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
    print(f"\nSeeding {len(args.channels)} channel(s) into {DATABASE_URL!r}...\n")
    asyncio.run(main(args.channels, args.name))
