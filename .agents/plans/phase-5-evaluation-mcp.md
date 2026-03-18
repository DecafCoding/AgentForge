# Feature: Phase 5 — Evaluation & Quality (Ragas + FastMCP + Testing Patterns)

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Phase 5 adds three capabilities focused on agent quality measurement and interoperability:

1. **Ragas Evaluation Pipelines** — Measure agent quality with standardized metrics (faithfulness, response relevancy, context precision, context recall) against real agent interactions logged in Langfuse. Not theoretical — evaluation runs against real data.
2. **FastMCP Server Exposure** — Agent capabilities exposed as MCP (Model Context Protocol) tools, making them callable from MCP clients (Claude Desktop, Cursor, etc.) without knowing implementation details.
3. **Testing Patterns Documentation** — Comprehensive guide covering unit testing agents, integration testing multi-agent workflows, and evaluation as a continuous practice.

## User Story

As a Python developer building AI agents with AgentForge
I want to measure agent quality with standardized metrics and expose agent tools to the MCP ecosystem
So that I can continuously improve agent performance and compose agents with other AI systems

## Problem Statement

Phases 1–4 provide a fully functional agent stack, but no way to systematically measure agent quality or expose capabilities to the broader MCP ecosystem. Developers cannot answer "is my agent getting better or worse?" without manual testing, and agent tools are only accessible via the FastAPI HTTP API.

## Solution Statement

Add Ragas evaluation pipelines that extract real agent interactions from Langfuse traces and compute quality scores. Add a FastMCP server that wraps agent capabilities as MCP tools. Document comprehensive testing patterns covering every layer of the stack.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `src/evaluation/`, `src/mcp/`, `src/db/`, `scripts/`, `docs/`, `tests/`
**Dependencies**: `ragas>=0.2.0`, `fastmcp>=2.0.0`, `langchain-openai>=0.2.0` (for Ragas LLM wrapper), `datasets` pulled in transitively by ragas

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/agent/agent.py` (lines 65–129) — `run_agent()` pattern; note `result.output` (not `result.data`) for Pydantic AI structured output
- `src/agent/models.py` — `AgentResponse`, `Source` models used throughout; these are also the MCP tool return types
- `src/agent/tools.py` — Pattern for tool functions; MCP tools in `src/mcp/server.py` call the same DB query functions
- `src/db/queries.py` (lines 25–84) — Pydantic models for DB records (`VideoSummary`, `ChannelStats`); add `EvaluationRunRecord` here too; note `ChannelStats` not `ChannelRecord`
- `src/db/client.py` — `create_pool()` and `close_pool()` — MCP server standalone mode needs to call these directly
- `src/db/migrations/versions/0002_scraped_pages.py` — Migration pattern to follow for `0003_evaluation_runs.py`
- `src/observability/tracing.py` — `get_client()` returns `Langfuse | None`; evaluation dataset builder uses this same client
- `src/config.py` — All env var loading; add `EVAL_MODEL`, `EVAL_DATASET_LIMIT`, `MCP_TRANSPORT`, `MCP_PORT` here
- `src/api/main.py` — Lifespan pattern; MCP server uses its own lifespan, not this one
- `src/orchestration/graph.py` — `run_workflow(query, pool)` is the public entry point; returns `AgentResponse` directly (not a dict); `_build_graph()` is private
- `tests/conftest.py` — `mock_pool`, `mock_cache`, `mock_memory_store` fixtures; add `mock_langfuse` fixture for evaluation tests
- `tests/test_agent.py` — Mock pattern using `patch("src.agent.agent.agent.run", AsyncMock(...))` — follow this for test_mcp_server.py
- `.env.example` — Append Phase 5 section at the bottom
- `pyproject.toml` — Dependency format; append to existing `dependencies` list

### New Files to Create

**Evaluation module:**
- `src/evaluation/__init__.py` — Module marker
- `src/evaluation/dataset.py` — Extract Langfuse traces into Ragas `EvaluationDataset`
- `src/evaluation/pipeline.py` — Ragas `aevaluate()` wrapper
- `src/evaluation/metrics.py` — Metric selection and DEFAULT_METRICS constant
- `src/evaluation/reporter.py` — Results formatting + DB persistence

**MCP module:**
- `src/mcp/__init__.py` — Module marker
- `src/mcp/server.py` — FastMCP server with 4 tools + lifespan for DB pool

**Scripts:**
- `scripts/export_dataset.py` — Export agent interactions from Langfuse to JSON for offline use
- `scripts/evaluate.py` — Run evaluation pipeline, print report, optionally save to DB
- `scripts/mcp_server.py` — Standalone MCP server entry point

**Tests:**
- `tests/test_evaluation.py` — Evaluation pipeline unit tests (mocked Langfuse + Ragas)
- `tests/test_mcp_server.py` — MCP server tool unit tests (mocked DB + agents)
- `tests/test_patterns/__init__.py` — Package marker
- `tests/test_patterns/test_agent_unit.py` — Agent unit test patterns using TestModel
- `tests/test_patterns/test_agent_integration.py` — Integration test patterns
- `tests/test_patterns/test_workflow_e2e.py` — LangGraph workflow end-to-end patterns

**Docs:**
- `docs/testing-patterns.md` — Comprehensive testing guide
- `docs/evaluation-guide.md` — Running and interpreting evaluations
- `docs/mcp-integration.md` — Connecting MCP clients to AgentForge

**Migration:**
- `src/db/migrations/versions/0003_evaluation_runs.py` — `evaluation_runs` table

### Relevant Documentation — SHOULD READ BEFORE IMPLEMENTING

- [Ragas aevaluate() Reference](https://docs.ragas.io/en/stable/references/aevaluate/)
  - Use `aevaluate()` (async) not `evaluate()` (sync) — this is an async codebase
  - `aevaluate()` does NOT apply `nest_asyncio`, which is correct for production async apps
- [Ragas EvaluationDataset](https://docs.ragas.io/en/stable/references/evaluate/)
  - In Ragas 0.4.x, native dataset format uses `EvaluationDataset` + `SingleTurnSample`
  - HuggingFace `datasets.Dataset` still works via `column_map` parameter
  - New column names: `user_input` (was `question`), `response` (was `answer`), `retrieved_contexts` (was `contexts`)
- [Ragas Metrics](https://docs.ragas.io/en/stable/references/metrics/)
  - Import from `ragas.metrics`: `faithfulness`, `response_relevancy`, `context_precision`, `context_recall`
  - Note: Phase 5 spec uses `answer_relevancy` — the correct 0.4.x name is `response_relevancy`
- [FastMCP Getting Started](https://gofastmcp.com/getting-started/welcome)
  - `from fastmcp import FastMCP`; `@mcp.tool` decorator (no parentheses for basic tools)
  - `mcp.run()` for stdio (default transport for local clients like Claude Desktop)
  - `mcp.run(transport="http", port=8001)` for SSE/HTTP remote access
- [FastMCP Lifespan](https://gofastmcp.com/servers/lifespan)
  - Use `lifespan=` parameter on `FastMCP()` constructor for DB pool lifecycle
  - Access state via tool `Context` argument: `ctx.state.pool`
- [FastMCP FastAPI Integration](https://gofastmcp.com/integrations/fastapi)
  - `mcp.http_app(path="/")` returns an ASGI app mountable into FastAPI
  - `app.mount("/mcp", mcp.http_app(path="/"))` for co-hosting with FastAPI

### Patterns to Follow

**Module docstring pattern** (required for every new Python file):
```python
"""
Ragas evaluation pipeline.

Wraps Ragas aevaluate() for async compatibility. Accepts an EvaluationDataset
and returns a dict of metric name → score. This module belongs to the
Evaluation layer and may import from src.config only (no agent or collector
imports).
"""
```

**Config constant pattern** (src/config.py):
```python
EVAL_MODEL: str = os.getenv("EVAL_MODEL", "gpt-4o")
EVAL_DATASET_LIMIT: int = int(os.getenv("EVAL_DATASET_LIMIT", "100"))
```

**Migration pattern** (mirror `0002_scraped_pages.py`):
```python
revision: str = "0003"
down_revision: str = "0002"

