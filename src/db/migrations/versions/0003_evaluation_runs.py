"""Add evaluation_runs table for tracking Ragas evaluation history.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the evaluation_runs table."""
    op.execute(
        """
        CREATE TABLE evaluation_runs (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            ran_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            dataset_size INTEGER     NOT NULL,
            results      JSONB       NOT NULL,
            metadata     JSONB       DEFAULT '{}',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_eval_runs_ran_at ON evaluation_runs(ran_at DESC)")


def downgrade() -> None:
    """Drop the evaluation_runs table."""
    op.execute("DROP TABLE IF EXISTS evaluation_runs")
