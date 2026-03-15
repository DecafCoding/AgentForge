"""Add scraped_pages table for web scraping collector.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the scraped_pages table."""
    op.execute(
        """
        CREATE TABLE scraped_pages (
            id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            url        VARCHAR     NOT NULL UNIQUE,
            title      VARCHAR,
            content    TEXT,
            metadata   JSONB       DEFAULT '{}',
            embedding  vector(1536),
            scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_scraped_pages_url ON scraped_pages(url)")


def downgrade() -> None:
    """Drop the scraped_pages table."""
    op.execute("DROP TABLE IF EXISTS scraped_pages")