def upgrade() -> None:
    op.execute("""CREATE TABLE evaluation_runs (...) """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS evaluation_runs")
```

**DB query function pattern** (src/db/queries.py):
```python
async def upsert_evaluation_run(
    pool: Pool,
    dataset_size: int,
    results: dict,
    metadata: dict | None = None,
) -> None:
    """Insert an evaluation run result for historical tracking."""
    import json
    await pool.execute(
        """INSERT INTO evaluation_runs (dataset_size, results, metadata)
           VALUES ($1, $2::jsonb, $3::jsonb)""",
        dataset_size,
        json.dumps(results),
        json.dumps(metadata or {}),
    )
```

**MCP lifespan pattern** (FastMCP 2.x):
```python
from contextlib import asynccontextmanager
from fastmcp import FastMCP, Context

@asynccontextmanager
async def lifespan(mcp: FastMCP):
    from src.db.client import create_pool, close_pool
    pool = await create_pool()
    mcp.state.pool = pool
    yield
    await close_pool(pool)

mcp = FastMCP("AgentForge", lifespan=lifespan)

@mcp.tool
async def ask_agent(question: str, ctx: Context) -> str:
    """..."""
    pool = ctx.state.pool
    result = await agent.run(question, deps=pool)
    return result.output.answer  # result.output not result.data
```

**Ragas EvaluationDataset pattern** (0.4.x):
```python
from ragas import EvaluationDataset, SingleTurnSample
from ragas.metrics import faithfulness, response_relevancy, context_precision

samples = [
    SingleTurnSample(
        user_input=s.question,
        response=s.answer,
        retrieved_contexts=s.contexts,
        reference=s.ground_truth,  # optional, enables context_recall
    )
    for s in eval_samples
]
dataset = EvaluationDataset(samples=samples)
result = await aevaluate(dataset=dataset, metrics=[faithfulness, response_relevancy])
```

**Logging pattern** (every module):
```python
import logging
logger = logging.getLogger(__name__)
```

**Error handling pattern** (graceful degradation):
```python
try:
    memory_client = await create_memory_client()
except Exception as exc:
    logger.error("Init failed — continuing without X", extra={"error": str(exc)})
    app.state.x = None
```

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation (deps + config + migration + DB)

Set up all infrastructure before writing feature code. Validation gates ensure nothing breaks before proceeding.

**Tasks:**
1. Add `ragas`, `fastmcp`, `datasets` to `pyproject.toml` and run `uv sync`
2. Add `EVAL_MODEL`, `EVAL_DATASET_LIMIT`, `MCP_TRANSPORT`, `MCP_PORT` to `src/config.py`
3. Add Phase 5 section to `.env.example`
4. Create Alembic migration `0003_evaluation_runs.py`
5. Add `EvaluationRunRecord`, `upsert_evaluation_run`, `get_evaluation_runs` to `src/db/queries.py`

### Phase 2: Evaluation Pipeline (PBI 5.1)

Build the Ragas evaluation stack from bottom up: metrics → dataset → pipeline → reporter → scripts.

**Tasks:**
6. Create `src/evaluation/__init__.py`
7. Create `src/evaluation/metrics.py` — metric definitions and DEFAULT_METRICS
8. Create `src/evaluation/dataset.py` — Langfuse trace extraction to `EvaluationDataset`
9. Create `src/evaluation/pipeline.py` — `run_evaluation()` wrapping `aevaluate()`
10. Create `src/evaluation/reporter.py` — `EvalReport` class with `summary()` and `save_to_db()`
11. Create `scripts/export_dataset.py` — CLI to export traces as JSON
12. Create `scripts/evaluate.py` — CLI to run evaluation and print/save results

### Phase 3: MCP Server (PBI 5.2)

Build the FastMCP server as a standalone module callable from scripts or mountable into FastAPI.

**Tasks:**
13. Create `src/mcp/__init__.py`
14. Create `src/mcp/server.py` — FastMCP server with lifespan (DB pool) and 4 tools
15. Create `scripts/mcp_server.py` — Standalone runner for local MCP clients

### Phase 4: Tests

Write all tests for the new modules using the existing mock patterns.

**Tasks:**
16. Create `tests/test_evaluation.py`
17. Create `tests/test_mcp_server.py`
18. Create `tests/test_patterns/__init__.py`
19. Create `tests/test_patterns/test_agent_unit.py`
20. Create `tests/test_patterns/test_agent_integration.py`
21. Create `tests/test_patterns/test_workflow_e2e.py`

### Phase 5: Documentation (PBI 5.3)

Write the three documentation files after the code is working — documentation should describe real, tested behavior.

**Tasks:**
22. Create `docs/testing-patterns.md`
23. Create `docs/evaluation-guide.md`
24. Create `docs/mcp-integration.md`

---

## STEP-BY-STEP TASKS

### Task 1: UPDATE `pyproject.toml` — add Phase 5 dependencies

- **ADD** to `dependencies` list (after the `redis` entry):
  ```toml
  # Evaluation (Phase 5)
  "ragas>=0.2.0",
  "fastmcp>=2.0.0",
  "langchain-openai>=0.2.0",
  ```
- **VALIDATE**: `uv sync` resolves without errors; `uv run python -c "import ragas, fastmcp; print('ok')"`
- **GOTCHA**: `ragas` pulls in `datasets` transitively — do NOT pin `datasets` explicitly as it may conflict with ragas's own constraint. FastMCP requires Python ≥ 3.10 — already satisfied by 3.12.
- **GOTCHA**: `langchain-openai` is required so Ragas can wrap the OpenAI LLM as a judge for metric computation. Without it, `aevaluate()` will fail unless `OPENAI_API_KEY` happens to be auto-detected via Ragas's own fallback — don't rely on that.

---

### Task 2: UPDATE `src/config.py` — add Phase 5 env vars

- **ADD** after the `REDIS_URL` block:
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
- **PATTERN**: Mirrors existing block format (e.g., `CACHE_ENABLED` block at line 92)
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
- **VALIDATE**: No validator needed — file is documentation.

---

### Task 4: CREATE `src/db/migrations/versions/0003_evaluation_runs.py`

- **IMPLEMENT**: Alembic migration creating `evaluation_runs` table
- **PATTERN**: Mirror `0002_scraped_pages.py` structure exactly
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
      op.execute("CREATE INDEX idx_eval_runs_ran_at ON evaluation_runs(ran_at DESC)")


  def downgrade() -> None:
      """Drop the evaluation_runs table."""
      op.execute("DROP TABLE IF EXISTS evaluation_runs")
  ```
- **VALIDATE**: `uv run alembic upgrade head` — should print `Running upgrade 0002 -> 0003`
- **GOTCHA**: Do NOT use `TIMESTAMPTZ DEFAULT NOW()` for `ran_at` in the INSERT — supply it explicitly so tests can control timestamps.

---

### Task 5: UPDATE `src/db/queries.py` — add evaluation run queries

- **ADD** at the bottom of the file (after the scraped page queries section):
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
- **IMPORTS**: `json` imported locally inside `upsert_evaluation_run` (matches pattern in `upsert_scraped_page` at line 303)
- **VALIDATE**: `uv run python -c "from src.db.queries import EvaluationRunRecord, upsert_evaluation_run; print('ok')"`

---

### Task 6: CREATE `src/evaluation/__init__.py`

- **IMPLEMENT**: Empty module marker with docstring
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

- **IMPLEMENT**: Metric definitions and default metric lists
  ```python
  """
  Ragas metric definitions for agent evaluation.

  Defines the default metric sets for unsupervised evaluation (no ground truth
  required) and supervised evaluation (ground truth annotations available).
  Import DEFAULT_METRICS or SUPERVISED_METRICS into the pipeline module.

  This module belongs to the Evaluation layer.
  """

  from ragas.metrics import (
      context_precision,
      faithfulness,
      response_relevancy,
  )
  from ragas.metrics import context_recall

  # Metrics that work without ground_truth — use for automated evaluation.
  DEFAULT_METRICS = [
      faithfulness,        # Is the answer supported by the retrieved context?
      response_relevancy,  # Is the answer relevant to the question?
      context_precision,   # Are the retrieved contexts ranked by relevance?
  ]

  # Additional metrics that require ground_truth annotations.
  SUPERVISED_METRICS = [
      context_recall,      # Did we retrieve all context needed to answer?
  ]
  ```
- **GOTCHA**: The Phase 5 spec mentions `answer_relevancy` — the correct Ragas 0.4.x name is `response_relevancy`. Import will fail if the wrong name is used. If `response_relevancy` import fails, try `answer_relevancy` — Ragas versions vary.
- **VALIDATE**: `uv run python -c "from src.evaluation.metrics import DEFAULT_METRICS; print(len(DEFAULT_METRICS))"`

---

### Task 8: CREATE `src/evaluation/dataset.py`

- **IMPLEMENT**: Extract Langfuse traces into a Ragas `EvaluationDataset`
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
  from ragas import EvaluationDataset, SingleTurnSample

  logger = logging.getLogger(__name__)


  class EvalSample(BaseModel):
      """Intermediate representation of one evaluation sample."""

      question: str
      answer: str
      contexts: list[str]
      ground_truth: Optional[str] = None


  def create_dataset_from_langfuse(
      limit: int = 100,
      trace_name: Optional[str] = None,
  ) -> EvaluationDataset:
      """Extract agent interactions from Langfuse traces into a Ragas dataset.

      Fetches traces from Langfuse, extracts input/output, and collects
      context strings from tool call child spans. Returns an EvaluationDataset
      ready for aevaluate(). Returns an empty dataset if Langfuse is not
      configured.

      Args:
          limit: Maximum number of traces to include.
          trace_name: Optional filter for trace name (e.g., "agent_run").

      Returns:
          EvaluationDataset with one SingleTurnSample per Langfuse trace.
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
                  retrieved_contexts=contexts if contexts else [""],
              )
          )

      logger.info("Built evaluation dataset", extra={"samples": len(samples)})
      return EvaluationDataset(samples=samples)
  ```
- **GOTCHA**: `retrieved_contexts` must be a non-empty list — Ragas raises if it's empty. Default to `[""]` when no tool contexts were captured.
- **GOTCHA**: Langfuse observation `type` field is uppercase `"TOOL"` in v2, not lowercase.
- **IMPORTS**: `get_client` imported inside function to avoid circular imports and to allow lazy Langfuse init.
- **VALIDATE**: `uv run python -c "from src.evaluation.dataset import create_dataset_from_langfuse; print('ok')"`

---

### Task 9: CREATE `src/evaluation/pipeline.py`

- **IMPLEMENT**: Async Ragas evaluation runner
  ```python
  """
  Ragas evaluation pipeline.

  Wraps Ragas aevaluate() for async use in an asyncio application.
  Returns a flat dict of metric name → float score suitable for storage
  and display. This module belongs to the Evaluation layer.
  """

  import logging
  from typing import Optional

  from langchain_openai import ChatOpenAI
  from ragas import EvaluationDataset, aevaluate
  from ragas.llms import LangchainLLMWrapper

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
                   SUPERVISED_METRICS automatically when reference (ground_truth)
                   is present in the samples.

      Returns:
          Dict mapping metric name to average score across the dataset.
      """
      if len(dataset) == 0:
          logger.warning("Empty evaluation dataset — returning zero scores")
          return {}

      if metrics is None:
          has_reference = any(
              s.reference is not None for s in dataset.samples
          )
          metrics = DEFAULT_METRICS + SUPERVISED_METRICS if has_reference else DEFAULT_METRICS

      logger.info(
          "Running evaluation",
          extra={
              "samples": len(dataset),
              "metrics": [m.name for m in metrics],
          },
      )

      # Wrap the configured model as a Ragas-compatible LLM judge.
      # Ragas uses this LLM internally to compute metric scores.
      llm = LangchainLLMWrapper(ChatOpenAI(model=EVAL_MODEL, api_key=OPENAI_API_KEY))

      result = await aevaluate(dataset=dataset, metrics=metrics, llm=llm)
      scores: dict[str, float] = result.to_pandas().mean().to_dict()

      logger.info("Evaluation complete", extra={"scores": scores})
      return scores
  ```
- **GOTCHA**: Use `aevaluate()` not `evaluate()`. The sync `evaluate()` applies `nest_asyncio` internally which can break in production async contexts.
- **GOTCHA**: `result.to_pandas().mean()` produces a pandas Series — `.to_dict()` converts to `{metric_name: float}`.
- **VALIDATE**: `uv run python -c "from src.evaluation.pipeline import run_evaluation; print('ok')"`

---

### Task 10: CREATE `src/evaluation/reporter.py`

- **IMPLEMENT**: Evaluation results formatting and DB persistence
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

- **IMPLEMENT**: CLI to export Langfuse interactions as JSON for offline use
  ```python
  """Export agent interactions from Langfuse to a JSON file for offline evaluation.

  Usage:
      uv run python scripts/export_dataset.py --limit 50 --trace-name agent_run
      uv run python scripts/export_dataset.py --output eval_data.json
  """

  import argparse
  import asyncio
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
          "--limit",
          type=int,
          default=100,
          help="Maximum number of traces to export (default: 100)",
      )
      parser.add_argument(
          "--trace-name",
          type=str,
          default=None,
          help="Filter by trace name (e.g., 'agent_run')",
      )
      parser.add_argument(
          "--output",
          type=str,
          default="eval_dataset.json",
          help="Output JSON file path (default: eval_dataset.json)",
      )
      args = parser.parse_args()

      from src.evaluation.dataset import create_dataset_from_langfuse

      dataset = create_dataset_from_langfuse(
          limit=args.limit,
          trace_name=args.trace_name,
      )

      if len(dataset) == 0:
          logger.warning("No samples found — check Langfuse configuration and trace filters")
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

