"""
Database query functions.

All SQL in the application lives here. Collectors and agents call these
typed async functions — no raw SQL is permitted outside this module. Every
function accepts an asyncpg Pool and returns typed Pydantic models, never
raw rows or dicts. This module belongs to the Data Layer.
"""

import logging
from datetime import datetime
from uuid import UUID

from asyncpg import Pool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models — reflect the database schema exactly
# ---------------------------------------------------------------------------


class ChannelRecord(BaseModel):
    """A YouTube channel row from the youtube_channels table."""

    id: UUID
    channel_id: str
    channel_name: str
    created_at: datetime


class VideoRecord(BaseModel):
    """A YouTube video row from the youtube_videos table.

    The ``embedding`` column is excluded from all queries in this module;
    it will be populated and queried separately once vector search is wired up.
    """

    id: UUID
    video_id: str
    channel_id: str
    title: str
    description: str | None = None
    published_at: datetime | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    duration: str | None = None
    transcript: str | None = None
    collected_at: datetime
    updated_at: datetime


class VideoSummary(BaseModel):
    """Lightweight video projection used by agent tools.

    Contains only the fields the agent needs to construct a response,
    keeping token usage low.
    """

    video_id: str
    channel_id: str
    title: str
    published_at: datetime | None = None
    view_count: int | None = None
    url: str = Field(default="")

    def model_post_init(self, __context: object) -> None:
        """Derive the YouTube watch URL from video_id."""
        if not self.url:
            self.url = f"https://www.youtube.com/watch?v={self.video_id}"


class ChannelStats(BaseModel):
    """Aggregate statistics for a single YouTube channel."""

    channel_id: str
    channel_name: str
    video_count: int
    total_views: int
    latest_video_at: datetime | None = None


# ---------------------------------------------------------------------------
# Channel queries
# ---------------------------------------------------------------------------


async def get_channels(pool: Pool) -> list[ChannelRecord]:
    """Return all tracked YouTube channels ordered by creation date."""
    rows = await pool.fetch(
        "SELECT id, channel_id, channel_name, created_at "
        "FROM youtube_channels ORDER BY created_at ASC",
    )
    return [ChannelRecord(**dict(row)) for row in rows]


async def upsert_channel(pool: Pool, channel_id: str, channel_name: str) -> None:
    """Insert a channel or update its name if the channel_id already exists.

    Args:
        pool: asyncpg connection pool.
        channel_id: YouTube channel identifier (e.g. ``UCxxxxxx``).
        channel_name: Human-readable display name of the channel.
    """
    await pool.execute(
        """
        INSERT INTO youtube_channels (channel_id, channel_name)
        VALUES ($1, $2)
        ON CONFLICT (channel_id) DO UPDATE SET channel_name = EXCLUDED.channel_name
        """,
        channel_id,
        channel_name,
    )
    logger.debug("Upserted channel", extra={"channel_id": channel_id})


# ---------------------------------------------------------------------------
# Video queries
# ---------------------------------------------------------------------------


async def get_videos(
    pool: Pool,
    channel_id: str,
    limit: int = 20,
) -> list[VideoRecord]:
    """Fetch the most recent videos for a channel.

    Args:
        pool: asyncpg connection pool.
        channel_id: YouTube channel identifier.
        limit: Maximum number of videos to return.

    Returns:
        List of video records ordered by published date descending.
    """
    rows = await pool.fetch(
        """
        SELECT id, video_id, channel_id, title, description,
               published_at, view_count, like_count, comment_count,
               duration, transcript, collected_at, updated_at
        FROM youtube_videos
        WHERE channel_id = $1
        ORDER BY published_at DESC
        LIMIT $2
        """,
        channel_id,
        limit,
    )
    return [VideoRecord(**dict(row)) for row in rows]


async def search_videos(pool: Pool, query: str, limit: int = 10) -> list[VideoSummary]:
    """Search videos by title and description using full-text search.

    Args:
        pool: asyncpg connection pool.
        query: Search terms to match against title and description.
        limit: Maximum number of results to return.

    Returns:
        List of matching video summaries ordered by relevance.
    """
    rows = await pool.fetch(
        """
        SELECT video_id, channel_id, title, published_at, view_count
        FROM youtube_videos
        WHERE to_tsvector('english', title || ' ' || COALESCE(description, ''))
              @@ plainto_tsquery('english', $1)
        ORDER BY published_at DESC
        LIMIT $2
        """,
        query,
        limit,
    )
    return [VideoSummary(**dict(row)) for row in rows]


async def get_channel_stats(pool: Pool, channel_id: str) -> ChannelStats | None:
    """Return aggregate statistics for a single channel.

    Args:
        pool: asyncpg connection pool.
        channel_id: YouTube channel identifier.

    Returns:
        Aggregated stats, or None if the channel does not exist.
    """
    row = await pool.fetchrow(
        """
        SELECT
            c.channel_id,
            c.channel_name,
            COUNT(v.id)::int          AS video_count,
            COALESCE(SUM(v.view_count), 0)::int AS total_views,
            MAX(v.published_at)       AS latest_video_at
        FROM youtube_channels c
        LEFT JOIN youtube_videos v ON v.channel_id = c.channel_id
        WHERE c.channel_id = $1
        GROUP BY c.channel_id, c.channel_name
        """,
        channel_id,
    )
    if row is None:
        return None
    return ChannelStats(**dict(row))


