"""
Collector-layer data models.

Pydantic models that represent data as it arrives from external sources,
before it is written to the database. These are intermediate transfer
objects — the database layer has its own models in src/db/queries.py.
This module must never import pydantic_ai, langfuse, or any LLM dependency.
"""

from datetime import datetime

from pydantic import BaseModel


class VideoMetadata(BaseModel):
    """YouTube video metadata as returned by the YouTube Data API v3.

    All fields except ``video_id``, ``channel_id``, and ``title`` are
    optional because the API may omit them depending on the requested parts
    and the video's privacy settings.
    """

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