- **IMPLEMENT**: CLI to run evaluation and print/save results
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
      parser = argparse.ArgumentParser(description="Run Ragas agent evaluation pipeline")
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

### Task 13: CREATE `src/mcp/__init__.py`

- **IMPLEMENT**: Module marker with docstring
  ```python
  """
  MCP (Model Context Protocol) server exposure.

  Exposes AgentForge agent capabilities as MCP tools, making them callable
  from any MCP-compatible client (Claude Desktop, Cursor, etc.). Built on
  FastMCP 2.x. This module belongs to the Application layer and may import
  from the Agent and Orchestration layers.
  """
  ```
- **VALIDATE**: `uv run python -c "import src.mcp; print('ok')"`

---

### Task 14: CREATE `src/mcp/server.py`

- **IMPLEMENT**: FastMCP server with 4 tools and DB pool lifespan
  ```python
  """
  FastMCP server definition.

  Exposes four AgentForge capabilities as MCP tools:
  - ask_agent: Single-agent question answering (Pattern 1)
  - search_videos: Direct database video search (no LLM)
  - get_channel_summary: Channel statistics
  - run_research_workflow: Multi-agent LangGraph workflow (Pattern 2)

  The server manages its own asyncpg pool via a lifespan context manager.
  Run via scripts/mcp_server.py (stdio) or mount into FastAPI (HTTP/SSE).

  This module belongs to the Application layer.
  """

  import logging
  from contextlib import asynccontextmanager
  from typing import Any

  from fastmcp import Context, FastMCP

  logger = logging.getLogger(__name__)


  @asynccontextmanager
  async def lifespan(mcp: FastMCP):
      """Create and close the database pool for the MCP server lifecycle.

      The pool is stored on mcp.state.pool and accessed by tools via ctx.state.pool.
      """
      from src.db.client import close_pool, create_pool

      logger.info("MCP server starting up — creating database pool")
      pool = await create_pool()
      mcp.state.pool = pool
      yield
      logger.info("MCP server shutting down — closing database pool")
      await close_pool(pool)


  mcp = FastMCP("AgentForge", lifespan=lifespan)


  @mcp.tool
  async def ask_agent(question: str, ctx: Context) -> str:
      """Ask the YouTube research agent a question.

      The agent queries a database of YouTube video metadata and transcripts
      to provide source-cited answers about content trends, video performance,
      and channel analytics. Uses Pydantic AI Pattern 1 (single agent with tools).

      Args:
          question: Natural-language question about YouTube content.

      Returns:
          The agent's answer as a plain string.
      """
      from src.agent.agent import agent

      pool = ctx.state.pool
      result = await agent.run(question, deps=pool)
      return result.output.answer


  @mcp.tool
  async def search_videos(ctx: Context, query: str, limit: int = 5) -> list[dict[str, Any]]:
      """Search the video database for videos matching a query.

      Performs full-text search against video titles and descriptions.
      Returns video summaries without LLM reasoning — faster and cheaper
      than ask_agent for simple lookup tasks.

      Args:
          query: Search terms to match against video titles and descriptions.
          limit: Maximum number of results to return (default 5, max 20).

      Returns:
          List of video summary dicts with title, video_id, url, and view_count.
      """
      from src.db.queries import search_videos as db_search_videos

      pool = ctx.state.pool
      limit = min(limit, 20)
      videos = await db_search_videos(pool, query, limit)
      return [v.model_dump() for v in videos]


  @mcp.tool
  async def get_channel_summary(channel_id: str, ctx: Context) -> dict[str, Any] | str:
      """Get a summary of a YouTube channel's content and performance metrics.

      Returns aggregate statistics including video count, total views,
      and most recent upload date.

      Args:
          channel_id: YouTube channel identifier (e.g. UCxxxxxx).

      Returns:
          Channel statistics dict, or an error message if not tracked.
      """
      from src.db.queries import get_channel_stats

      pool = ctx.state.pool
      stats = await get_channel_stats(pool, channel_id)
      if stats is None:
          return f"Channel '{channel_id}' is not tracked in the database."
      return stats.model_dump(mode="json")


  @mcp.tool
  async def run_research_workflow(query: str, ctx: Context) -> str:
      """Run the multi-agent research workflow (research → analysis → synthesis).

      Uses the LangGraph Pattern 2 pipeline: a research agent gathers data,
      an analysis agent evaluates quality, and a synthesis agent produces
      the final answer. Slower than ask_agent but produces higher-quality
      responses for complex research questions.

      Args:
          query: Natural-language research query.

      Returns:
          Synthesised answer string from the workflow.
      """
      from src.orchestration.graph import run_workflow

      pool = ctx.state.pool
      result = await run_workflow(query, pool)
      return result.answer
  ```
