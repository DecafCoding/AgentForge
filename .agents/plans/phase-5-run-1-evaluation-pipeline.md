# Phase 5 — Run 1: Foundation + Ragas Evaluation Pipeline (PBI 5.1)

The following plan should be complete, but validate documentation and codebase patterns before implementing.

Pay special attention to Ragas API version. After `uv sync`, run `uv run python -c "import ragas; print(ragas.__version__)"` and `uv run python -c "from ragas.metrics import faithfulness; print(type(faithfulness))"` to confirm the actual installed API before writing any evaluation code.

## What This Run Delivers

- All Phase 5 dependencies installed and config wired
- `evaluation_runs` database table + typed query functions
- `src/evaluation/` module: dataset extraction, pipeline, metrics, reporter
- `scripts/export_dataset.py` and `scripts/evaluate.py`
- `tests/test_evaluation.py`

**Does NOT include:** MCP server (Run 2), test patterns, or documentation (Run 3).

## Prerequisites

Phases 1–4 complete and all tests passing on branch `feat/phase-5-evaluation-mcp`.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/config.py` — All env var loading pattern; add new constants after the `REDIS_URL` block
- `src/db/queries.py` (lines 1–20, 275–319) — Module docstring, import block, and `upsert_scraped_page` pattern to follow for new evaluation query functions. Note `json` is imported locally inside functions (line 303), not at top of file
- `src/db/migrations/versions/0002_scraped_pages.py` — Exact migration structure to mirror
- `src/db/client.py` — `create_pool()` and `close_pool()` — scripts call these directly
- `src/observability/tracing.py` — `get_client()` returns `Langfuse | None`; evaluation dataset builder imports this
- `.env.example` — Append Phase 5 section at the bottom of the file
- `pyproject.toml` (lines 1–36) — Dependency list format; append after `redis` entry
- `tests/conftest.py` — `mock_pool` fixture at line 15; `test_evaluation.py` uses this
- `tests/test_agent.py` — Mock pattern: `patch("src.agent.agent.agent.run", AsyncMock(...))` — follow for evaluation tests

### New Files to Create

- `src/evaluation/__init__.py`
- `src/evaluation/metrics.py`
- `src/evaluation/dataset.py`
- `src/evaluation/pipeline.py`
- `src/evaluation/reporter.py`
- `src/db/migrations/versions/0003_evaluation_runs.py`
- `scripts/export_dataset.py`
- `scripts/evaluate.py`
- `tests/test_evaluation.py`

### Patterns to Follow

**Config constant block** (mirror existing blocks in `src/config.py`):
```python
# ---------------------------------------------------------------------------
# Evaluation (Phase 5)
# ---------------------------------------------------------------------------
EVAL_MODEL: str = os.getenv("EVAL_MODEL", "gpt-4o")
EVAL_DATASET_LIMIT: int = int(os.getenv("EVAL_DATASET_LIMIT", "100"))
```

**Migration structure** (mirror `0002_scraped_pages.py` exactly):
```python
revision: str = "0003"
down_revision: str = "0002"
```

**DB query function** (mirror `upsert_scraped_page` pattern — local `json` import, `$1::jsonb` cast):
```python
async def upsert_evaluation_run(pool: Pool, dataset_size: int, results: dict, ...) -> None:
    import json
    await pool.execute("INSERT INTO evaluation_runs ... VALUES ($1, $2::jsonb, $3::jsonb)", ...)
