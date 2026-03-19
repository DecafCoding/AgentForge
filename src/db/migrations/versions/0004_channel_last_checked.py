"""Add last_checked_at to youtube_channels.

Tracks when each channel was last checked by the collector so the
scheduler can prioritise channels that have not been checked recently
and skip channels checked within the last three days.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add last_checked_at column to youtube_channels."""
    op.execute(
        """
        ALTER TABLE youtube_channels
        ADD COLUMN last_checked_at TIMESTAMPTZ
        """
    )


def downgrade() -> None:
    """Remove last_checked_at column from youtube_channels."""
    op.execute(
        """
        ALTER TABLE youtube_channels
        DROP COLUMN last_checked_at
        """
    )