- **GOTCHA**: `Context` must be a parameter in the tool function for FastMCP to inject it — position matters. For `search_videos` and `get_channel_summary`, put `ctx: Context` before `query`/`channel_id` if FastMCP requires it first, OR place it last. Check FastMCP docs — in 2.x, `ctx: Context` can be in any position.
- **GOTCHA**: `run_workflow` returns `AgentResponse` (not a dict) — use `result.answer`, not `result.get("final_answer")`. See `src/orchestration/graph.py:102-114`.
- **GOTCHA**: `result.output.answer` for Pydantic AI — `result.data` is the old pre-1.0 API.
- **VALIDATE**: `uv run python -c "from src.mcp.server import mcp; print(mcp.name)"`

---

### Task 15: CREATE `scripts/mcp_server.py`

- **IMPLEMENT**: Standalone runner for the MCP server
  ```python
  """Start the AgentForge MCP server as a standalone process.

  Supports both stdio transport (for local MCP clients like Claude Desktop)
  and HTTP transport (for remote clients).

  Usage:
      # stdio (for Claude Desktop / local clients):
      uv run python scripts/mcp_server.py

      # HTTP (for remote / Cursor / custom clients):
      uv run python scripts/mcp_server.py --transport http

  Claude Desktop config (~/.config/claude/claude_desktop_config.json):
      {
        "mcpServers": {
          "agentforge": {
            "command": "uv",
            "args": ["run", "python", "scripts/mcp_server.py"],
            "cwd": "/absolute/path/to/agentforge"
          }
        }
      }
  """

  import argparse
  import logging

  logging.basicConfig(level=logging.INFO)


  def main() -> None:
      """Parse args and start the MCP server."""
      parser = argparse.ArgumentParser(description="Start the AgentForge MCP server")
      parser.add_argument(
          "--transport",
          choices=["stdio", "http"],
          default=None,
          help="Transport protocol (default: reads MCP_TRANSPORT env var, falls back to stdio)",
      )
      parser.add_argument(
          "--port",
          type=int,
          default=None,
          help="Port for HTTP transport (default: reads MCP_PORT env var, falls back to 8001)",
      )
      args = parser.parse_args()

      from src.config import MCP_PORT, MCP_TRANSPORT
      from src.mcp.server import mcp

      transport = args.transport or MCP_TRANSPORT
      port = args.port or MCP_PORT

      if transport == "http":
          mcp.run(transport="http", port=port)
      else:
          mcp.run()  # stdio is the default


  if __name__ == "__main__":
      main()
  ```