async def upsert_video(
    pool: Pool,
    video_id: str,
    channel_id: str,
    title: str,
    description: str | None,
    published_at: datetime | None,
    view_count: int | None,
    like_count: int | None,
    comment_count: int | None,
    duration: str | None,
    transcript: str | None,
) -> None:
    """Insert a video or update its metadata if the video_id already exists.

    Args:
        pool: asyncpg connection pool.
        video_id: YouTube video identifier.
        channel_id: Parent channel identifier (must exist in youtube_channels).
        title: Video title.
        description: Video description text.
        published_at: UTC publish timestamp.
        view_count: View count at collection time.
        like_count: Like count at collection time.
        comment_count: Comment count at collection time.
        duration: ISO 8601 duration string (e.g. ``PT4M13S``).
        transcript: Full video transcript text, if available.
    """
    await pool.execute(
        """
        INSERT INTO youtube_videos (
            video_id, channel_id, title, description, published_at,
            view_count, like_count, comment_count, duration, transcript
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (video_id) DO UPDATE SET
            title         = EXCLUDED.title,
            description   = EXCLUDED.description,
            view_count    = EXCLUDED.view_count,
            like_count    = EXCLUDED.like_count,
            comment_count = EXCLUDED.comment_count,
            duration      = EXCLUDED.duration,
            transcript    = EXCLUDED.transcript,
            updated_at    = NOW()
        """,
        video_id,
        channel_id,
        title,
        description,
        published_at,
        view_count,
        like_count,
        comment_count,
        duration,
        transcript,
    )
    logger.debug("Upserted video", extra={"video_id": video_id})


# ---------------------------------------------------------------------------
# Scraped page queries
# ---------------------------------------------------------------------------


class ScrapedPageRecord(BaseModel):
    """A scraped web page row from the scraped_pages table."""

    id: UUID
    url: str
    title: str | None = None
    content: str | None = None
    metadata: dict = Field(default_factory=dict)
    scraped_at: datetime


async def upsert_scraped_page(
    pool: Pool,
    url: str,
    title: str | None,
    content: str | None,
    metadata: dict | None = None,
) -> None:
    """Insert a scraped page or update its content if the URL already exists.

    Args:
        pool: asyncpg connection pool.
        url: Page URL (unique key).
        title: Page title extracted from metadata.
        content: Page content as markdown text.
        metadata: Additional page metadata as JSON.
    """
    import json

    await pool.execute(
        """
        INSERT INTO scraped_pages (url, title, content, metadata, scraped_at)
        VALUES ($1, $2, $3, $4::jsonb, NOW())
        ON CONFLICT (url) DO UPDATE SET
            title      = EXCLUDED.title,
            content    = EXCLUDED.content,
            metadata   = EXCLUDED.metadata,
            scraped_at = NOW()
        """,
        url,
        title,
        content,
        json.dumps(metadata or {}),
    )
    logger.debug("Upserted scraped page", extra={"url": url})


async def search_scraped_pages(
    pool: Pool,
    query: str,
    limit: int = 10,
) -> list[ScrapedPageRecord]:
    """Search scraped pages by title and content using full-text search.

    Args:
        pool: asyncpg connection pool.
        query: Search terms to match against title and content.
        limit: Maximum number of results.

    Returns:
        List of matching scraped page records.
    """
    rows = await pool.fetch(
        """
        SELECT id, url, title, content, metadata, scraped_at
        FROM scraped_pages
        WHERE to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(content, ''))
              @@ plainto_tsquery('english', $1)
        ORDER BY scraped_at DESC
        LIMIT $2
        """,
        query,
        limit,
    )
    return [ScrapedPageRecord(**dict(row)) for row in rows]


async def get_scraped_page(pool: Pool, url: str) -> ScrapedPageRecord | None:
    """Fetch a single scraped page by URL.

    Args:
        pool: asyncpg connection pool.
        url: The page URL to look up.

    Returns:
        The scraped page record, or None if not found.
    """
    row = await pool.fetchrow(
        "SELECT id, url, title, content, metadata, scraped_at "
        "FROM scraped_pages WHERE url = $1",
        url,
    )
    if row is None:
        return None
    return ScrapedPageRecord(**dict(row))


# ---------------------------------------------------------------------------
# Evaluation run queries
# ---------------------------------------------------------------------------


class EvaluationRunRecord(BaseModel):
    """A row from the evaluation_runs table."""

    id: UUID
    ran_at: datetime
    dataset_size: int
    results: dict
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


async def upsert_evaluation_run(
    pool: Pool,
    dataset_size: int,
    results: dict,
    metadata: dict | None = None,
) -> None:
    """Insert an evaluation run result for historical tracking.

    Args:
        pool: asyncpg connection pool.
        dataset_size: Number of samples evaluated.
        results: Dict of metric name → score from Ragas.
        metadata: Optional context (model used, trace filter, etc.).
    """
    import json

    await pool.execute(
        """
        INSERT INTO evaluation_runs (dataset_size, results, metadata)
        VALUES ($1, $2::jsonb, $3::jsonb)
        """,
        dataset_size,
        json.dumps(results),
        json.dumps(metadata or {}),
    )
    logger.debug("Inserted evaluation run", extra={"dataset_size": dataset_size})


async def get_evaluation_runs(
    pool: Pool,
    limit: int = 20,
) -> list[EvaluationRunRecord]:
    """Fetch recent evaluation run records ordered by date descending.

    Args:
        pool: asyncpg connection pool.
        limit: Maximum number of records to return.

    Returns:
        List of evaluation run records.
    """
    rows = await pool.fetch(
        """
        SELECT id, ran_at, dataset_size, results, metadata, created_at
        FROM evaluation_runs
        ORDER BY ran_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [EvaluationRunRecord(**dict(row)) for row in rows]
