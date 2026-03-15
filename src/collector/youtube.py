"""
YouTube video metadata collector.

Fetches video metadata and transcripts from the YouTube Data API v3 on a
scheduled interval and stores them in Postgres via src.db.queries. This
module belongs to the Collector layer and must not import any LLM or
observability dependencies.

Sync API clients (googleapiclient, youtube_transcript_api) are wrapped in
asyncio.to_thread() so they do not block the event loop.
"""

import asyncio
import logging
from datetime import UTC, datetime

from asyncpg import Pool
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

from src.collector.base import BaseCollector
from src.collector.models import VideoMetadata
from src.db import queries

logger = logging.getLogger(__name__)

# Maximum videos to fetch per channel per collection cycle.
_MAX_RESULTS_PER_CHANNEL = 25


class YouTubeCollector(BaseCollector):
    """Collects video metadata and transcripts from YouTube channels.

    Implements the BaseCollector interface for scheduled data collection.
    Uses the YouTube Data API v3 for metadata and youtube-transcript-api
    for transcripts. Both clients are synchronous and are run in a thread
    pool via asyncio.to_thread(). Stores results via src.db.queries.
    """

    def __init__(self, pool: Pool, api_key: str) -> None:
        super().__init__(pool)
        self._api_key = api_key
        # Lazy-initialised on first collect() call so __init__ stays sync.
        self._youtube_client: object | None = None

    async def _get_client(self) -> object:
        """Return the YouTube API client, building it on first call."""
        if self._youtube_client is None:
            # build() fetches the discovery document — run in thread.
            self._youtube_client = await asyncio.to_thread(
                build,
                "youtube",
                "v3",
                developerKey=self._api_key,
                # Disable on-disk caching to avoid permission issues in Docker.
                cache_discovery=False,
            )
        return self._youtube_client

    async def collect(self) -> int:
        """Run a collection cycle for all channels stored in the database.

        Returns:
            Total number of videos upserted across all channels.
        """
        if not self._api_key:
            logger.warning("YOUTUBE_API_KEY is not set — skipping collection")
            return 0

        channels = await queries.get_channels(self._pool)
        if not channels:
            logger.info("No channels configured — skipping collection")
            return 0

        total = 0
        for channel in channels:
            try:
                count = await self._collect_channel(channel.channel_id)
                total += count
            except Exception as exc:
                # Log and continue — one failed channel must not abort others.
                logger.error(
                    "Failed to collect channel",
                    extra={"channel_id": channel.channel_id, "error": str(exc)},
                )

        logger.info("Collection cycle complete", extra={"total_videos": total})
        return total

    async def _collect_channel(self, channel_id: str) -> int:
        """Fetch and store recent videos for a single channel.

        Args:
            channel_id: YouTube channel identifier (e.g. ``UCxxxxxx``).

        Returns:
            Number of videos upserted for this channel.
        """
        logger.info("Collecting channel", extra={"channel_id": channel_id})
        client = await self._get_client()

        video_ids = await self._fetch_recent_video_ids(client, channel_id)
        if not video_ids:
            logger.info("No videos found", extra={"channel_id": channel_id})
            return 0

        videos = await self._fetch_video_details(client, channel_id, video_ids)

        count = 0
        for video in videos:
            video.transcript = await self._fetch_transcript(video.video_id)
            await queries.upsert_video(
                self._pool,
                video_id=video.video_id,
                channel_id=video.channel_id,
                title=video.title,
                description=video.description,
                published_at=video.published_at,
                view_count=video.view_count,
                like_count=video.like_count,
                comment_count=video.comment_count,
                duration=video.duration,
                transcript=video.transcript,
            )
            count += 1

        logger.info(
            "Channel collected",
            extra={"channel_id": channel_id, "videos": count},
        )
        return count

    async def _fetch_recent_video_ids(
        self,
        client: object,
        channel_id: str,
    ) -> list[str]:
        """Return the IDs of the most recently published videos for a channel.

        Args:
            client: Authenticated YouTube API client.
            channel_id: YouTube channel identifier.

        Returns:
            List of video ID strings, newest first.
        """

        def _call() -> list[str]:
            response = (
                client.search()  # type: ignore[attr-defined]
                .list(
                    part="id",
                    channelId=channel_id,
                    maxResults=_MAX_RESULTS_PER_CHANNEL,
                    type="video",
                    order="date",
                )
                .execute()
            )
            return [
                item["id"]["videoId"]
                for item in response.get("items", [])
                if item.get("id", {}).get("videoId")
            ]

        try:
            return await asyncio.to_thread(_call)
        except HttpError as exc:
            logger.error(
                "YouTube API error fetching video IDs",
                extra={"channel_id": channel_id, "error": str(exc)},
            )
            return []

    async def _fetch_video_details(
        self,
        client: object,
        channel_id: str,
        video_ids: list[str],
    ) -> list[VideoMetadata]:
        """Fetch full metadata for a batch of video IDs.

        Args:
            client: Authenticated YouTube API client.
            channel_id: The parent channel ID (used to populate VideoMetadata).
            video_ids: List of YouTube video IDs to fetch.

        Returns:
            List of populated VideoMetadata objects.
        """

        def _call() -> list[VideoMetadata]:
            response = (
                client.videos()  # type: ignore[attr-defined]
                .list(
                    part="snippet,statistics,contentDetails",
                    id=",".join(video_ids),
                )
                .execute()
            )

            results: list[VideoMetadata] = []
            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                details = item.get("contentDetails", {})

                published_raw = snippet.get("publishedAt")
                published_at: datetime | None = None
                if published_raw:
                    published_at = datetime.fromisoformat(
                        published_raw.replace("Z", "+00:00")
                    ).astimezone(UTC)

                results.append(
                    VideoMetadata(
                        video_id=item["id"],
                        channel_id=channel_id,
                        title=snippet.get("title", ""),
                        description=snippet.get("description"),
                        published_at=published_at,
                        view_count=_safe_int(stats.get("viewCount")),
                        like_count=_safe_int(stats.get("likeCount")),
                        comment_count=_safe_int(stats.get("commentCount")),
                        duration=details.get("duration"),
                    )
                )
            return results

        try:
            return await asyncio.to_thread(_call)
        except HttpError as exc:
            logger.error(
                "YouTube API error fetching video details",
                extra={"channel_id": channel_id, "error": str(exc)},
            )
            return []

    async def _fetch_transcript(self, video_id: str) -> str | None:
        """Attempt to fetch the English transcript for a video.

        Transcript failures are silent — many videos have no transcript.

        Args:
            video_id: YouTube video identifier.

        Returns:
            Full transcript text joined into a single string, or None.
        """

        def _call() -> str | None:
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id,
                languages=["en", "en-US", "en-GB"],
            )
            return " ".join(segment["text"] for segment in transcript)

        try:
            return await asyncio.to_thread(_call)
        except (TranscriptsDisabled, NoTranscriptFound):
            return None
        except Exception as exc:
            logger.debug(
                "Transcript unavailable",
                extra={"video_id": video_id, "error": str(exc)},
            )
            return None


def _safe_int(value: str | None) -> int | None:
    """Convert a string to int, returning None if conversion fails."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