```

**Module-level logger** (every new file):
```python
import logging
logger = logging.getLogger(__name__)
```

---

## RAGAS API VERIFICATION (do this before writing evaluation code)

```bash
uv run python -c "import ragas; print('version:', ragas.__version__)"
uv run python -c "from ragas.metrics import faithfulness; print('instance type:', type(faithfulness))"
uv run python -c "from ragas import aevaluate; print('aevaluate available')"
uv run python -c "from ragas import EvaluationDataset; from ragas.dataset_schema import SingleTurnSample; print('dataset API ok')"
```

**If `aevaluate` import fails:** use `evaluate` (sync) wrapped in `asyncio.to_thread()` as fallback.
**If `faithfulness` import fails:** try `from ragas.metrics import Faithfulness; faithfulness = Faithfulness()`.
**If `SingleTurnSample` is not in `ragas.dataset_schema`:** try `from ragas import SingleTurnSample`.

---

## STEP-BY-STEP TASKS

### Task 1: UPDATE `pyproject.toml` — add Phase 5 dependencies

- **ADD** after the `"redis>=5.0.0",` line:
  ```toml
  # Evaluation (Phase 5)
  "ragas>=0.2.0",
  "fastmcp>=2.0.0",
  "langchain-openai>=0.2.0",
  ```
- **NOTE**: `fastmcp` added now so `uv sync` resolves the full Phase 5 dep tree once. It won't be used until Run 2.
- **NOTE**: Do NOT add `datasets` explicitly — ragas pulls it in transitively and pinning it separately can cause version conflicts.
- **VALIDATE**: `uv sync` then `uv run python -c "import ragas, fastmcp; print('ok')"`

---

### Task 2: UPDATE `src/config.py` — add Phase 5 env vars

- **ADD** after the `REDIS_URL` block (line ~93):
  ```python
  # ---------------------------------------------------------------------------
  # Evaluation (Phase 5)
  # ---------------------------------------------------------------------------
  EVAL_MODEL: str = os.getenv("EVAL_MODEL", "gpt-4o")
  EVAL_DATASET_LIMIT: int = int(os.getenv("EVAL_DATASET_LIMIT", "100"))

  # ---------------------------------------------------------------------------
  # MCP Server (Phase 5)
  # ---------------------------------------------------------------------------
  MCP_TRANSPORT: str = os.getenv("MCP_TRANSPORT", "stdio")
  MCP_PORT: int = int(os.getenv("MCP_PORT", "8001"))
  ```
- **NOTE**: MCP vars added now so `.env.example` and config are complete in one pass.
- **VALIDATE**: `uv run python -c "from src.config import EVAL_MODEL, MCP_PORT; print(EVAL_MODEL, MCP_PORT)"`

---

### Task 3: UPDATE `.env.example` — add Phase 5 section

- **ADD** at the bottom of the file:
  ```bash
  # -----------------------------------------------------------------------------
  # Evaluation (Phase 5)
  # EVAL_MODEL: LLM used by Ragas to compute evaluation metrics (separate from app model).
  # EVAL_DATASET_LIMIT: Max Langfuse traces to include in one evaluation run.
  # -----------------------------------------------------------------------------
  EVAL_MODEL=gpt-4o
  EVAL_DATASET_LIMIT=100

  # -----------------------------------------------------------------------------
  # MCP Server (Phase 5)
  # MCP_TRANSPORT: stdio (for Claude Desktop/local clients) | http (for remote clients).
  # MCP_PORT: Port for HTTP transport only (ignored for stdio).
  # -----------------------------------------------------------------------------
  MCP_TRANSPORT=stdio
  MCP_PORT=8001
  ```

---

### Task 4: CREATE `src/db/migrations/versions/0003_evaluation_runs.py`

- **IMPLEMENT**:
  ```python
  """Add evaluation_runs table for tracking Ragas evaluation history.

  Revision ID: 0003
  Revises: 0002
  Create Date: 2026-03-16
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
      op.execute(
          "CREATE INDEX idx_eval_runs_ran_at ON evaluation_runs(ran_at DESC)"
      )


  def downgrade() -> None:
      """Drop the evaluation_runs table."""
      op.execute("DROP TABLE IF EXISTS evaluation_runs")
  ```
- **VALIDATE**: `uv run alembic upgrade head` — should show `Running upgrade 0002 -> 0003`
- **GOTCHA**: If Postgres is not running locally, this validates in CI. Proceed to Task 5.

---

### Task 5: UPDATE `src/db/queries.py` — add evaluation run queries

- **ADD** at the bottom of the file, after the scraped page queries section:
  ```python
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
      logger.debug(
          "Inserted evaluation run", extra={"dataset_size": dataset_size}
      )


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
  ```
- **VALIDATE**: `uv run python -c "from src.db.queries import EvaluationRunRecord, upsert_evaluation_run, get_evaluation_runs; print('ok')"`

---

### Task 6: CREATE `src/evaluation/__init__.py`

```python
"""
Agent quality evaluation layer.

