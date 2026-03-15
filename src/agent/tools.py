"""
Agent tools — database query wrappers.

Each function here is a Pydantic AI tool. Tools take a RunContext[Pool]
as their first argument; Pydantic AI injects the dependency automatically
at call time. All data access goes through src.db.queries — no raw SQL
and no direct HTTP calls are permitted in this module.

This module must not import apscheduler, httpx, or any collector dependency.
"""

import logging

from asyncpg import Pool
from pydantic_ai import RunContext

from src.db.queries import ChannelStats, VideoSummary, get_channel_stats, get_videos, search_videos

logger = logging.getLogger(__name__)


async def query_recent_videos(
    ctx: RunContext[Pool],
    channel_id: str,
    limit: int = 10,
) -> list[VideoSummary]:
    """Fetch the most recently published videos for a YouTube channel.

    Use this tool when the user asks about recent uploads, latest content,
    or what a specific channel has been posting.

    Args:
        ctx: Injected run context carrying the database pool.
        channel_id: YouTube channel identifier (e.g. ``UCxxxxxx``).
        limit: Maximum number of videos to return (default 10, max 50).

    Returns:
        List of video summaries ordered by publish date descending.
    """
    limit = min(limit, 50)
    logger.debug("Tool: query_recent_videos", extra={"channel_id": channel_id, "limit": limit})
    return await get_videos(ctx.deps, channel_id, limit)


async def search_videos_by_query(
    ctx: RunContext[Pool],
    query: str,
    limit: int = 10,
) -> list[VideoSummary]:
    """Search collected videos by title and description keywords.

    Use this tool when the user asks about a specific topic, subject, or
    keyword across all channels rather than a specific channel's uploads.

    Args:
        ctx: Injected run context carrying the database pool.
        query: Search keywords or phrase to match against video titles
               and descriptions.
        limit: Maximum number of results to return (default 10).

    Returns:
        List of matching video summaries ordered by relevance.
    """
    logger.debug("Tool: search_videos_by_query", extra={"query": query})
    return await search_videos(ctx.deps, query, limit)


async def get_channel_statistics(
    ctx: RunContext[Pool],
    channel_id: str,
) -> ChannelStats | None:
    """Return aggregate statistics for a YouTube channel.

    Use this tool when the user asks about a channel's overall performance,
    total view counts, video count, or most recent upload date.

    Args:
        ctx: Injected run context carrying the database pool.
        channel_id: YouTube channel identifier (e.g. ``UCxxxxxx``).

    Returns:
        Aggregated channel stats, or None if the channel is not tracked.
    """
    logger.debug("Tool: get_channel_statistics", extra={"channel_id": channel_id})
    return await get_channel_stats(ctx.deps, channel_id)