- **VALIDATE**: `uv run python scripts/mcp_server.py --help`

---

### Task 16: CREATE `tests/test_evaluation.py`

- **IMPLEMENT**: Unit tests for evaluation pipeline (all mocked)
  ```python
  """
  Evaluation pipeline tests.

  Tests the evaluation module components using mocked Langfuse and Ragas
  dependencies. No real LLM calls or Langfuse connections are made.
  """

  from unittest.mock import MagicMock, patch

  import pytest
  from ragas import EvaluationDataset, SingleTurnSample


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
      """Dataset creation returns an empty EvaluationDataset when Langfuse is None."""
      with patch("src.evaluation.dataset.get_client", return_value=None):
          from src.evaluation.dataset import create_dataset_from_langfuse

          dataset = create_dataset_from_langfuse(limit=10)

      assert len(dataset) == 0


  def test_create_dataset_skips_traces_with_missing_input():
      """Traces with empty question or answer are skipped."""
      mock_trace = MagicMock()
      mock_trace.id = "trace-1"
      mock_trace.input = {}  # empty input
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
      """Valid traces produce one sample per trace."""
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


  # ---------------------------------------------------------------------------
  # run_evaluation
  # ---------------------------------------------------------------------------


  async def test_run_evaluation_returns_empty_dict_for_empty_dataset():
      """run_evaluation() returns empty dict when dataset has no samples."""
      from src.evaluation.pipeline import run_evaluation

      empty_dataset = EvaluationDataset(samples=[])
      result = await run_evaluation(empty_dataset)
      assert result == {}


  async def test_run_evaluation_calls_aevaluate_with_default_metrics():
      """run_evaluation() calls aevaluate() with DEFAULT_METRICS when none specified."""
      from src.evaluation.metrics import DEFAULT_METRICS

      dataset = EvaluationDataset(
          samples=[
              SingleTurnSample(
                  user_input="Q?", response="A.", retrieved_contexts=["context"]
              )
          ]
      )

      mock_result = MagicMock()
      mock_df = MagicMock()
      mock_df.mean.return_value.to_dict.return_value = {"faithfulness": 0.9}
      mock_result.to_pandas.return_value = mock_df

      with patch("src.evaluation.pipeline.aevaluate", return_value=mock_result) as mock_eval:
          from src.evaluation.pipeline import run_evaluation

          scores = await run_evaluation(dataset)

      mock_eval.assert_called_once()
      call_kwargs = mock_eval.call_args.kwargs
      assert call_kwargs["metrics"] == DEFAULT_METRICS
      assert scores == {"faithfulness": 0.9}


  # ---------------------------------------------------------------------------
  # EvalReport
  # ---------------------------------------------------------------------------


  def test_eval_report_summary_formats_correctly():
      """EvalReport.summary() produces a readable string with metric scores."""
      from src.evaluation.reporter import EvalReport

      report = EvalReport(
          results={"faithfulness": 0.85, "response_relevancy": 0.92},
          dataset_size=50,
      )
      summary = report.summary()

      assert "50 samples" in summary
      assert "faithfulness: 0.850" in summary
      assert "response_relevancy: 0.920" in summary


  async def test_eval_report_save_to_db_calls_upsert(mock_pool):
      """EvalReport.save_to_db() calls upsert_evaluation_run with correct args."""
      from src.evaluation.reporter import EvalReport

      report = EvalReport(results={"faithfulness": 0.8}, dataset_size=10)

      with patch(
          "src.evaluation.reporter.upsert_evaluation_run"
      ) as mock_upsert:
          from unittest.mock import AsyncMock

          mock_upsert = AsyncMock()
          with patch("src.evaluation.reporter.upsert_evaluation_run", mock_upsert):
              await report.save_to_db(mock_pool)

      mock_upsert.assert_called_once_with(
          pool=mock_pool,
          dataset_size=10,
          results={"faithfulness": 0.8},
          metadata={},
      )
  ```
- **PATTERN**: Mirrors `tests/test_agent.py` mock-everything approach
- **VALIDATE**: `uv run pytest tests/test_evaluation.py -v`

---

### Task 17: CREATE `tests/test_mcp_server.py`

- **IMPLEMENT**: MCP server tool unit tests
  ```python
  """
  MCP server tool tests.

  Tests each MCP tool function directly by mocking the underlying
  agent, workflow, and database calls. No real MCP transport is involved.
  """

  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest


  def _make_mock_ctx(pool):
      """Build a mock FastMCP Context with a pool on state."""
      ctx = MagicMock()
      ctx.state = MagicMock()
      ctx.state.pool = pool
      return ctx


  # ---------------------------------------------------------------------------
  # ask_agent
  # ---------------------------------------------------------------------------


  async def test_ask_agent_returns_answer_string(mock_pool):
      """ask_agent tool calls agent.run() and returns the answer field."""
      from src.agent.models import AgentResponse, Source

      mock_output = AgentResponse(
          answer="The latest video is about Python.",
          sources=[Source(title="Python Tutorial", video_id="abc", url="http://yt.be/abc")],
          confidence=0.9,
      )
      mock_result = MagicMock()
      mock_result.output = mock_output

      ctx = _make_mock_ctx(mock_pool)

      with patch("src.mcp.server.agent") as mock_agent:
          mock_agent.run = AsyncMock(return_value=mock_result)

          from src.mcp.server import ask_agent

          result = await ask_agent("What is the latest video?", ctx)

      assert result == "The latest video is about Python."
      mock_agent.run.assert_called_once_with("What is the latest video?", deps=mock_pool)


  # ---------------------------------------------------------------------------
  # search_videos
  # ---------------------------------------------------------------------------


  async def test_search_videos_returns_list_of_dicts(mock_pool):
      """search_videos tool returns serialised VideoSummary dicts."""
      from datetime import datetime

      from src.db.queries import VideoSummary

      mock_videos = [
          VideoSummary(
              video_id="vid1",
              channel_id="UCxyz",
              title="Python Tutorial",
              published_at=datetime(2026, 1, 1),
              view_count=1000,
          )
      ]

      ctx = _make_mock_ctx(mock_pool)

      with patch("src.mcp.server.db_search_videos", AsyncMock(return_value=mock_videos)):
          from src.mcp.server import search_videos

          result = await search_videos(ctx, "python", limit=5)

      assert len(result) == 1
      assert result[0]["video_id"] == "vid1"
      assert result[0]["title"] == "Python Tutorial"


  # ---------------------------------------------------------------------------
  # get_channel_summary
  # ---------------------------------------------------------------------------


  async def test_get_channel_summary_returns_stats_dict(mock_pool):
      """get_channel_summary returns channel stats as a dict."""
      from datetime import datetime

      from src.db.queries import ChannelStats

      mock_stats = ChannelStats(
          channel_id="UCxyz",
          channel_name="Test Channel",
          video_count=42,
          total_views=100000,
          latest_video_at=datetime(2026, 1, 15),
      )

      ctx = _make_mock_ctx(mock_pool)

      with patch("src.mcp.server.get_channel_stats", AsyncMock(return_value=mock_stats)):
          from src.mcp.server import get_channel_summary

          result = await get_channel_summary("UCxyz", ctx)

      assert isinstance(result, dict)
      assert result["channel_name"] == "Test Channel"
      assert result["video_count"] == 42


  async def test_get_channel_summary_returns_string_when_not_found(mock_pool):
      """get_channel_summary returns descriptive string for unknown channel."""
      ctx = _make_mock_ctx(mock_pool)

      with patch("src.mcp.server.get_channel_stats", AsyncMock(return_value=None)):
          from src.mcp.server import get_channel_summary

          result = await get_channel_summary("UCunknown", ctx)

      assert isinstance(result, str)
      assert "UCunknown" in result


  # ---------------------------------------------------------------------------
  # run_research_workflow
  # ---------------------------------------------------------------------------


  async def test_run_research_workflow_returns_answer(mock_pool):
      """run_research_workflow calls run_workflow and returns answer string."""
      from src.agent.models import AgentResponse

      mock_response = AgentResponse(answer="Research complete.", sources=[], confidence=0.7)
      ctx = _make_mock_ctx(mock_pool)

      with patch("src.mcp.server.run_workflow", AsyncMock(return_value=mock_response)):
          from src.mcp.server import run_research_workflow

          result = await run_research_workflow("Research AI trends", ctx)

      assert result == "Research complete."
  ```