Provides Ragas evaluation pipelines for measuring agent output quality
against real interactions logged in Langfuse. This layer imports from
src.config and src.db.queries only — no agent or collector imports.
"""
```
- **VALIDATE**: `uv run python -c "import src.evaluation; print('ok')"`

---

### Task 7: CREATE `src/evaluation/metrics.py`

- **IMPLEMENT** (adjust import style based on Ragas API verification result):
  ```python
  """
  Ragas metric definitions for agent evaluation.

  Defines the default metric sets for unsupervised evaluation (no ground truth
  required) and supervised evaluation (ground truth annotations available).
  Import DEFAULT_METRICS or SUPERVISED_METRICS into the pipeline module.

  This module belongs to the Evaluation layer.
  """

  # ---------------------------------------------------------------------------
  # Metric imports
  #
  # Ragas 0.2.x exports pre-instantiated metric instances from ragas.metrics.
  # If the import below fails, replace with: from ragas.metrics import Faithfulness
  # and instantiate: faithfulness = Faithfulness()
  # ---------------------------------------------------------------------------
  from ragas.metrics import (
      context_precision,
      context_recall,
      faithfulness,
  )

  # Try response_relevancy first (0.2.x+); fall back to answer_relevancy (0.1.x).
  try:
      from ragas.metrics import response_relevancy
  except ImportError:
      from ragas.metrics import answer_relevancy as response_relevancy  # type: ignore[no-redef]

  # Metrics that work without ground_truth — use for automated evaluation.
  DEFAULT_METRICS = [
      faithfulness,        # Is the answer supported by the retrieved context?
      response_relevancy,  # Is the answer relevant to the question?
      context_precision,   # Are the retrieved contexts ranked by relevance?
  ]

  # Additional metrics that require ground_truth / reference annotations.
  SUPERVISED_METRICS = [
      context_recall,      # Did we retrieve all context needed to answer?
  ]
  ```
- **VALIDATE**: `uv run python -c "from src.evaluation.metrics import DEFAULT_METRICS; print(len(DEFAULT_METRICS), 'metrics')"`

---

### Task 8: CREATE `src/evaluation/dataset.py`

```python
"""
Evaluation dataset creation from Langfuse traces.

Extracts agent interactions (question → retrieved contexts → answer) from
Langfuse traces and converts them into a Ragas-compatible EvaluationDataset.
Each Langfuse trace becomes one SingleTurnSample.

