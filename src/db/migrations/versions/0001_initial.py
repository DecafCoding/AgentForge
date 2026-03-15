"""Initial schema: pgvector extension, youtube_channels, youtube_videos.

Revision ID: 0001
Revises:
Create Date: 2026-03-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial schema."""
    # pgvector must be enabled before any vector column is created.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE youtube_channels (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            channel_id   VARCHAR     NOT NULL UNIQUE,
            channel_name VARCHAR     NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE youtube_videos (
            id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            video_id      VARCHAR     NOT NULL UNIQUE,
            channel_id    VARCHAR     NOT NULL
                              REFERENCES youtube_channels(channel_id)
                              ON DELETE CASCADE,
            title         VARCHAR     NOT NULL,
            description   TEXT,
            published_at  TIMESTAMPTZ,
            view_count    INTEGER,
            like_count    INTEGER,
            comment_count INTEGER,
            duration      VARCHAR,
            transcript    TEXT,
            embedding     vector(1536),
            collected_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        "CREATE INDEX idx_videos_channel ON youtube_videos(channel_id)"
    )
    op.execute(
        "CREATE INDEX idx_videos_published ON youtube_videos(published_at DESC)"
    )


def downgrade() -> None:
    """Drop all tables and the pgvector extension."""
    op.execute("DROP TABLE IF EXISTS youtube_videos")
    op.execute("DROP TABLE IF EXISTS youtube_channels")
    op.execute("DROP EXTENSION IF EXISTS vector")