- **GOTCHA**: `db_search_videos` import in `src/mcp/server.py` is `from src.db.queries import search_videos as db_search_videos` — mock the alias name in the server module namespace.
- **VALIDATE**: `uv run pytest tests/test_mcp_server.py -v`

---

### Task 18: CREATE `tests/test_patterns/__init__.py`

- **IMPLEMENT**: Empty module marker
  ```python
  """Example test patterns for AgentForge documentation."""
  ```
- **VALIDATE**: `uv run python -c "import tests.test_patterns; print('ok')"`

---

### Task 19: CREATE `tests/test_patterns/test_agent_unit.py`

- **IMPLEMENT**: Documented unit test patterns for agents (PBI 5.3 artifact)
  ```python
  """
  Agent unit test patterns.

  Reference examples demonstrating how to unit-test Pydantic AI agents
  without making real LLM calls. These tests are the concrete examples
  referenced in docs/testing-patterns.md.

  Key patterns:
  - Mock agent.run() to return a controlled AgentResponse
  - Use MagicMock(spec=RunContext) for tool context injection
  - Patch get_langfuse() to None to disable tracing in unit tests
  """

  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest


  def _make_agent_response(answer: str = "Test answer", confidence: float = 0.9):
      """Build a minimal AgentResponse for test use."""
      from src.agent.models import AgentResponse, Source

      return AgentResponse(
          answer=answer,
          sources=[Source(title="Video", video_id="v1", url="https://yt.be/v1")],
          confidence=confidence,
      )


  async def test_agent_returns_structured_output_shape(mock_pool):
      """run_agent() always returns an AgentResponse — never a raw string."""
      expected = _make_agent_response()
      mock_result = MagicMock()
      mock_result.output = expected

      with (
          patch("src.agent.agent.get_langfuse", return_value=None),
          patch("src.agent.agent.agent.run", AsyncMock(return_value=mock_result)),
      ):
          from src.agent.agent import run_agent

          result = await run_agent("Any question", mock_pool)

      assert hasattr(result, "answer")
      assert hasattr(result, "sources")
      assert hasattr(result, "confidence")
      assert isinstance(result.sources, list)


  async def test_agent_tool_receives_pool_from_deps(mock_pool):
      """Agent tools receive the pool via RunContext.deps — not as a global."""
      from pydantic_ai import RunContext

      from src.agent.tools import query_recent_videos

      ctx = MagicMock(spec=RunContext)
      ctx.deps = mock_pool

      with patch("src.agent.tools.get_videos", AsyncMock(return_value=[])) as mock_get:
          await query_recent_videos(ctx, channel_id="UCtest", limit=5)
          mock_get.assert_called_once_with(mock_pool, "UCtest", 5)


  def test_collector_module_has_no_llm_imports():
      """Collector must never import pydantic_ai, langfuse, or openai."""
      import ast
      import importlib.util

      import src.collector.youtube as mod

      source_file = importlib.util.find_spec(mod.__name__).origin
      with open(source_file) as f:
          tree = ast.parse(f.read())

      forbidden = {"pydantic_ai", "langfuse", "openai"}
      for node in ast.walk(tree):
          if isinstance(node, ast.Import):
              for alias in node.names:
                  assert alias.name.split(".")[0] not in forbidden, (
                      f"Collector imports forbidden module: {alias.name}"
                  )
          elif isinstance(node, ast.ImportFrom):
              module = (node.module or "").split(".")[0]
              assert module not in forbidden, (
                  f"Collector imports forbidden module: {node.module}"
              )
  ```
- **PATTERN**: Mirrors patterns in `tests/test_agent.py` (lines 69-107) and `tests/test_collector.py`
- **VALIDATE**: `uv run pytest tests/test_patterns/test_agent_unit.py -v`

---

### Task 20: CREATE `tests/test_patterns/test_agent_integration.py`

- **IMPLEMENT**: Integration test patterns for the full API stack
  ```python
  """
  Agent integration test patterns.

  Reference examples for testing the full API stack end-to-end using an
  httpx AsyncClient backed by the FastAPI ASGI app. The database pool and
  LLM are mocked so no external services are needed.

  These are the concrete examples referenced in docs/testing-patterns.md.
  """

  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest


  async def test_ask_endpoint_returns_200_with_valid_question(client):
      """POST /api/ask with a valid question should return 200 and structured JSON."""
      from src.agent.models import AgentResponse, Source

      mock_response = AgentResponse(
          answer="The channel has covered Python, FastAPI, and AI.",
          sources=[Source(title="Python Tutorial", video_id="abc", url="https://yt.be/abc")],
          confidence=0.85,
      )

      with patch("src.api.routes.run_agent", AsyncMock(return_value=mock_response)):
          response = await client.post(
              "/api/ask", json={"question": "What topics has this channel covered?"}
          )

      assert response.status_code == 200
      body = response.json()
      assert "answer" in body
      assert "sources" in body
      assert len(body["sources"]) == 1


  async def test_ask_endpoint_returns_500_when_agent_raises(client):
      """POST /api/ask should return 500 when the agent raises an exception."""
      with patch(
          "src.api.routes.run_agent",
          AsyncMock(side_effect=RuntimeError("model timeout")),
      ):
          response = await client.post("/api/ask", json={"question": "Test"})

      assert response.status_code == 500


  async def test_health_endpoint_returns_ok(client):
      """GET /health should return 200 and status ok."""
      response = await client.get("/health")
      assert response.status_code == 200
      assert response.json()["status"] == "ok"
  ```
- **PATTERN**: Uses `client` fixture from `tests/conftest.py` (lines 54-89)
- **VALIDATE**: `uv run pytest tests/test_patterns/test_agent_integration.py -v`

---