This module belongs to the Evaluation layer.
"""

import logging
from typing import Optional

from pydantic import BaseModel
from ragas import EvaluationDataset
from ragas.dataset_schema import SingleTurnSample

logger = logging.getLogger(__name__)


class EvalSample(BaseModel):
    """Intermediate representation of one evaluation sample before Ragas conversion."""

    question: str
    answer: str
    contexts: list[str]
    ground_truth: Optional[str] = None


def create_dataset_from_langfuse(
    limit: int = 100,
    trace_name: Optional[str] = None,
) -> EvaluationDataset:
    """Extract agent interactions from Langfuse traces into a Ragas dataset.

    Fetches traces from Langfuse, extracts input/output, and collects context
    strings from tool call child spans. Returns an EvaluationDataset ready for
    aevaluate(). Returns an empty dataset if Langfuse is not configured.

    Args:
        limit: Maximum number of traces to include.
        trace_name: Optional filter for trace name (e.g., "agent_run").

    Returns:
        EvaluationDataset with one SingleTurnSample per valid Langfuse trace.
    """
    from src.observability.tracing import get_client

    lf = get_client()
    if lf is None:
        logger.warning(
            "Langfuse not configured — returning empty evaluation dataset"
        )
        return EvaluationDataset(samples=[])

    traces = lf.fetch_traces(name=trace_name, limit=limit)
    logger.info(
        "Fetched traces for evaluation",
        extra={"count": len(traces.data), "trace_name": trace_name},
    )

    samples = []
    for trace in traces.data:
        question = (trace.input or {}).get("question", "")
        answer = (trace.output or {}).get("answer", "")

        if not question or not answer:
            logger.debug(
                "Skipping trace with missing input/output",
                extra={"trace_id": trace.id},
            )
            continue

        # Extract context strings from tool call child spans.
        contexts: list[str] = []
        try:
            observations = lf.fetch_observations(trace_id=trace.id)
            for obs in observations.data:
                if obs.type == "TOOL" and obs.output:
                    contexts.append(str(obs.output))
        except Exception as exc:
            logger.warning(
                "Failed to fetch observations for trace",
                extra={"trace_id": trace.id, "error": str(exc)},
            )

        samples.append(
            SingleTurnSample(
                user_input=question,
                response=answer,
                # Ragas requires a non-empty list — default to [""] when no tool
                # contexts were captured so evaluation still runs.
                retrieved_contexts=contexts if contexts else [""],
            )
        )

    logger.info("Built evaluation dataset", extra={"samples": len(samples)})
    return EvaluationDataset(samples=samples)
```
- **GOTCHA**: `SingleTurnSample` location may vary — try `from ragas.dataset_schema import SingleTurnSample`; if that fails, try `from ragas import SingleTurnSample`.
- **GOTCHA**: Langfuse observation `type` is uppercase `"TOOL"` in v2 API.
- **VALIDATE**: `uv run python -c "from src.evaluation.dataset import create_dataset_from_langfuse; print('ok')"`

---

### Task 9: CREATE `src/evaluation/pipeline.py`

```python
"""
Ragas evaluation pipeline.

Wraps Ragas aevaluate() for async use. Returns a flat dict of
metric name → float score suitable for storage and display.

This module belongs to the Evaluation layer.
"""

import logging
from typing import Optional

from ragas import EvaluationDataset, aevaluate

from src.config import EVAL_MODEL, OPENAI_API_KEY
from src.evaluation.metrics import DEFAULT_METRICS, SUPERVISED_METRICS

logger = logging.getLogger(__name__)


async def run_evaluation(
    dataset: EvaluationDataset,
    metrics: Optional[list] = None,
) -> dict[str, float]:
    """Run Ragas evaluation on a dataset of agent interactions.

    Uses aevaluate() (truly async) rather than evaluate() (sync + nest_asyncio)
    to avoid event loop conflicts in an async application.

    Args:
        dataset: Ragas EvaluationDataset built from real agent interactions.
        metrics: Metric list to compute. Defaults to DEFAULT_METRICS. Adds
                 SUPERVISED_METRICS automatically when reference is present
                 in the samples.

    Returns:
        Dict mapping metric name to average score across the dataset.
        Returns empty dict if dataset is empty.
    """
    if len(dataset) == 0:
        logger.warning("Empty evaluation dataset — returning zero scores")
        return {}

    if metrics is None:
        has_reference = any(
            s.reference is not None for s in dataset.samples
        )
        metrics = (
            DEFAULT_METRICS + SUPERVISED_METRICS if has_reference else DEFAULT_METRICS
        )

    logger.info(
        "Running evaluation",
        extra={
            "samples": len(dataset),
            "metrics": [getattr(m, "name", str(m)) for m in metrics],
        },
    )

    # Wrap the configured model as a Ragas-compatible LLM judge.
    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper

    llm = LangchainLLMWrapper(ChatOpenAI(model=EVAL_MODEL, api_key=OPENAI_API_KEY))

    result = await aevaluate(dataset=dataset, metrics=metrics, llm=llm)
    scores: dict[str, float] = result.to_pandas().mean().to_dict()

    logger.info("Evaluation complete", extra={"scores": scores})
    return scores
```
- **GOTCHA**: `aevaluate` is async — `await` it. Do NOT use `evaluate()` (sync) in async code.
- **GOTCHA**: `result.to_pandas().mean().to_dict()` returns `{metric_name: float}`. Numeric columns only — non-numeric cols (if any) produce NaN; filter those out if needed.
- **VALIDATE**: `uv run python -c "from src.evaluation.pipeline import run_evaluation; print('ok')"`

---

### Task 10: CREATE `src/evaluation/reporter.py`

```python
"""
Evaluation results reporter.

