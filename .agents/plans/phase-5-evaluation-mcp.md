# Feature: Phase 5 — Evaluation & Quality (Ragas + FastMCP + Testing Patterns)

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Phase 5 adds three capabilities focused on agent quality measurement and interoperability:

1. **Ragas Evaluation Pipelines** — Measure agent quality with standardized metrics (faithfulness, answer relevancy, context precision, context recall) against real agent interactions logged in Langfuse. Not theoretical — evaluation runs against real data.
2. **FastMCP Server Exposure** — Agent capabilities exposed as MCP (Model Context Protocol) tools, making them callable from MCP clients (Claude Desktop, Cursor, etc.) without knowing implementation details.
3. **Testing Patterns Documentation** — Comprehensive guide covering unit testing agents, integration testing multi-agent workflows, and evaluation as a continuous practice.

## User Story

As a Python developer building AI agents with AgentForge
I want to measure agent quality with standardized metrics and expose agent tools to the MCP ecosystem
So that I can continuously improve agent performance and compose agents with other AI systems

## Problem Statement

Phases 1–4 provide a fully functional agent stack, but no way to systematically measure agent quality or expose capabilities to the broader MCP ecosystem. Developers cannot answer "is my agent getting better or worse?" without manual testing, and agent tools are only accessible via the FastAPI HTTP API.

## Solution Statement

Add Ragas evaluation pipelines that extract real agent interactions from Langfuse traces and compute standardized RAG quality metrics. Add a FastMCP server that wraps existing agent tools as MCP-compatible tools. Add comprehensive testing documentation with executable example tests.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium-High
**Primary Systems Affected**: New `src/evaluation/` module, new `src/mcp/` module, new `tests/test_patterns/` directory, new documentation files, `pyproject.toml`, `.env.example`, CI workflow, Alembic migration
**Dependencies**: `ragas>=0.4.0`, `fastmcp>=3.0.0`, `datasets` (required by Ragas)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

**Core patterns to mirror:**
- `src/config.py` (full file) — Why: All env vars live here. You must add `EVAL_MODEL`, `EVAL_DATASET_LIMIT`, `MCP_TRANSPORT`, `MCP_PORT` following the exact pattern (section comments, type annotations, defaults).
- `src/cache/client.py` (full file) — Why: Best example of a Phase 4 "optional infrastructure" module. The evaluation and MCP modules follow this same pattern: graceful no-op when not configured.
- `src/observability/tracing.py` (full file) — Why: The Langfuse client singleton pattern. The evaluation dataset builder needs to use `get_client()` to access Langfuse traces.
- `src/agent/agent.py` (full file) — Why: Contains `run_agent()` — the traced agent runner that MCP tools will call. Also shows the agent definition pattern.
- `src/agent/tools.py` (full file) — Why: Contains agent tools (query_recent_videos, search_videos_by_query, get_channel_statistics, web_search). MCP tools wrap these same capabilities.
- `src/agent/models.py` (full file) — Why: `AgentResponse` and `Source` models that MCP tools return.
- `src/orchestration/graph.py` (full file) — Why: Contains `run_workflow()` — the multi-agent pipeline runner that the MCP `run_research_workflow` tool will call.
- `src/db/client.py` (full file) — Why: `create_pool()` and `close_pool()` — the MCP server's lifespan hook must manage its own pool since it runs as a separate process.
- `src/db/queries.py` (lines 156-179, 182-209) — Why: `search_videos()` and `get_channel_stats()` — direct DB queries that MCP tools can call for lightweight operations.
- `src/api/main.py` (full file) — Why: Lifespan pattern for pool/scheduler/memory/cache. The MCP server needs a simpler version of this.
- `src/api/routes.py` (full file) — Why: Shows how API endpoints delegate to agents — MCP tools follow the same thin-wrapper pattern.
- `src/api/schemas.py` (full file) — Why: Shows response model pattern.

**Migration pattern:**
- `src/db/migrations/versions/0002_scraped_pages.py` (full file) — Why: Most recent migration. Follow exact structure for `0003_evaluation_runs.py`.

**Test patterns:**
- `tests/conftest.py` (full file) — Why: Fixture conventions (mock_pool, mock_cache, mock_memory_store, client).
- `tests/test_cache.py` (full file) — Why: Best example of testing an optional infrastructure module with graceful degradation.
- `tests/test_agent.py` (full file) — Why: Agent test patterns including Langfuse mocking and model mocking.
- `tests/test_collector.py` (full file) — Why: Boundary verification tests using AST parsing. New boundary tests for `src/evaluation/` and `src/mcp/` follow this pattern.
- `tests/test_web_search.py` (full file) — Why: Shows testing of search tool integration pattern.

**CI workflow:**
- `.github/workflows/ci.yml` (full file) — Why: Must add new env vars (`EVAL_MODEL`, `MCP_TRANSPORT`, etc.) to the test job.

**Existing env config:**
- `.env.example` (full file) — Why: Must add Phase 5 env vars following existing section format.

### New Files to Create

**Evaluation module (`src/evaluation/`):**
- `src/evaluation/__init__.py` — Package init with module docstring
- `src/evaluation/dataset.py` — Dataset creation from Langfuse traces
- `src/evaluation/pipeline.py` — Ragas evaluation pipeline setup
- `src/evaluation/metrics.py` — Metric selection and custom metric helpers
- `src/evaluation/reporter.py` — Evaluation results formatting and storage

**MCP module (`src/mcp/`):**
- `src/mcp/__init__.py` — Package init with module docstring
- `src/mcp/server.py` — FastMCP server definition with lifespan and tool registration
- `src/mcp/tools.py` — Agent capabilities exposed as MCP tools

**Scripts:**
- `scripts/evaluate.py` — Manual evaluation pipeline runner
- `scripts/export_dataset.py` — Export agent interactions for evaluation
- `scripts/mcp_server.py` — Standalone MCP server runner

**Database migration:**
- `src/db/migrations/versions/0003_evaluation_runs.py` — evaluation_runs table