### Task 21: CREATE `tests/test_patterns/test_workflow_e2e.py`

- **IMPLEMENT**: LangGraph multi-agent workflow test patterns
  ```python
  """
  Multi-agent workflow end-to-end test patterns.

  Reference examples for testing LangGraph workflows. Mocks individual
  agent nodes to verify graph routing logic (including the conditional
  retry edge) without real LLM calls.

  These are the concrete examples referenced in docs/testing-patterns.md.
  """

  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest


  async def test_workflow_returns_agent_response_shape(mock_pool):
      """run_workflow() returns an AgentResponse with answer, sources, confidence."""
      from src.agent.models import AgentResponse

      with (
          patch("src.orchestration.graph.get_langfuse", return_value=None),
          patch(
              "src.orchestration.graph._graph.ainvoke",
              AsyncMock(
                  return_value={
                      "final_answer": "Synthesised answer.",
                      "final_sources": ["vid1"],
                      "final_confidence": 0.8,
                      "steps_completed": 3,
                  }
              ),
          ),
      ):
          from src.orchestration.graph import run_workflow

          result = await run_workflow("Research query", mock_pool)

      assert isinstance(result, AgentResponse)
      assert result.answer == "Synthesised answer."
      assert result.confidence == 0.8
      assert len(result.sources) == 1


  async def test_workflow_returns_default_response_when_no_final_answer(mock_pool):
      """run_workflow() returns a fallback response when final_answer is None."""
      with (
          patch("src.orchestration.graph.get_langfuse", return_value=None),
          patch(
              "src.orchestration.graph._graph.ainvoke",
              AsyncMock(
                  return_value={
                      "final_answer": None,
                      "final_sources": [],
                      "final_confidence": None,
                      "steps_completed": 1,
                  }
              ),
          ),
      ):
          from src.orchestration.graph import run_workflow

          result = await run_workflow("Research query", mock_pool)

      assert "sufficient" in result.answer.lower()
      assert result.confidence == 0.1
  ```
- **PATTERN**: Patches `_graph.ainvoke` directly — mirrors pattern in `tests/test_orchestration.py`
- **VALIDATE**: `uv run pytest tests/test_patterns/test_workflow_e2e.py -v`

---

### Task 22: CREATE `docs/testing-patterns.md`

- **IMPLEMENT**: Comprehensive testing guide covering all layers
- **CONTENT** must cover:
  1. **When to unit test vs integration test vs e2e** — decision table
  2. **Mocking Pydantic AI agents** — `patch("src.agent.agent.agent.run", AsyncMock(...))`, using `mock_result.output` not `mock_result.data`
  3. **Testing the collector/reasoning boundary** — `ast` module import inspection pattern (from `test_agent_unit.py`)
  4. **Testing LangGraph workflows** — patch `_graph.ainvoke` to control state output
  5. **Using the shared fixtures** — `mock_pool`, `mock_cache`, `mock_memory_store`, `client` from `conftest.py`
  6. **Running evaluations in CI** — Document as a scheduled workflow, not on every PR push
  7. **Interpreting Ragas metrics** — What faithfulness ≥ 0.8 means in practice
  8. Reference all test files in `tests/test_patterns/` as concrete examples
- **VALIDATE**: File exists and is readable markdown

---

### Task 23: CREATE `docs/evaluation-guide.md`

- **IMPLEMENT**: Guide for running and interpreting Ragas evaluations
- **CONTENT** must cover:
  1. **Prerequisites** — Langfuse configured, `OPENAI_API_KEY` set for Ragas LLM evaluator, `EVAL_MODEL` configured
  2. **Running your first evaluation** — `uv run python scripts/evaluate.py --limit 20`
  3. **Exporting dataset for offline use** — `uv run python scripts/export_dataset.py`
  4. **Saving results to DB** — `--save-to-db` flag and querying `evaluation_runs` table
  5. **Interpreting the metrics** table:
     - Faithfulness ≥ 0.8 → answers are grounded in retrieved context
     - Response Relevancy ≥ 0.7 → answers address the question asked
     - Context Precision ≥ 0.6 → retrieved contexts are relevant
     - Context Recall (requires ground truth) → how much relevant context was captured
  6. **When evaluations are meaningful** — need ≥20 samples for stable scores
  7. **Acting on low scores** — faithfulness low → improve system prompt; context_precision low → improve search query generation
  8. **Adding ground truth** — how to annotate samples for supervised metrics
- **VALIDATE**: File exists and is readable markdown

---

### Task 24: CREATE `docs/mcp-integration.md`

- **IMPLEMENT**: Guide for connecting MCP clients to AgentForge
- **CONTENT** must cover:
  1. **What MCP enables** — any MCP client can use agent tools without knowing the implementation
  2. **Available tools** — table of 4 tools with descriptions
  3. **Running the MCP server** — `uv run python scripts/mcp_server.py`
  4. **Claude Desktop configuration** — exact JSON for `claude_desktop_config.json`
  5. **HTTP transport** — `uv run python scripts/mcp_server.py --transport http`
  6. **Mounting into FastAPI** — code snippet using `mcp.http_app()` + `app.mount()`
  7. **Which tools to expose vs keep internal** — security guidance (expose read-only, not mutation tools)
  8. **Testing MCP connectivity** — programmatic MCP client test
- **VALIDATE**: File exists and is readable markdown

---

## TESTING STRATEGY

### Unit Tests

All tests mock external dependencies (DB, LLM, Langfuse, Ragas). Tests run in CI without any external services.

- `tests/test_evaluation.py` — mocked Langfuse + mocked Ragas `aevaluate()`
- `tests/test_mcp_server.py` — mocked agent, DB queries, and workflow
- `tests/test_patterns/test_agent_unit.py` — mocked `agent.run()` + `RunContext`
- Boundary verification test: collector must not import `pydantic_ai`, `langfuse`, or `openai`

### Integration Tests

- `tests/test_patterns/test_agent_integration.py` — full ASGI stack with mocked LLM
- `tests/test_patterns/test_workflow_e2e.py` — full graph execution with mocked `ainvoke`

### Edge Cases

- Empty Langfuse dataset → `run_evaluation()` returns `{}`
- Langfuse not configured → `create_dataset_from_langfuse()` returns empty dataset (no crash)
- Trace with missing question or answer → sample is skipped (not added to dataset)
- Tool contexts empty → `retrieved_contexts` defaults to `[""]` (Ragas requires non-empty list)
- MCP channel not found → `get_channel_summary()` returns descriptive string (not None or exception)
- `run_workflow()` returns `AgentResponse` with `final_answer=None` → fallback message used

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
# Lint all new files
uv run ruff check src/evaluation/ src/mcp/ scripts/evaluate.py scripts/export_dataset.py scripts/mcp_server.py

# Format check
uv run ruff format --check src/evaluation/ src/mcp/ tests/test_evaluation.py tests/test_mcp_server.py tests/test_patterns/

# Auto-fix any style issues
uv run ruff check --fix src/evaluation/ src/mcp/
uv run ruff format src/evaluation/ src/mcp/ tests/test_evaluation.py tests/test_mcp_server.py tests/test_patterns/
```

**Expected**: All pass with exit code 0

### Level 2: Unit Tests (new modules only)

```bash
# Evaluation tests
uv run pytest tests/test_evaluation.py -v --tb=short

