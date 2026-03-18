"""
Evaluation results reporter.

Formats Ragas evaluation scores for human-readable output and persists
results to Postgres for historical tracking. This module belongs to the
Evaluation layer.
"""

import logging
from datetime import UTC, datetime

from asyncpg import Pool

logger = logging.getLogger(__name__)


class EvalReport:
    """Formats and optionally stores evaluation results.

    Wraps the raw metric scores from run_evaluation() with metadata
    about the evaluation run and provides formatting helpers.
    """

    def __init__(
        self,
        results: dict[str, float],
        dataset_size: int,
        metadata: dict | None = None,
    ) -> None:
        """Initialise the report with results and context metadata.

        Args:
            results: Dict of metric name → float score from run_evaluation().
            dataset_size: Number of samples in the evaluated dataset.
            metadata: Optional run context (model, trace filter, etc.).
        """
        self.results = results
        self.dataset_size = dataset_size
        self.metadata = metadata or {}
        self.timestamp = datetime.now(tz=UTC)

    def summary(self) -> str:
        """Return a human-readable evaluation summary.

        Returns:
            Formatted string with timestamp, dataset size, and per-metric scores.
        """
        lines = [
            f"Evaluation Report — {self.timestamp.isoformat()}",
            f"Dataset size: {self.dataset_size} samples",
            "",
        ]
        if not self.results:
            lines.append("  No results (empty dataset or evaluation skipped)")
        else:
            for metric, score in sorted(self.results.items()):
                lines.append(f"  {metric}: {score:.3f}")
        return "\n".join(lines)

    async def save_to_db(self, pool: Pool) -> None:
        """Persist evaluation results to Postgres for historical tracking.

        Args:
            pool: asyncpg connection pool.
        """
        from src.db.queries import upsert_evaluation_run

        await upsert_evaluation_run(
            pool=pool,
            dataset_size=self.dataset_size,
            results=self.results,
            metadata=self.metadata,
        )
        logger.info(
            "Saved evaluation run to database",
            extra={"dataset_size": self.dataset_size},
        )