Formats Ragas evaluation scores for human-readable output and persists
results to Postgres for historical tracking. This module belongs to the
Evaluation layer.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

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
        metadata: Optional[dict] = None,
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
        self.timestamp = datetime.now(tz=timezone.utc)

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
```
- **VALIDATE**: `uv run python -c "from src.evaluation.reporter import EvalReport; r = EvalReport({}, 0); print(r.summary())"`

---

### Task 11: CREATE `scripts/export_dataset.py`

```python
"""Export agent interactions from Langfuse to a JSON file for offline evaluation.

Usage:
    uv run python scripts/export_dataset.py
    uv run python scripts/export_dataset.py --limit 50 --trace-name agent_run
    uv run python scripts/export_dataset.py --output eval_data.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Export evaluation dataset to JSON."""
    parser = argparse.ArgumentParser(
        description="Export agent interactions from Langfuse for offline evaluation"
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Maximum number of traces to export (default: 100)",
    )
    parser.add_argument(
        "--trace-name", type=str, default=None,
        help="Filter by trace name (e.g., 'agent_run')",
    )
    parser.add_argument(
        "--output", type=str, default="eval_dataset.json",
        help="Output JSON file path (default: eval_dataset.json)",
    )
    args = parser.parse_args()

    from src.evaluation.dataset import create_dataset_from_langfuse

    dataset = create_dataset_from_langfuse(
        limit=args.limit,
        trace_name=args.trace_name,
    )

    if len(dataset) == 0:
        logger.warning(
            "No samples found — check Langfuse configuration and trace filters"
        )
        sys.exit(1)

    output_path = Path(args.output)
    records = [
        {
            "user_input": s.user_input,
            "response": s.response,
            "retrieved_contexts": s.retrieved_contexts,
            "reference": s.reference,
        }
        for s in dataset.samples
    ]

    output_path.write_text(json.dumps(records, indent=2, default=str))
    logger.info("Exported %d samples to %s", len(records), output_path)


if __name__ == "__main__":
    main()
```
- **VALIDATE**: `uv run python scripts/export_dataset.py --help`

---

### Task 12: CREATE `scripts/evaluate.py`

```python
"""Run the Ragas evaluation pipeline against real agent interactions.

Fetches traces from Langfuse, runs Ragas evaluation, prints the report,
and optionally saves results to Postgres.

Usage:
    uv run python scripts/evaluate.py
    uv run python scripts/evaluate.py --limit 50 --trace-name agent_run
    uv run python scripts/evaluate.py --save-to-db
"""

import argparse
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run evaluation pipeline."""
    parser = argparse.ArgumentParser(
        description="Run Ragas agent evaluation pipeline"
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--trace-name", type=str, default=None)
    parser.add_argument(
        "--save-to-db",
        action="store_true",
        help="Persist results to Postgres evaluation_runs table",
    )
    args = parser.parse_args()

    from src.evaluation.dataset import create_dataset_from_langfuse
    from src.evaluation.pipeline import run_evaluation
    from src.evaluation.reporter import EvalReport

    dataset = create_dataset_from_langfuse(
        limit=args.limit,
        trace_name=args.trace_name,
    )
    logger.info("Dataset size: %d samples", len(dataset))

    results = await run_evaluation(dataset)

    report = EvalReport(
        results=results,
        dataset_size=len(dataset),
        metadata={"trace_name": args.trace_name, "limit": args.limit},
    )
    print(report.summary())

    if args.save_to_db:
        from src.db.client import close_pool, create_pool

        pool = await create_pool()
        try:
            await report.save_to_db(pool)
            logger.info("Results saved to database")
        finally:
            await close_pool(pool)


if __name__ == "__main__":
    asyncio.run(main())
```
- **VALIDATE**: `uv run python scripts/evaluate.py --help`

---

### Task 13: CREATE `tests/test_evaluation.py`

```python
"""
Evaluation pipeline tests.