# MCP server tests
uv run pytest tests/test_mcp_server.py -v --tb=short

# Test patterns
uv run pytest tests/test_patterns/ -v --tb=short
```

**Expected**: All tests pass

### Level 3: Full Test Suite (regression check)

```bash
uv run pytest tests/ -v --tb=short
```

**Expected**: All existing Phase 1–4 tests still pass; new tests also pass

### Level 4: Migration Validation

```bash
# Run migration (requires running Postgres)
uv run alembic upgrade head

# Verify rollback works
uv run alembic downgrade -1
uv run alembic upgrade head
```

**Expected**: `Running upgrade 0002 -> 0003, Add evaluation_runs table`

### Level 5: Smoke Tests

```bash
# Config loads cleanly
uv run python -c "from src.config import EVAL_MODEL, MCP_PORT; print(EVAL_MODEL, MCP_PORT)"

# All new modules import cleanly
uv run python -c "import src.evaluation.pipeline, src.evaluation.dataset, src.mcp.server; print('ok')"

# MCP server starts and exposes tools (verify help output)
uv run python scripts/mcp_server.py --help
uv run python scripts/evaluate.py --help
uv run python scripts/export_dataset.py --help

# Lint the full project (no regressions)
uv run ruff check .
```

---

## ACCEPTANCE CRITERIA

- [ ] `ragas>=0.4.0` and `fastmcp>=2.0.0` are in `pyproject.toml` and resolve via `uv sync`
- [ ] `src/config.py` exports `EVAL_MODEL`, `EVAL_DATASET_LIMIT`, `MCP_TRANSPORT`, `MCP_PORT`
- [ ] Migration `0003_evaluation_runs.py` runs cleanly (`alembic upgrade head`)
- [ ] `EvaluationRunRecord`, `upsert_evaluation_run`, `get_evaluation_runs` are in `src/db/queries.py`
- [ ] `scripts/export_dataset.py` runs and prints help without errors
- [ ] `scripts/evaluate.py` runs and prints help without errors; returns empty-dataset message gracefully when Langfuse is not configured
- [ ] `src/mcp/server.py` defines `mcp` with exactly 4 tools: `ask_agent`, `search_videos`, `get_channel_summary`, `run_research_workflow`
- [ ] `scripts/mcp_server.py` starts without error when `--help` is passed
- [ ] All tools use `result.output.answer` (Pydantic AI ≥ 1.0) not `result.data`
- [ ] `run_research_workflow` returns `result.answer` from `AgentResponse` (not dict access)
- [ ] `tests/test_evaluation.py` passes with `pytest -v`
- [ ] `tests/test_mcp_server.py` passes with `pytest -v`
- [ ] `tests/test_patterns/` all pass with `pytest -v`
- [ ] `uv run pytest tests/ -v` — all tests pass (zero regressions)
- [ ] `uv run ruff check .` — passes with zero errors
- [ ] `docs/testing-patterns.md`, `docs/evaluation-guide.md`, `docs/mcp-integration.md` exist
- [ ] `tests/test_patterns/__init__.py` exists (makes it a proper package)

---

## COMPLETION CHECKLIST

- [ ] All 24 tasks completed in order
- [ ] `uv sync` resolves cleanly after Task 1
- [ ] `uv run alembic upgrade head` shows `0003` migration
- [ ] `uv run pytest tests/ -v --tb=short` → all green
- [ ] `uv run ruff check .` → zero errors
- [ ] `uv run ruff format --check .` → zero formatting issues
- [ ] All 4 MCP tools verified importable
- [ ] All 3 doc files created

---

## NOTES

### Critical API Corrections vs. Phase 5 Spec

The `docs/Phase5.md` spec contains code written against older library versions. The following corrections apply:

| Issue | Spec Code | Correct Code |
|-------|-----------|--------------|
| Pydantic AI result access | `result.data.answer` | `result.output.answer` |
| Ragas evaluation function | `evaluate()` (sync) | `aevaluate()` (async) |
| Ragas metric name | `answer_relevancy` | `response_relevancy` |
| Ragas dataset class | `Dataset.from_dict({...})` | `EvaluationDataset(samples=[...])` |
| Ragas column names | `question`, `answer`, `contexts` | `user_input`, `response`, `retrieved_contexts` |
| DB pool in MCP | `get_pool()` (doesn't exist) | lifespan-managed `mcp.state.pool` |
| Workflow result access | `result.get("final_output")` | `result.answer` (returns `AgentResponse`) |
| Spec `build_workflow()` | Doesn't exist | `_build_graph()` is private; use `_graph` directly |

### FastMCP Tool Signature Note

In FastMCP 2.x, `ctx: Context` can appear in any position in the tool function signature. For clarity and consistency, place it **last** in all tools. FastMCP 2.x also uses `@mcp.tool` (no parentheses) for simple tools with no extra configuration, though `@mcp.tool()` with parentheses also works.

### Ragas LLM Configuration

`aevaluate()` requires an explicit `llm=` argument wrapping the judge model. Ragas 0.2.x uses LangChain wrappers:

```python
from langchain_openai import ChatOpenAI
from ragas.llms import LangchainLLMWrapper

llm = LangchainLLMWrapper(ChatOpenAI(model=EVAL_MODEL, api_key=OPENAI_API_KEY))
result = await aevaluate(dataset=dataset, metrics=metrics, llm=llm)
```

`langchain-openai` is a required dep for this reason. For Groq or Ollama evaluation, swap `ChatOpenAI` with `ChatGroq` (`langchain-groq`) or `ChatOllama` (`langchain-ollama`) — no code changes needed beyond swapping the LangChain class.

### Ragas Metric Instantiation

In Ragas 0.2.x, metrics are classes that must be instantiated: `Faithfulness()`, `AnswerRelevancy()`. However, `ragas.metrics` likely also exports pre-instantiated module-level instances (`faithfulness`, `answer_relevancy`). Verify with `uv run python -c "from ragas.metrics import faithfulness; print(type(faithfulness))"`. If that fails, use `from ragas.metrics import Faithfulness; metrics = [Faithfulness()]` instead.

### MCP Server and FastAPI Co-hosting

Phase 5 ships the MCP server as a standalone process (`scripts/mcp_server.py`). Co-hosting with FastAPI via `app.mount("/mcp", mcp.http_app(path="/"))` is documented in `docs/mcp-integration.md` as an optional pattern for teams that prefer a single process — but it is NOT implemented in Phase 5 to keep scope focused.

### Evaluation Metrics Import Compatibility

If `from ragas.metrics import response_relevancy` raises `ImportError`, try `from ragas.metrics import answer_relevancy` as a fallback — Ragas versions differ between 0.2.x and 0.4.x. Check installed version with `uv run python -c "import ragas; print(ragas.__version__)"` and adjust accordingly.

---

**Confidence Score: 8/10**

The plan is high-confidence due to deep codebase familiarity (all file patterns verified) and validated external API research (Ragas 0.4.x + FastMCP 2.x). The 2-point deduction accounts for: (1) Ragas metric import names that may vary by sub-version, and (2) FastMCP 2.x `Context` injection behavior that should be verified against actual installed version before finalizing tool signatures.