**Documentation:**
- `docs/testing-patterns.md` — Comprehensive testing guide
- `docs/evaluation-guide.md` — How to run and interpret evaluations
- `docs/mcp-integration.md` — Using AgentForge from MCP clients

**Tests:**
- `tests/test_evaluation.py` — Evaluation pipeline tests
- `tests/test_mcp_server.py` — MCP server tests
- `tests/test_patterns/` — Example test pattern files
  - `tests/test_patterns/__init__.py`
  - `tests/test_patterns/test_agent_unit.py` — Unit test patterns for agents
  - `tests/test_patterns/test_agent_integration.py` — Integration test patterns
  - `tests/test_patterns/test_workflow_e2e.py` — End-to-end workflow tests

### Relevant Documentation — YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [Ragas v0.4 Documentation](https://docs.ragas.io/en/stable/)
  - [Migration from v0.3 to v0.4](https://docs.ragas.io/en/stable/howtos/migrations/migrate_from_v03_to_v04/) — **CRITICAL:** Phase5.md uses outdated v0.1 API. v0.4 has breaking changes.
  - [Available Metrics](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/) — Metrics are now classes, not bare names
  - [aevaluate() reference](https://docs.ragas.io/en/stable/references/aevaluate/) — Async evaluation for use in async apps
  - [LLM Adapters](https://docs.ragas.io/en/stable/howtos/llm-adapters/) — How to configure evaluator LLM
  - Why: The Phase5.md code samples use deprecated v0.1 API. Must use v0.4 API.

- [FastMCP 3.x Documentation](https://gofastmcp.com/)
  - [Server Tools](https://gofastmcp.com/servers/tools) — @mcp.tool decorator usage
  - [Running Your Server](https://gofastmcp.com/deployment/running-server) — Transport options
  - [HTTP Deployment](https://gofastmcp.com/deployment/http) — Streamable HTTP transport
  - [Server reference](https://gofastmcp.com/servers/server) — FastMCP constructor options
  - Why: FastMCP 3.x has different patterns from v2 (bundled into `mcp` SDK). Standalone again.

- [Langfuse Python SDK](https://langfuse.com/docs/sdk/python)
  - [Fetch traces API](https://langfuse.com/docs/sdk/python#fetch-traces) — `langfuse.fetch_traces()` for dataset extraction
  - Why: Evaluation dataset builder needs to extract traces.

### Patterns to Follow

**Naming Conventions:**
- Module files: `snake_case.py` (e.g., `pipeline.py`, `dataset.py`, `reporter.py`)
- Classes: `PascalCase` (e.g., `EvalSample`, `EvalReport`, `EvaluationPipeline`)
- Functions: `snake_case` (e.g., `run_evaluation`, `create_dataset_from_langfuse`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_METRICS`, `EVAL_MODEL`)
- Test functions: `test_<subject>_<expected_behavior>` (e.g., `test_evaluation_pipeline_runs_with_default_metrics`)

**Module docstring pattern (every file):**
```python
"""
Short description of the module.

Longer description of purpose, role in system, and layer membership.
This module belongs to the <Layer> layer.
"""
```

**Error handling pattern:**
```python
try:
    result = await some_operation()
except SpecificError as exc:
    logger.error("Operation failed", extra={"error": str(exc), "context": value})
    return graceful_fallback  # Never crash the caller
```

**Logging pattern:**
```python
import logging
logger = logging.getLogger(__name__)
# Use structured extra, never print()
logger.info("Operation complete", extra={"metric": value, "count": n})
```

**Config pattern (in src/config.py):**
```python
# ---------------------------------------------------------------------------
# Section Name (Phase N)
# ---------------------------------------------------------------------------
VARIABLE_NAME: type = os.getenv("VARIABLE_NAME", "default")
```

**`__init__.py` pattern:**
```python
"""
Package short description.

One-line description of what this package provides.
"""
```

**Test fixture override pattern:**
```python
async def test_something(mock_pool):
    """Test description."""
    mock_pool.fetch = AsyncMock(return_value=[specific_test_data])
    result = await function_under_test(mock_pool)
    assert result == expected
```

---

## IMPORTANT: Ragas API Changes from Phase5.md

The Phase5.md document uses **outdated Ragas v0.1 API**. The current version is **v0.4.3** with significant breaking changes. Here are the corrections:

| Phase5.md (v0.1 — WRONG) | Correct v0.4 API |
|---------------------------|-------------------|
| `from ragas import evaluate` | `from ragas import evaluate, aevaluate` |
| `from ragas.metrics import faithfulness, answer_relevancy` | `from ragas.metrics import Faithfulness, AnswerRelevancy` (classes) |
| `Dataset.from_dict({"question": ..., "answer": ..., "contexts": ...})` | `EvaluationDataset(samples=[SingleTurnSample(...)])` |
| `evaluate(dataset=dataset, metrics=metrics, llm=model)` | `await aevaluate(dataset=dataset, metrics=[Faithfulness(llm=llm)], llm=llm)` |
| `ground_truth` field | `reference` field on `SingleTurnSample` |
| Metrics as bare names | Metrics as instantiated classes with `llm` parameter |
| No async support | `aevaluate()` for async apps (avoids event loop conflicts) |

**Key decision:** Use `aevaluate()` throughout since the app is async-native (FastAPI). The synchronous `evaluate()` uses `nest_asyncio` which conflicts with running event loops.

## IMPORTANT: FastMCP API Notes

- **Package:** `fastmcp>=3.0.0` (standalone, NOT bundled in `mcp` SDK)
- **Decorator:** `@mcp.tool` (no parentheses needed for simple cases)
- **Async tools:** Natively supported, preferred for I/O-bound work
- **Lifespan:** Use `app_lifespan` pattern for DB pool management (MCP server runs as separate process)
- **Context access:** `ctx.request_context.lifespan_context` to reach lifespan resources
- **Transport:** `stdio` for local/Claude Desktop, `http` for remote (replaces SSE)

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — Dependencies and Configuration

Set up the base: add dependencies, config vars, migration, and package scaffolding.

**Tasks:**
- Add `ragas`, `fastmcp`, `datasets` to `pyproject.toml`
- Add Phase 5 env vars to `src/config.py` and `.env.example`
- Create Alembic migration for `evaluation_runs` table
- Create package `__init__.py` files for `src/evaluation/` and `src/mcp/`
- Add new env vars to CI workflow

### Phase 2: Core Implementation — Evaluation Pipeline

Build the Ragas evaluation module using the correct v0.4 API.

**Tasks:**
- Implement dataset creation from Langfuse traces
- Implement evaluation pipeline with metric selection
- Implement results reporter with DB storage
- Implement metric helpers
- Create evaluation scripts

### Phase 3: Core Implementation — MCP Server

Build the FastMCP server exposing agent tools.

**Tasks:**
- Implement MCP server with lifespan-managed DB pool
- Implement MCP tools wrapping agent capabilities
- Create standalone MCP server runner script

### Phase 4: Documentation

Write comprehensive testing, evaluation, and MCP integration guides.

**Tasks:**
- Write testing-patterns.md
- Write evaluation-guide.md
- Write mcp-integration.md

### Phase 5: Testing & Validation

Add tests for all new modules and example test patterns.

**Tasks:**
- Add evaluation pipeline tests
- Add MCP server tests
- Add boundary verification tests
- Add example test pattern files
- Update conftest.py with new fixtures
- Verify all existing tests still pass

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: UPDATE `pyproject.toml` — Add Phase 5 dependencies

- **IMPLEMENT**: Add `ragas`, `fastmcp`, and `datasets` to the `[project] dependencies` list
- **PATTERN**: Follow existing dependency format in `pyproject.toml:6-36`
- **DETAILS**:
  ```toml
  # Evaluation (Phase 5)
  "ragas>=0.4.0",
  "datasets>=2.0.0",
  # MCP server (Phase 5)
  "fastmcp>=3.0.0",
  ```
- **GOTCHA**: `datasets` is required by Ragas for dataset handling. Pin `ragas>=0.4.0` to ensure v0.4 API compatibility.
- **VALIDATE**: `uv sync --dev` completes without errors

---

### Task 2: UPDATE `src/config.py` — Add Phase 5 environment variables

- **IMPLEMENT**: Add two new sections: Evaluation (Phase 5) and MCP Server (Phase 5)
- **PATTERN**: Follow exact section format from `src/config.py:69-93` (Phase 4 sections)
- **IMPORTS**: None new — uses existing `os` and `dotenv`
- **DETAILS**: Add after the Caching section (line 93):
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
- **GOTCHA**: Follow same type annotation pattern. Use `int()` wrapper for integer env vars.
- **VALIDATE**: `uv run python -c "from src.config import EVAL_MODEL, MCP_TRANSPORT; print(EVAL_MODEL, MCP_TRANSPORT)"`

---

### Task 3: UPDATE `.env.example` — Add Phase 5 configuration

- **IMPLEMENT**: Add two new sections at the end of the file
- **PATTERN**: Follow exact section format from `.env.example:68-101` (Phase 4 sections)
- **DETAILS**:
  ```env
  # -----------------------------------------------------------------------------
  # Evaluation (Phase 5)
  # Ragas evaluation pipeline — measures agent quality against real interactions.
  # EVAL_MODEL: LLM used by Ragas for metric computation (evaluator model).
  # EVAL_DATASET_LIMIT: Maximum traces to include in evaluation dataset.
  # -----------------------------------------------------------------------------
  EVAL_MODEL=gpt-4o
  EVAL_DATASET_LIMIT=100

  # -----------------------------------------------------------------------------
  # MCP Server (Phase 5)
  # FastMCP server for exposing agent tools to MCP clients (Claude Desktop, etc).
  # MCP_TRANSPORT: stdio (local/subprocess) or http (remote/networked).
  # MCP_PORT: Port for HTTP transport (only used when MCP_TRANSPORT=http).
  # -----------------------------------------------------------------------------
  MCP_TRANSPORT=stdio
  MCP_PORT=8001
  ```
- **VALIDATE**: File ends with newline; sections are consistently formatted

---

### Task 4: UPDATE `.github/workflows/ci.yml` — Add Phase 5 env vars

- **IMPLEMENT**: Add `EVAL_MODEL`, `EVAL_DATASET_LIMIT`, `MCP_TRANSPORT`, `MCP_PORT` to the `env:` block in the test job
- **PATTERN**: Follow existing env var entries at `.github/workflows/ci.yml:58-77`
- **DETAILS**:
  ```yaml
  EVAL_MODEL: "gpt-4o"
  EVAL_DATASET_LIMIT: "100"
  MCP_TRANSPORT: "stdio"
  MCP_PORT: "8001"
  ```
- **GOTCHA**: All values must be strings (quoted) in YAML env blocks.
- **VALIDATE**: `yamllint .github/workflows/ci.yml` or manual review for valid YAML

---

### Task 5: CREATE `src/db/migrations/versions/0003_evaluation_runs.py` — Evaluation tracking table

- **IMPLEMENT**: Alembic migration for `evaluation_runs` table
- **PATTERN**: Mirror `src/db/migrations/versions/0002_scraped_pages.py` exactly
- **DETAILS**:
  ```python
  """Add evaluation_runs table for tracking evaluation results over time.

  Revision ID: 0003
  Revises: 0002
  Create Date: 2026-03-15
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
              id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
              timestamp     TIMESTAMPTZ NOT NULL,
              dataset_size  INTEGER     NOT NULL,
              results       JSONB       NOT NULL,
              metadata      JSONB       DEFAULT '{}',
              created_at    TIMESTAMPTZ DEFAULT NOW()
          )
          """
      )


  def downgrade() -> None:
      """Drop the evaluation_runs table."""
      op.execute("DROP TABLE IF EXISTS evaluation_runs")
  ```
- **VALIDATE**: `uv run alembic check` or review migration chain (0001 → 0002 → 0003)

---

### Task 6: CREATE `src/evaluation/__init__.py` — Evaluation package init

- **IMPLEMENT**:
  ```python
  """
  Agent quality evaluation with Ragas.

  Provides evaluation pipelines that measure agent quality using standardized
  RAG metrics (faithfulness, answer relevancy, context precision) against
  real agent interactions extracted from Langfuse traces.
  """
  ```
- **VALIDATE**: `uv run python -c "import src.evaluation"`

---

### Task 7: CREATE `src/evaluation/metrics.py` — Metric selection and helpers

- **IMPLEMENT**: Define metric constants using Ragas v0.4 class-based API. Provide a helper to select metrics based on dataset content.
- **PATTERN**: Follow constant naming from `src/config.py` (UPPER_SNAKE_CASE)
- **IMPORTS**: `from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall` and `from ragas.llms import llm_factory`
- **DETAILS**:
  - Define `create_evaluator_llm(model: str) -> object` — wraps `llm_factory()` with the configured eval model
  - Define `get_default_metrics(llm) -> list` — returns `[Faithfulness(llm=llm), AnswerRelevancy(llm=llm), ContextPrecision(llm=llm)]`
  - Define `get_supervised_metrics(llm) -> list` — returns `[ContextRecall(llm=llm)]` (needs `reference` field)
  - Define `select_metrics(llm, has_reference: bool) -> list` — combines default + supervised when reference data available
- **GOTCHA**: Ragas v0.4 metrics are **classes that take `llm` as a constructor arg**, not bare names. Must instantiate them.
- **GOTCHA**: Import `llm_factory` from `ragas.llms`. For OpenAI: `llm_factory("gpt-4o", provider="openai")`.
- **VALIDATE**: `uv run python -c "from src.evaluation.metrics import get_default_metrics, create_evaluator_llm"`

---

### Task 8: CREATE `src/evaluation/dataset.py` — Dataset creation from Langfuse

- **IMPLEMENT**: Extract agent interactions from Langfuse traces into Ragas v0.4 `EvaluationDataset`
- **PATTERN**: Follow error handling from `src/cache/client.py` (graceful degradation, structured logging)
- **IMPORTS**: `from ragas import EvaluationDataset, SingleTurnSample`, `from langfuse import Langfuse`
- **DETAILS**:
  - Define `EvalSample(BaseModel)` — intermediate Pydantic model with `question: str`, `answer: str`, `contexts: list[str]`, `reference: str | None = None`
  - Define `async def create_dataset_from_langfuse(langfuse: Langfuse, limit: int = 100, trace_name: str | None = None) -> EvaluationDataset`
    - Call `langfuse.fetch_traces(name=trace_name, limit=limit)` to get traces
    - For each trace: extract `question` from `trace.input`, `answer` from `trace.output`
    - Extract contexts from child observations (tool call outputs): `langfuse.fetch_observations(trace_id=trace.id)`
    - Convert to `SingleTurnSample(user_input=question, response=answer, retrieved_contexts=contexts)`
    - If `reference` is provided, include it on the sample
    - Return `EvaluationDataset(samples=[...])`
  - Define `async def export_dataset_to_json(dataset: EvaluationDataset, path: str) -> None` — serialize to JSON file
- **GOTCHA**: Ragas v0.4 uses `SingleTurnSample` with fields: `user_input` (not `question`), `response` (not `answer`), `retrieved_contexts` (not `contexts`), `reference` (not `ground_truth`/`ground_truths`).
- **GOTCHA**: `langfuse.fetch_traces()` returns a `FetchTracesResponse` with `.data` attribute containing the list.
- **GOTCHA**: Handle empty traces gracefully — return empty dataset, don't crash.
- **VALIDATE**: `uv run python -c "from src.evaluation.dataset import create_dataset_from_langfuse, EvalSample"`

---

### Task 9: CREATE `src/evaluation/pipeline.py` — Ragas evaluation pipeline

- **IMPLEMENT**: Run Ragas evaluation on a dataset and return results
- **PATTERN**: Follow async patterns from `src/agent/agent.py:65-129`
- **IMPORTS**: `from ragas import aevaluate`, `from src.evaluation.metrics import create_evaluator_llm, select_metrics`, `from src.config import EVAL_MODEL`
- **DETAILS**:
  - Define `async def run_evaluation(dataset: EvaluationDataset, model: str | None = None, metrics: list | None = None) -> dict`
    - Default `model` to `EVAL_MODEL` from config
    - Create evaluator LLM via `create_evaluator_llm(model)`
    - If `metrics` is None, auto-select via `select_metrics(llm, has_reference=...)`. Check if any sample in the dataset has a `reference` field set.
    - Call `result = await aevaluate(dataset=dataset, metrics=metrics, llm=llm)`
    - Return result as dict (metric name → score)
  - Define `async def run_evaluation_from_langfuse(langfuse: Langfuse, limit: int = 100, trace_name: str | None = None, model: str | None = None) -> dict`
    - Convenience function: creates dataset then runs evaluation
- **GOTCHA**: Use `aevaluate()` (async), NOT `evaluate()` (sync). The sync version uses `nest_asyncio` which conflicts with FastAPI's event loop.
- **GOTCHA**: `aevaluate()` returns a result object. Access scores via dict-like interface or `.to_pandas()`.
- **VALIDATE**: `uv run python -c "from src.evaluation.pipeline import run_evaluation"`

---

### Task 10: CREATE `src/evaluation/reporter.py` — Results formatting and storage

- **IMPLEMENT**: Format evaluation results for human reading and persist to Postgres
- **PATTERN**: Follow DB interaction pattern from `src/db/queries.py` (accept pool, use parameterized SQL)
- **IMPORTS**: `from asyncpg import Pool`, `from pydantic import BaseModel`
- **DETAILS**:
  - Define `EvalReportRecord(BaseModel)` — Pydantic model with `id: UUID`, `timestamp: datetime`, `dataset_size: int`, `results: dict`, `metadata: dict`, `created_at: datetime`
  - Define `class EvalReport` with:
    - `__init__(self, results: dict, dataset_size: int, metadata: dict | None = None)`
    - `summary(self) -> str` — human-readable summary of metric scores
    - `async def save(self, pool: Pool) -> None` — store in `evaluation_runs` table via SQL (follow `upsert_video` pattern)
  - Define `async def get_evaluation_history(pool: Pool, limit: int = 20) -> list[EvalReportRecord]` — fetch recent evaluation runs
- **GOTCHA**: Use `json.dumps()` for JSONB columns. Follow the pattern from `src/db/queries.py:304` (`upsert_scraped_page` with `json.dumps`).
- **VALIDATE**: `uv run python -c "from src.evaluation.reporter import EvalReport, get_evaluation_history"`

---

### Task 11: CREATE `src/mcp/__init__.py` — MCP package init

- **IMPLEMENT**:
  ```python
  """
  MCP server for exposing agent tools.

  Wraps AgentForge agent capabilities as Model Context Protocol tools,
  making them callable from MCP clients like Claude Desktop and Cursor.
  """
  ```
- **VALIDATE**: `uv run python -c "import src.mcp"`

---

### Task 12: CREATE `src/mcp/server.py` — FastMCP server with lifespan

- **IMPLEMENT**: FastMCP server with asyncpg pool managed via lifespan pattern
- **PATTERN**: Follow lifespan from `src/api/main.py:27-81` but simpler (no scheduler, no memory, no cache)
- **IMPORTS**: `from fastmcp import FastMCP, Context`, `from contextlib import asynccontextmanager`, `from dataclasses import dataclass`, `from asyncpg import Pool`
- **DETAILS**:
  - Define `@dataclass class MCPAppContext:` with `pool: Pool`
  - Define `@asynccontextmanager async def mcp_lifespan(server: FastMCP) -> AsyncIterator[MCPAppContext]:`
    - Create pool via `asyncpg.create_pool(DATABASE_URL)` (use `src.config.DATABASE_URL`)
    - Yield `MCPAppContext(pool=pool)`
    - Close pool on shutdown
  - Create `mcp = FastMCP(name="AgentForge", lifespan=mcp_lifespan)`
  - Import and register tools from `src.mcp.tools`
- **GOTCHA**: The MCP server runs as a **separate process** from FastAPI. It needs its own DB pool. Do NOT try to share `app.state.pool` from FastAPI.
- **GOTCHA**: FastMCP 3.x lifespan context is accessed via `ctx.request_context.lifespan_context`.
- **VALIDATE**: `uv run python -c "from src.mcp.server import mcp"`

---

### Task 13: CREATE `src/mcp/tools.py` — Agent capabilities as MCP tools

- **IMPLEMENT**: Define MCP tools that wrap existing agent capabilities
- **PATTERN**: Follow thin-wrapper pattern from `src/api/routes.py` (validate, delegate, shape response)
- **IMPORTS**: `from fastmcp import Context`, `from src.mcp.server import mcp`
- **DETAILS**: Define these tools on the `mcp` instance:

  1. `@mcp.tool async def ask_agent(question: str, ctx: Context) -> str`
     - Docstring: "Ask the YouTube research agent a question. Returns a source-cited answer."
     - Get pool from `ctx.request_context.lifespan_context.pool`
     - Call `run_agent(question, pool)` from `src.agent.agent`
     - Return `response.answer` (string, not full model — MCP tools return simple types)

  2. `@mcp.tool async def search_videos(query: str, limit: int = 5, ctx: Context) -> list[dict]`
     - Docstring: "Search the video database for videos matching a query."
     - Call `search_videos()` from `src.db.queries` directly (lightweight, no LLM)
     - Return `[v.model_dump() for v in videos]`

  3. `@mcp.tool async def get_channel_summary(channel_id: str, ctx: Context) -> dict | str`
     - Docstring: "Get aggregate statistics for a YouTube channel."
     - Call `get_channel_stats()` from `src.db.queries`
     - Return `stats.model_dump()` or "Channel not found" if None

  4. `@mcp.tool async def run_research(query: str, ctx: Context) -> str`
     - Docstring: "Run the multi-agent research workflow (research → analysis → synthesis)."
     - Call `run_workflow(query, pool)` from `src.orchestration.graph`
     - Return `response.answer`

- **GOTCHA**: MCP tools should return simple serializable types (str, dict, list), not Pydantic models. FastMCP handles JSON serialization.
- **GOTCHA**: The `ctx: Context` parameter is auto-injected by FastMCP and hidden from the LLM. Place it as the last parameter.
- **GOTCHA**: Import the `mcp` instance from `src.mcp.server`, not create a new one. Tools register on the same server.
- **VALIDATE**: `uv run python -c "from src.mcp.tools import ask_agent"`

---

### Task 14: CREATE `scripts/mcp_server.py` — Standalone MCP server runner

- **IMPLEMENT**: Entry point for running the MCP server as a standalone process
- **PATTERN**: Follow `scripts/pull_model.py` for script structure (docstring, imports, main block)
- **DETAILS**:
  ```python
  """Run the AgentForge MCP server.

  Usage:
      uv run python scripts/mcp_server.py              # stdio transport (Claude Desktop)
      uv run python scripts/mcp_server.py --http        # HTTP transport (remote clients)
      uv run python scripts/mcp_server.py --http 8001   # HTTP on custom port
  """
  import sys

  from dotenv import load_dotenv
  load_dotenv()

  from src.config import MCP_PORT, MCP_TRANSPORT

  # Import tools to register them on the server
  import src.mcp.tools  # noqa: F401
  from src.mcp.server import mcp

  if __name__ == "__main__":
      transport = MCP_TRANSPORT
      port = MCP_PORT

      if "--http" in sys.argv:
          transport = "http"
          idx = sys.argv.index("--http")
          if idx + 1 < len(sys.argv) and sys.argv[idx + 1].isdigit():
              port = int(sys.argv[idx + 1])

      if transport == "http":
          mcp.run(transport="http", host="0.0.0.0", port=port)
      else:
          mcp.run(transport="stdio")
  ```
- **VALIDATE**: `uv run python -c "import scripts.mcp_server"` (import check only — don't run the server)

---

### Task 15: CREATE `scripts/evaluate.py` — Manual evaluation runner

- **IMPLEMENT**: CLI script to run evaluation pipeline against real Langfuse traces
- **PATTERN**: Follow `scripts/collect.py` for async script structure
- **DETAILS**:
  ```python
  """Run the Ragas evaluation pipeline against real agent interactions.

  Usage:
      uv run python scripts/evaluate.py
      uv run python scripts/evaluate.py --limit 50
      uv run python scripts/evaluate.py --trace-name agent_run
      uv run python scripts/evaluate.py --save   # Save results to Postgres
  """
  ```
  - Parse args: `--limit` (int, default from config), `--trace-name` (str, optional), `--save` (flag)
  - Get Langfuse client via `get_client()` from `src.observability.tracing`
  - Create dataset via `create_dataset_from_langfuse()`
  - Run evaluation via `run_evaluation()`
  - Print `EvalReport.summary()`
  - If `--save`: create pool, call `report.save(pool)`, close pool
- **GOTCHA**: Must call `load_dotenv()` before importing config.
- **VALIDATE**: `uv run python scripts/evaluate.py --help` (if argparse used) or import check

---

### Task 16: CREATE `scripts/export_dataset.py` — Export interactions for evaluation

- **IMPLEMENT**: CLI script to export agent interactions from Langfuse to JSON
- **DETAILS**:
  ```python
  """Export agent interactions from Langfuse traces to a JSON file.

  Usage:
      uv run python scripts/export_dataset.py output.json
      uv run python scripts/export_dataset.py output.json --limit 200
      uv run python scripts/export_dataset.py output.json --trace-name agent_run
  """
  ```
  - Parse args: output path (positional), `--limit`, `--trace-name`
  - Create dataset via `create_dataset_from_langfuse()`
  - Export via `export_dataset_to_json()` or manual JSON dump
  - Print count of exported samples
- **VALIDATE**: `uv run python scripts/export_dataset.py --help` or import check

---

### Task 17: UPDATE `src/db/queries.py` — Add evaluation query functions

- **IMPLEMENT**: Add query functions for evaluation_runs table
- **PATTERN**: Follow existing query pattern from `src/db/queries.py:286-369` (scraped pages section)
- **DETAILS**: Add at the end of the file:
  - Add `EvalRunRecord(BaseModel)` with fields matching the migration: `id: UUID`, `timestamp: datetime`, `dataset_size: int`, `results: dict`, `metadata: dict`, `created_at: datetime`
  - Add `async def insert_evaluation_run(pool, timestamp, dataset_size, results, metadata) -> None`
  - Add `async def get_evaluation_runs(pool, limit=20) -> list[EvalRunRecord]`
- **GOTCHA**: Use `json.dumps()` for JSONB parameters. Follow the `upsert_scraped_page` pattern exactly.
- **VALIDATE**: `uv run python -c "from src.db.queries import EvalRunRecord, insert_evaluation_run, get_evaluation_runs"`

---

### Task 18: CREATE `docs/testing-patterns.md` — Comprehensive testing guide

- **IMPLEMENT**: Documentation covering all testing patterns in the codebase
- **DETAILS**: Cover these sections:
  1. **Testing Philosophy** — Test behavior, not implementation. Mock external deps, never real LLM calls.
  2. **Unit Testing Agents** — Using Pydantic AI's `TestModel`, mocking pool, testing structured output
  3. **Testing Collectors** — No LLM mocking needed, mock external APIs, verify boundary
  4. **Integration Testing Multi-Agent Workflows** — Testing LangGraph graphs, state propagation, conditional routing
  5. **Boundary Verification Tests** — AST-based import checks, why they matter
  6. **Testing Optional Features** — Cache, memory, search: graceful degradation patterns
  7. **Fixtures and Conventions** — `conftest.py` patterns, naming, async handling
  8. **Running Tests** — Commands, filtering, verbose output
  9. **Evaluation as Testing** — Using Ragas for continuous quality measurement (link to evaluation-guide.md)
- **GOTCHA**: Include actual code examples from the codebase (reference specific test files and line numbers). Do not invent abstract examples.
- **VALIDATE**: File exists and is well-structured markdown

---

### Task 19: CREATE `docs/evaluation-guide.md` — Evaluation guide

- **IMPLEMENT**: Documentation covering running evaluations and interpreting results
- **DETAILS**: Cover these sections:
  1. **Prerequisites** — Langfuse running with traces, API key for evaluator model
  2. **Quick Start** — Run `scripts/evaluate.py` with examples
  3. **Understanding Metrics** — What faithfulness, answer relevancy, context precision, context recall measure
  4. **Creating Datasets** — From Langfuse traces, manual annotation, JSON export
  5. **Running Evaluations** — CLI usage, programmatic usage
  6. **Interpreting Results** — Score ranges, what good/bad looks like, actionable improvements
  7. **Tracking Over Time** — Storing results in Postgres, comparing runs
  8. **Running in CI** — How to add as a scheduled job (not every PR)
  9. **Evaluator Model Selection** — Using EVAL_MODEL, cost considerations
- **VALIDATE**: File exists and is well-structured markdown

---

### Task 20: CREATE `docs/mcp-integration.md` — MCP integration guide

- **IMPLEMENT**: Documentation covering MCP server setup and client configuration
- **DETAILS**: Cover these sections:
  1. **What is MCP** — Brief explanation of Model Context Protocol
  2. **Available Tools** — List of exposed tools with descriptions
  3. **Running the MCP Server** — stdio vs HTTP transport, startup commands
  4. **Claude Desktop Configuration** — JSON config for `mcpServers`
  5. **Cursor Configuration** — How to add as MCP server in Cursor
  6. **HTTP Transport for Remote Access** — Running with `--http`, port configuration
  7. **Testing the Server** — Verifying tools are accessible
  8. **Security Considerations** — Local/trusted use only, no auth
- **VALIDATE**: File exists and is well-structured markdown

---

### Task 21: UPDATE `tests/conftest.py` — Add Phase 5 fixtures

- **IMPLEMENT**: Add `mock_langfuse` fixture for evaluation tests
- **PATTERN**: Follow existing fixture patterns in `tests/conftest.py`
- **DETAILS**: Add a `mock_langfuse` fixture that returns a MagicMock with:
  - `fetch_traces()` → returns mock `FetchTracesResponse` with `.data` list
  - `fetch_observations()` → returns mock response with `.data` list
  - `trace()`, `span()`, `generation()` → return MagicMock
  - `flush()` → no-op
- **VALIDATE**: `uv run pytest tests/conftest.py --co` (collect only, verify no import errors)

---

### Task 22: CREATE `tests/test_evaluation.py` — Evaluation pipeline tests

- **IMPLEMENT**: Tests for the evaluation module
- **PATTERN**: Follow `tests/test_cache.py` structure (optional infrastructure, graceful degradation)
- **DETAILS**:
  - Test `EvalSample` model validation
  - Test `create_dataset_from_langfuse` with mocked Langfuse client:
    - Happy path: traces with input/output → produces EvaluationDataset
    - Empty traces → returns empty dataset
    - Missing input/output fields → handles gracefully
  - Test `EvalReport.summary()` produces readable output
  - Test `EvalReport.save()` calls pool.execute with correct params
  - Test `select_metrics` returns correct metrics based on `has_reference`
  - Test `get_evaluation_runs` query delegation
  - Boundary test: `test_evaluation_has_no_collector_imports` — verify `src/evaluation/` does not import from `src/collector/` or `apscheduler`
- **GOTCHA**: Mock Ragas functions — do not make real LLM calls in tests. Patch `aevaluate` to return mock results.
- **VALIDATE**: `uv run pytest tests/test_evaluation.py -v --tb=short`

---

### Task 23: CREATE `tests/test_mcp_server.py` — MCP server tests

- **IMPLEMENT**: Tests for the MCP server module
- **PATTERN**: Follow `tests/test_api.py` structure (mock pool, test tool delegation)
- **DETAILS**:
  - Test MCP server instantiation (`mcp` is a FastMCP instance)
  - Test `ask_agent` tool calls `run_agent` with correct args (mock agent, mock pool)
  - Test `search_videos` tool calls `search_videos` query with correct args
  - Test `get_channel_summary` tool returns stats or "not found"
  - Test `run_research` tool calls `run_workflow` with correct args
  - Boundary test: `test_mcp_has_no_collector_imports` — verify `src/mcp/` does not import from `src/collector/` or `apscheduler`
- **GOTCHA**: Testing MCP tools requires calling them directly as async functions (they're registered on the server but are also normal async functions in FastMCP 3.x). Mock the `Context` parameter.
- **GOTCHA**: The `ctx.request_context.lifespan_context.pool` chain must be mockable. Create a nested mock object.
- **VALIDATE**: `uv run pytest tests/test_mcp_server.py -v --tb=short`

---

### Task 24: CREATE `tests/test_patterns/__init__.py` — Test patterns package init

- **IMPLEMENT**: Empty or minimal init
- **VALIDATE**: Directory exists with `__init__.py`

---

### Task 25: CREATE `tests/test_patterns/test_agent_unit.py` — Agent unit test examples

- **IMPLEMENT**: Example tests demonstrating unit testing patterns for Pydantic AI agents
- **PATTERN**: Follow `tests/test_agent.py` for actual patterns used in the project
- **DETAILS**:
  - Test agent returns structured AgentResponse
  - Test agent tools are callable with mock pool
  - Test model validation (confidence bounds, required fields)
  - Include comments explaining each pattern for documentation purposes
- **VALIDATE**: `uv run pytest tests/test_patterns/test_agent_unit.py -v --tb=short`

---

### Task 26: CREATE `tests/test_patterns/test_agent_integration.py` — Integration test examples

- **IMPLEMENT**: Example tests demonstrating integration testing with mocked dependencies
- **DETAILS**:
  - Test API endpoint → agent → response chain (mock LLM, real routing)
  - Test memory-aware agent with mock memory store
  - Include comments explaining integration test boundaries
- **VALIDATE**: `uv run pytest tests/test_patterns/test_agent_integration.py -v --tb=short`

---

### Task 27: CREATE `tests/test_patterns/test_workflow_e2e.py` — Workflow end-to-end test examples

- **IMPLEMENT**: Example tests for LangGraph multi-agent workflows
- **PATTERN**: Follow `tests/test_orchestration.py` for actual patterns
- **DETAILS**:
  - Test full workflow execution with mocked agents
  - Test conditional routing (quality threshold → retry vs continue)
  - Test state propagation between nodes
  - Include comments explaining workflow testing strategies
- **VALIDATE**: `uv run pytest tests/test_patterns/test_workflow_e2e.py -v --tb=short`

---

### Task 28: Run full validation

- **VALIDATE**: Run all validation commands sequentially:
  ```bash
  # Level 1: Syntax & Style
  uv run ruff check .
  uv run ruff format --check .

  # Level 2: All tests pass
  uv run pytest tests/ -v --tb=short

  # Level 3: Import verification
  uv run python -c "from src.evaluation.pipeline import run_evaluation; from src.evaluation.dataset import create_dataset_from_langfuse; from src.evaluation.reporter import EvalReport; from src.mcp.server import mcp; from src.mcp.tools import ask_agent"
  ```

---

## TESTING STRATEGY

### Unit Tests

Tests mock all external dependencies (Langfuse, Ragas, asyncpg, Redis). No real LLM calls, no real DB queries, no real network requests.

**Evaluation tests** (`test_evaluation.py`):
- Mock `langfuse.fetch_traces()` and `langfuse.fetch_observations()` to return test data
- Mock `aevaluate()` to return predefined metric scores
- Test dataset creation logic with various edge cases
- Test report formatting and DB storage

**MCP tests** (`test_mcp_server.py`):
- Mock the Context object chain (`ctx.request_context.lifespan_context.pool`)
- Mock `run_agent()`, `run_workflow()`, DB query functions
- Test each tool's delegation logic
- Verify return types are simple serializable values

### Integration Tests

The test pattern examples (`tests/test_patterns/`) serve as both documentation and executable integration tests, using the same mock infrastructure as the main test suite.

### Edge Cases

- Empty Langfuse traces (no data to evaluate)
- Traces with missing input/output fields
- Evaluation with zero samples in dataset
- MCP tool called with invalid arguments
- Channel not found in `get_channel_summary`
- Langfuse not configured (evaluation should fail gracefully with clear message)

### Boundary Tests

- `test_evaluation_has_no_collector_imports` — `src/evaluation/` must not import `src/collector/`, `apscheduler`
- `test_mcp_has_no_collector_imports` — `src/mcp/` must not import `src/collector/`, `apscheduler`

---

## VALIDATION COMMANDS

Execute every command to ensure zero regressions and 100% feature correctness.

### Level 1: Syntax & Style

```bash
# Ruff linting (must pass with 0 errors)
uv run ruff check .

# Ruff formatting check
uv run ruff format --check .
```

**Expected**: Both commands exit 0

### Level 2: Unit Tests

```bash
# Run all tests
uv run pytest tests/ -v --tb=short

# Run only new Phase 5 tests
uv run pytest tests/test_evaluation.py tests/test_mcp_server.py tests/test_patterns/ -v --tb=short
```

**Expected**: All tests pass

### Level 3: Import Verification

```bash
# Verify all new modules import cleanly
uv run python -c "
from src.evaluation.dataset import create_dataset_from_langfuse, EvalSample
from src.evaluation.pipeline import run_evaluation
from src.evaluation.metrics import get_default_metrics, create_evaluator_llm, select_metrics
from src.evaluation.reporter import EvalReport, get_evaluation_history
from src.mcp.server import mcp
from src.mcp.tools import ask_agent
from src.config import EVAL_MODEL, EVAL_DATASET_LIMIT, MCP_TRANSPORT, MCP_PORT
from src.db.queries import EvalRunRecord, insert_evaluation_run, get_evaluation_runs
print('All Phase 5 imports OK')
"
```

**Expected**: Prints "All Phase 5 imports OK"

### Level 4: Manual Validation

```bash
# Verify migration chain is intact
uv run alembic check

# Verify MCP server can be imported (don't run it)
uv run python -c "from scripts.mcp_server import mcp; print('MCP server importable')"
```

### Level 5: Existing Test Regression

```bash
# All pre-existing tests must still pass
uv run pytest tests/test_agent.py tests/test_api.py tests/test_cache.py tests/test_collector.py tests/test_cross_agent_tracing.py tests/test_memory.py tests/test_memory_agent.py tests/test_ollama_provider.py tests/test_orchestration.py tests/test_searxng.py tests/test_web_scraper.py tests/test_web_search.py -v --tb=short
```

**Expected**: All existing tests pass unchanged

---

## ACCEPTANCE CRITERIA

- [ ] `ragas`, `fastmcp`, and `datasets` are in `pyproject.toml` and resolve via `uv sync`
- [ ] `scripts/export_dataset.py` extracts agent interactions from Langfuse into a Ragas-compatible dataset
- [ ] `scripts/evaluate.py` runs the evaluation pipeline and prints metric scores
- [ ] Evaluation results include faithfulness, answer relevancy, and context precision scores
- [ ] Evaluation results can be stored in Postgres via `evaluation_runs` table
- [ ] FastMCP server starts and exposes at least 4 agent tools (`ask_agent`, `search_videos`, `get_channel_summary`, `run_research`)
- [ ] `ask_agent` MCP tool accepts a question and returns an agent-generated answer
- [ ] `run_research` MCP tool triggers the multi-agent workflow and returns results
- [ ] MCP server is configurable for stdio and HTTP transports
- [ ] `docs/testing-patterns.md` covers unit testing, integration testing, workflow testing, and evaluation
- [ ] `docs/evaluation-guide.md` covers running evaluations, interpreting metrics, and acting on results
- [ ] `docs/mcp-integration.md` covers configuring MCP clients to connect to AgentForge
- [ ] Example test files in `tests/test_patterns/` demonstrate all documented patterns
- [ ] All existing Phase 1–4 tests still pass
- [ ] New tests cover: evaluation pipeline, MCP server tools, boundary verification
- [ ] All new modules follow project conventions (docstrings, type hints, logging, error handling)
- [ ] Ruff lint and format checks pass with zero errors

---

## COMPLETION CHECKLIST

- [ ] All 28 tasks completed in order
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully:
  - [ ] Level 1: `ruff check`, `ruff format --check`
  - [ ] Level 2: `pytest` (all tests pass)
  - [ ] Level 3: Import verification
  - [ ] Level 4: Migration check, MCP server import
  - [ ] Level 5: Existing test regression
- [ ] Full test suite passes (unit + integration)
- [ ] No linting errors
- [ ] No formatting errors
- [ ] All acceptance criteria met
- [ ] Code reviewed for quality and maintainability

---

## NOTES

### Critical: Ragas API version mismatch

The Phase5.md specification uses Ragas v0.1 API which is deprecated. This plan uses the correct v0.4 API throughout. Key differences documented in the "IMPORTANT: Ragas API Changes" section above. The implementation agent MUST use v0.4 API — do not copy code from Phase5.md verbatim.

### FastMCP as separate process

The MCP server runs as a standalone process (via `scripts/mcp_server.py`), not embedded in the FastAPI app. This means:
- It needs its own DB pool (managed via FastMCP lifespan)
- It does NOT share `app.state` with FastAPI
- It imports and calls the same agent/query functions, but with its own pool
- Configuration comes from the same `.env` file

### Evaluation is optional

Like Redis caching, evaluation requires external dependencies (Langfuse with real traces, an LLM for metric computation). The module should handle missing configuration gracefully — clear error messages, not crashes.

### No automated evaluation in CI

Per Phase5.md: "Document how to do it, but don't enforce it in the default CI pipeline." Evaluation requires real Langfuse traces and an LLM API key — not suitable for CI.

### Layer boundaries

- `src/evaluation/` may import from: `src/config`, `src/observability`, `src/db`
- `src/evaluation/` must NOT import from: `src/collector/`, `src/agent/` (evaluation reads from Langfuse, not from agents directly)
- `src/mcp/` may import from: `src/config`, `src/agent`, `src/orchestration`, `src/db`
- `src/mcp/` must NOT import from: `src/collector/`, `apscheduler`