Tests the evaluation module components using mocked Langfuse and Ragas
dependencies. No real LLM calls or Langfuse connections are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ragas import EvaluationDataset
from ragas.dataset_schema import SingleTurnSample


# ---------------------------------------------------------------------------
# EvalSample model
# ---------------------------------------------------------------------------


def test_eval_sample_requires_question_and_answer():
    """EvalSample must have question and answer fields."""
    from src.evaluation.dataset import EvalSample

    sample = EvalSample(question="What is X?", answer="X is Y.", contexts=["X is Y."])
    assert sample.question == "What is X?"
    assert sample.ground_truth is None


# ---------------------------------------------------------------------------
# create_dataset_from_langfuse
# ---------------------------------------------------------------------------


def test_create_dataset_returns_empty_when_langfuse_not_configured():
    """Dataset creation returns empty EvaluationDataset when Langfuse is None."""
    with patch("src.evaluation.dataset.get_client", return_value=None):
        from src.evaluation.dataset import create_dataset_from_langfuse

        dataset = create_dataset_from_langfuse(limit=10)

    assert len(dataset) == 0


def test_create_dataset_skips_traces_with_missing_input():
    """Traces with empty question or answer are skipped."""
    mock_trace = MagicMock()
    mock_trace.id = "trace-1"
    mock_trace.input = {}
    mock_trace.output = {"answer": "Some answer"}

    mock_traces = MagicMock()
    mock_traces.data = [mock_trace]

    mock_lf = MagicMock()
    mock_lf.fetch_traces.return_value = mock_traces

    with patch("src.evaluation.dataset.get_client", return_value=mock_lf):
        from src.evaluation.dataset import create_dataset_from_langfuse

        dataset = create_dataset_from_langfuse(limit=10)

    assert len(dataset) == 0


def test_create_dataset_extracts_question_and_answer():
    """Valid traces produce one sample per trace with contexts from tool spans."""
    mock_obs = MagicMock()
    mock_obs.type = "TOOL"
    mock_obs.output = "retrieved context text"

    mock_observations = MagicMock()
    mock_observations.data = [mock_obs]

    mock_trace = MagicMock()
    mock_trace.id = "trace-1"
    mock_trace.input = {"question": "What is Python?"}
    mock_trace.output = {"answer": "Python is a programming language."}

    mock_traces = MagicMock()
    mock_traces.data = [mock_trace]

    mock_lf = MagicMock()
    mock_lf.fetch_traces.return_value = mock_traces
    mock_lf.fetch_observations.return_value = mock_observations

    with patch("src.evaluation.dataset.get_client", return_value=mock_lf):
        from src.evaluation.dataset import create_dataset_from_langfuse

        dataset = create_dataset_from_langfuse(limit=10)

    assert len(dataset) == 1
    assert dataset.samples[0].user_input == "What is Python?"
    assert dataset.samples[0].response == "Python is a programming language."
    assert "retrieved context text" in dataset.samples[0].retrieved_contexts


def test_create_dataset_defaults_contexts_to_empty_string_when_no_tools():
    """Traces with no tool spans get retrieved_contexts=[''] — never empty list."""
    mock_observations = MagicMock()
    mock_observations.data = []

    mock_trace = MagicMock()
    mock_trace.id = "trace-1"
    mock_trace.input = {"question": "Q?"}
    mock_trace.output = {"answer": "A."}

    mock_traces = MagicMock()
    mock_traces.data = [mock_trace]

    mock_lf = MagicMock()
    mock_lf.fetch_traces.return_value = mock_traces
    mock_lf.fetch_observations.return_value = mock_observations

    with patch("src.evaluation.dataset.get_client", return_value=mock_lf):
        from src.evaluation.dataset import create_dataset_from_langfuse

        dataset = create_dataset_from_langfuse(limit=10)

    assert dataset.samples[0].retrieved_contexts == [""]


# ---------------------------------------------------------------------------
# run_evaluation
# ---------------------------------------------------------------------------


async def test_run_evaluation_returns_empty_dict_for_empty_dataset():
    """run_evaluation() returns empty dict when dataset has no samples."""
    from src.evaluation.pipeline import run_evaluation

    empty_dataset = EvaluationDataset(samples=[])
    result = await run_evaluation(empty_dataset)
    assert result == {}


async def test_run_evaluation_calls_aevaluate_with_metrics_and_llm():
    """run_evaluation() calls aevaluate() with metrics and a wrapped LLM."""
    dataset = EvaluationDataset(
        samples=[
            SingleTurnSample(
                user_input="Q?", response="A.", retrieved_contexts=["context"]
            )
        ]
    )

    mock_df = MagicMock()
    mock_df.mean.return_value.to_dict.return_value = {"faithfulness": 0.9}
    mock_result = MagicMock()
    mock_result.to_pandas.return_value = mock_df

    with (
        patch("src.evaluation.pipeline.aevaluate", AsyncMock(return_value=mock_result)),
        patch("src.evaluation.pipeline.LangchainLLMWrapper"),
        patch("src.evaluation.pipeline.ChatOpenAI"),
    ):
        from src.evaluation.pipeline import run_evaluation

        scores = await run_evaluation(dataset)

    assert scores == {"faithfulness": 0.9}


# ---------------------------------------------------------------------------
# EvalReport
# ---------------------------------------------------------------------------


def test_eval_report_summary_includes_metric_scores():
    """EvalReport.summary() produces readable string with all metric scores."""
    from src.evaluation.reporter import EvalReport

    report = EvalReport(
        results={"faithfulness": 0.85, "response_relevancy": 0.92},
        dataset_size=50,
    )
    summary = report.summary()

    assert "50 samples" in summary
    assert "faithfulness: 0.850" in summary
    assert "response_relevancy: 0.920" in summary


def test_eval_report_summary_handles_empty_results():
    """EvalReport.summary() handles empty results without crashing."""
    from src.evaluation.reporter import EvalReport

    report = EvalReport(results={}, dataset_size=0)
    summary = report.summary()
    assert "No results" in summary


async def test_eval_report_save_to_db_delegates_to_upsert(mock_pool):
    """EvalReport.save_to_db() calls upsert_evaluation_run with correct args."""
    from src.evaluation.reporter import EvalReport

    report = EvalReport(results={"faithfulness": 0.8}, dataset_size=10)

    with patch(
        "src.evaluation.reporter.upsert_evaluation_run", AsyncMock()
    ) as mock_upsert:
        await report.save_to_db(mock_pool)

    mock_upsert.assert_called_once_with(
        pool=mock_pool,
        dataset_size=10,
        results={"faithfulness": 0.8},
        metadata={},
    )
```
- **VALIDATE**: `uv run pytest tests/test_evaluation.py -v --tb=short`

---

## VALIDATION COMMANDS

```bash
# Level 1 — style
uv run ruff check src/evaluation/ scripts/evaluate.py scripts/export_dataset.py
uv run ruff format --check src/evaluation/ scripts/evaluate.py scripts/export_dataset.py

# Level 2 — new tests only
uv run pytest tests/test_evaluation.py -v --tb=short

# Level 3 — full regression
uv run pytest tests/ -v --tb=short

# Level 4 — smoke imports
uv run python -c "import src.evaluation.pipeline, src.evaluation.dataset, src.evaluation.reporter; print('ok')"
uv run python scripts/evaluate.py --help
uv run python scripts/export_dataset.py --help
```

## ACCEPTANCE CRITERIA

- [ ] `uv sync` resolves cleanly with ragas, fastmcp, langchain-openai
- [ ] `alembic upgrade head` shows migration `0002 -> 0003`
- [ ] `from src.db.queries import EvaluationRunRecord` works
- [ ] `from src.evaluation.metrics import DEFAULT_METRICS` works — 3 metrics
- [ ] `from src.evaluation.pipeline import run_evaluation` works
- [ ] `scripts/evaluate.py --help` exits 0
- [ ] `scripts/export_dataset.py --help` exits 0
- [ ] `tests/test_evaluation.py` all pass
- [ ] `uv run pytest tests/ -v` all pass (zero regressions)
- [ ] `uv run ruff check .` zero errors
