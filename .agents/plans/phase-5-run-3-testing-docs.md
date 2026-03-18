# Phase 5 — Run 3: Testing Patterns + Documentation (PBI 5.3)

The following plan should be complete, but validate documentation and codebase patterns before implementing.

This run is the lowest risk of the three — primarily writing test pattern examples and markdown documentation. The test pattern files are working reference code, not just docs.

## What This Run Delivers

- `tests/test_patterns/` package with 3 example test files
- `docs/testing-patterns.md` — comprehensive testing guide
- `docs/evaluation-guide.md` — running and interpreting Ragas evaluations
- `docs/mcp-integration.md` — connecting MCP clients to AgentForge

**Does NOT include:** Ragas evaluation (Run 1) or MCP server (Run 2). Both must be complete.

## Prerequisites

- Run 1 complete: `src/evaluation/` module, migration, `tests/test_evaluation.py` passing
- Run 2 complete: `src/mcp/server.py`, `tests/test_mcp_server.py` passing
- All existing tests passing: `uv run pytest tests/ -v`
- Branch: `feat/phase-5-evaluation-mcp`

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `tests/conftest.py` — All shared fixtures: `mock_pool` (line 15), `mock_cache` (line 31), `mock_memory_store` (line 43), `client` (line 54). The test patterns reference these.
- `tests/test_agent.py` — Complete example of agent unit test patterns; `_make_agent_response()` helper, mock pattern for `agent.run`, Langfuse tracing mock
- `tests/test_collector.py` — Boundary verification test pattern using `ast` module — `test_patterns/test_agent_unit.py` mirrors this
- `tests/test_api.py` — API integration test patterns using the `client` fixture
- `tests/test_orchestration.py` — LangGraph workflow test patterns — `test_patterns/test_workflow_e2e.py` mirrors this
- `src/agent/agent.py` (lines 39–62) — Agent definition; `result.output` accessor
- `src/orchestration/graph.py` (lines 63–66) — `_graph` is the module-level compiled graph; patch `_graph.ainvoke` in workflow tests
- `src/mcp/server.py` — MCP server from Run 2; mcp-integration.md documents running it
- `src/evaluation/` — Evaluation modules from Run 1; evaluation-guide.md documents running them
- `.env.example` — Phase 5 section added in Run 1; mcp-integration.md references these vars

### New Files to Create

- `tests/test_patterns/__init__.py`
- `tests/test_patterns/test_agent_unit.py`
- `tests/test_patterns/test_agent_integration.py`
- `tests/test_patterns/test_workflow_e2e.py`
- `docs/testing-patterns.md`
- `docs/evaluation-guide.md`
- `docs/mcp-integration.md`

### Patterns to Follow

**Test file header** (all test_patterns files should explain their purpose clearly):
```python
"""
Agent unit test patterns.

Reference examples demonstrating how to unit-test Pydantic AI agents
without making real LLM calls. These tests are the concrete examples
referenced in docs/testing-patterns.md.
"""
```

**Agent mock pattern** (from `tests/test_agent.py` lines 71–86):
```python
mock_result = MagicMock()
mock_result.output = expected_response  # .output not .data

with (
    patch("src.agent.agent.get_langfuse", return_value=None),
    patch("src.agent.agent.agent.run", AsyncMock(return_value=mock_result)),
):
    from src.agent.agent import run_agent
    result = await run_agent("question", mock_pool)
```

**Graph test pattern** (from `tests/test_orchestration.py`):
```python
with patch(
    "src.orchestration.graph._graph.ainvoke",
    AsyncMock(return_value={...state dict...}),
):
    result = await run_workflow("query", mock_pool)
```

**Boundary verification pattern** (from `tests/test_collector.py`):
```python
import ast, importlib.util
source = importlib.util.find_spec(mod.__name__).origin
with open(source) as f:
    tree = ast.parse(f.read())
# walk tree, assert no forbidden imports
```

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `tests/test_patterns/__init__.py`

```python
"""Example test patterns for AgentForge documentation."""
```
- **VALIDATE**: `uv run python -c "import tests.test_patterns; print('ok')"`

---

### Task 2: CREATE `tests/test_patterns/test_agent_unit.py`

```python
"""
Agent unit test patterns.

Reference examples demonstrating how to unit-test Pydantic AI agents
without making real LLM calls. These tests are the concrete examples
referenced in docs/testing-patterns.md.

Key patterns demonstrated:
  1. Mock agent.run() to return a controlled AgentResponse
  2. Use MagicMock(spec=RunContext) for tool context injection
  3. Patch get_langfuse() to None to disable tracing noise in unit tests
  4. Verify architectural boundary (collector must not import LLM deps)
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
    """run_agent() always returns an AgentResponse — never a raw string.

    This verifies the output contract: any code calling run_agent() can
    safely access .answer, .sources, and .confidence.
    """
    expected = _make_agent_response()
    mock_result = MagicMock()
    mock_result.output = expected  # Pydantic AI >= 1.0 uses .output

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
    assert 0.0 <= result.confidence <= 1.0


async def test_agent_tool_receives_pool_via_run_context(mock_pool):
    """Agent tools receive the pool through RunContext.deps — not a global.

    This verifies that the dependency injection pattern is wired correctly.
    Each agent.run() call gets its own pool reference.
    """
    from pydantic_ai import RunContext

    from src.agent.tools import query_recent_videos

    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_pool

    with patch("src.agent.tools.get_videos", AsyncMock(return_value=[])) as mock_get:
        await query_recent_videos(ctx, channel_id="UCtest", limit=5)
        mock_get.assert_called_once_with(mock_pool, "UCtest", 5)


async def test_agent_confidence_is_clamped_between_zero_and_one(mock_pool):
    """AgentResponse rejects confidence values outside [0.0, 1.0]."""
    from pydantic import ValidationError

    from src.agent.models import AgentResponse

    with pytest.raises(ValidationError):
        AgentResponse(answer="test", sources=[], confidence=1.5)

    with pytest.raises(ValidationError):
        AgentResponse(answer="test", sources=[], confidence=-0.1)


def test_collector_module_has_no_llm_imports():
    """CRITICAL: Collector must never import pydantic_ai, langfuse, or openai.

    This is the automated architecture review. It parses the collector source
    with the ast module and fails loudly if the boundary is violated.
    """
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
                root = alias.name.split(".")[0]
                assert root not in forbidden, (
                    f"Collector imports forbidden module: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            assert root not in forbidden, (
                f"Collector imports forbidden module: {node.module}"
            )
```
- **VALIDATE**: `uv run pytest tests/test_patterns/test_agent_unit.py -v --tb=short`

---

### Task 3: CREATE `tests/test_patterns/test_agent_integration.py`

```python
"""
Agent integration test patterns.

Reference examples for testing the full API stack end-to-end using an
httpx AsyncClient backed by the FastAPI ASGI app. The database pool and
LLM are mocked — no external services required.

Key patterns demonstrated:
  1. Use the shared 'client' fixture from conftest.py
  2. Patch at the route layer (src.api.routes.run_agent) not the agent layer
  3. Test both happy path and error path for each endpoint
  4. Verify response shape matches the schema

These are the concrete examples referenced in docs/testing-patterns.md.
"""

from unittest.mock import AsyncMock, patch

import pytest


async def test_ask_endpoint_returns_200_with_structured_response(client):
    """POST /api/ask returns 200 and an answer + sources on success."""
    from src.agent.models import AgentResponse, Source

    mock_response = AgentResponse(
        answer="The channel has covered Python, FastAPI, and AI.",
        sources=[
            Source(
                title="Python Tutorial",
                video_id="abc123",
                url="https://youtube.com/watch?v=abc123",
            )
        ],
        confidence=0.85,
    )

    with patch("src.api.routes.run_agent", AsyncMock(return_value=mock_response)):
        response = await client.post(
            "/api/ask",
            json={"question": "What topics has this channel covered?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert "sources" in body
    assert len(body["sources"]) == 1
    assert body["sources"][0]["video_id"] == "abc123"


async def test_ask_endpoint_returns_500_when_agent_raises(client):
    """POST /api/ask returns 500 when the agent raises an exception.

    Verifies that agent errors are caught and converted to HTTP 500
    rather than crashing the server or leaking tracebacks.
    """
    with patch(
        "src.api.routes.run_agent",
        AsyncMock(side_effect=RuntimeError("model timeout")),
    ):
        response = await client.post("/api/ask", json={"question": "Test"})

    assert response.status_code == 500
    assert "detail" in response.json()


async def test_research_endpoint_returns_workflow_response(client):
    """POST /api/research returns answer, sources, and confidence."""
    from src.agent.models import AgentResponse, Source

    mock_response = AgentResponse(
        answer="Multi-agent research result.",
        sources=[Source(title="Video", video_id="xyz", url="https://yt.be/xyz")],
        confidence=0.75,
    )

    with patch("src.api.routes.run_workflow", AsyncMock(return_value=mock_response)):
        response = await client.post(
            "/api/research",
            json={"query": "Research Python trends"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Multi-agent research result."
    assert "confidence" in body


async def test_health_endpoint_returns_ok(client):
    """GET /health returns 200 with status 'ok'."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_ask_endpoint_rejects_empty_question(client):
    """POST /api/ask rejects requests with missing question field."""
    response = await client.post("/api/ask", json={})
    assert response.status_code == 422  # FastAPI validation error
```
- **VALIDATE**: `uv run pytest tests/test_patterns/test_agent_integration.py -v --tb=short`

---

### Task 4: CREATE `tests/test_patterns/test_workflow_e2e.py`

```python
"""
Multi-agent workflow end-to-end test patterns.

Reference examples for testing LangGraph workflows. Patches the compiled
graph's ainvoke() method to control state output — this tests the graph
wiring and result extraction logic without real LLM calls.

Key patterns demonstrated:
  1. Patch _graph.ainvoke to return a controlled state dict
  2. Verify run_workflow() maps state dict → AgentResponse correctly
  3. Test the fallback path when final_answer is None (low-quality result)
  4. Verify Langfuse tracing is gracefully bypassed when not configured

These are the concrete examples referenced in docs/testing-patterns.md.
"""

from unittest.mock import AsyncMock, patch

import pytest


async def test_workflow_returns_agent_response_shape(mock_pool):
    """run_workflow() maps the graph's state dict to an AgentResponse correctly."""
    from src.agent.models import AgentResponse

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=None),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(
                return_value={
                    "final_answer": "Synthesised answer.",
                    "final_sources": ["vid1", "vid2"],
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
    assert len(result.sources) == 2


async def test_workflow_returns_fallback_when_final_answer_is_none(mock_pool):
    """run_workflow() returns a low-confidence fallback when final_answer is None.

    This tests the branch where analysis quality was too low and the workflow
    exhausted max_retries without producing a usable answer.
    """
    with (
        patch("src.orchestration.graph.get_langfuse", return_value=None),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(
                return_value={
                    "final_answer": None,
                    "final_sources": [],
                    "final_confidence": None,
                    "steps_completed": 3,
                }
            ),
        ),
    ):
        from src.orchestration.graph import run_workflow

        result = await run_workflow("Hard query", mock_pool)

    # Fallback message and minimum confidence
    assert result.answer is not None
    assert len(result.answer) > 0
    assert result.confidence == 0.1
    assert result.sources == []


async def test_workflow_injects_pool_into_initial_state(mock_pool):
    """run_workflow() passes the pool into WorkflowState so nodes can use it."""
    from src.orchestration.state import WorkflowState

    captured_states = []

    async def capture_state(state):
        captured_states.append(state)
        return {
            "final_answer": "ok",
            "final_sources": [],
            "final_confidence": 0.5,
            "steps_completed": 1,
        }

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=None),
        patch("src.orchestration.graph._graph.ainvoke", capture_state),
    ):
        from src.orchestration.graph import run_workflow

        await run_workflow("query", mock_pool)

    assert len(captured_states) == 1
    state = captured_states[0]
    assert isinstance(state, WorkflowState)
    assert state.pool is mock_pool
    assert state.query == "query"


async def test_workflow_propagates_exception_on_graph_failure(mock_pool):
    """run_workflow() re-raises exceptions from the graph after updating trace."""
    with (
        patch("src.orchestration.graph.get_langfuse", return_value=None),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(side_effect=RuntimeError("graph failed")),
        ),
        pytest.raises(RuntimeError, match="graph failed"),
    ):
        from src.orchestration.graph import run_workflow

        await run_workflow("query", mock_pool)
```
- **VALIDATE**: `uv run pytest tests/test_patterns/test_workflow_e2e.py -v --tb=short`

---

### Task 5: CREATE `docs/testing-patterns.md`

Write a comprehensive guide. Must include all sections below — use the test files just created as concrete code examples throughout.

**Required sections:**

#### 1. Overview — When to Use Which Test Type

Include this decision table:

| Scenario | Test type | File location |
|----------|-----------|---------------|
| Agent output structure | Unit | `tests/test_agent.py` |
| Tool delegation to DB | Unit | `tests/test_agent.py` |
| Collector boundary | Unit (AST) | `tests/test_collector.py` |
| API endpoint happy path | Integration | `tests/test_api.py` |
| API error handling | Integration | `tests/test_api.py` |
| Workflow graph routing | E2E (mocked graph) | `tests/test_orchestration.py` |
| Evaluation pipeline | Unit | `tests/test_evaluation.py` |
| MCP tool logic | Unit | `tests/test_mcp_server.py` |

#### 2. Mocking the Agent (No Real LLM Calls)

Show the exact pattern from `tests/test_patterns/test_agent_unit.py`:
- `mock_result.output = expected` — why `.output` not `.data`
- Why we patch `get_langfuse` to `None` in unit tests
- How to verify tool invocation count

#### 3. Testing the Collector/Reasoning Boundary

Show the AST boundary test pattern. Explain why this matters — a real example where the boundary was almost violated (importing langfuse for logging). Include the exact forbidden module set.

#### 4. Testing LangGraph Workflows

Show why we patch `_graph.ainvoke` (the compiled graph) rather than individual nodes. Explain that `_graph` is module-level in `src/orchestration/graph.py` (line 66) and is the right interception point.

#### 5. Using the Shared Fixtures

Document each fixture from `conftest.py`:
- `mock_pool` — what it mocks (fetch, fetchrow, execute, close), how to override for populated results
- `mock_cache` — when to use it (cache tests only)
- `mock_memory_store` — when to use it (memory agent tests)
- `client` — the full ASGI stack, what it patches at startup

#### 6. Running the Full Test Suite

```bash
uv run pytest tests/ -v --tb=short
uv run pytest tests/test_patterns/ -v  # patterns only
uv run pytest tests/test_agent.py::test_run_agent_returns_agent_response_when_tracing_disabled  # single test
```

#### 7. Evaluation in CI

Document the recommended approach: run evaluation as a **scheduled GitHub Actions job** (weekly or nightly), not on every PR. Include a sample workflow snippet showing how to add it as a separate job. Explain why: evaluation requires real Langfuse data and costs LLM tokens — neither is appropriate for every commit.

#### 8. Interpreting Ragas Metrics

| Metric | Healthy range | Low score means |
|--------|---------------|-----------------|
| Faithfulness | ≥ 0.8 | Answers not grounded in retrieved context — review system prompt |
| Response Relevancy | ≥ 0.7 | Answers don't address the question — check tool selection |
| Context Precision | ≥ 0.6 | Irrelevant chunks retrieved — improve search queries |
| Context Recall | ≥ 0.7 | Missing relevant context — increase search limit or improve query |

- **VALIDATE**: File exists with correct markdown headings

---

### Task 6: CREATE `docs/evaluation-guide.md`

**Required sections:**

#### Prerequisites
- Langfuse configured and running with agent traces (Phase 1/2 must have been used)
- `OPENAI_API_KEY` set (Ragas uses it for LLM judge)
- `EVAL_MODEL` set in `.env` (defaults to `gpt-4o`)
- At least ~20 traces in Langfuse for meaningful scores

#### Running Your First Evaluation
```bash
# Check how many traces are available
# (open Langfuse at http://localhost:3001 → Traces)

# Run with a small dataset first
uv run python scripts/evaluate.py --limit 20 --trace-name agent_run

# Expected output:
# Evaluation Report — 2026-03-16T...
# Dataset size: 18 samples        (some traces may be skipped if missing input/output)
#   context_precision: 0.712
#   faithfulness: 0.841
#   response_relevancy: 0.788
```

#### Exporting Dataset for Offline Use
```bash
uv run python scripts/export_dataset.py --limit 50 --output eval_data.json
```

Explain the JSON format and that `reference` (ground truth) will be null for all samples unless manually annotated.

#### Saving Results to Database
```bash
uv run python scripts/evaluate.py --save-to-db
```

Query historical results:
```sql
SELECT ran_at, dataset_size, results
FROM evaluation_runs
ORDER BY ran_at DESC
LIMIT 10;
```

#### When Scores Are Meaningful
- Need ≥ 20 samples for stable scores (< 20 = high variance)
- Run against the same trace filter each time for comparable results
- Scores vary by model — note which `EVAL_MODEL` was used

#### Acting on Low Scores
For each metric include specific actionable steps (not generic advice):
- **Low faithfulness**: agent is hallucinating beyond retrieved context → tighten system prompt with "only use data from your tools"
- **Low response_relevancy**: agent answers tangential questions → add clarification step or improve tool descriptions
- **Low context_precision**: irrelevant docs retrieved → increase `plainto_tsquery` precision or add semantic similarity filter

#### Adding Ground Truth for Supervised Metrics
Explain how to annotate `reference` fields in the exported JSON and re-run evaluation with `context_recall` enabled.

- **VALIDATE**: File exists with correct markdown headings

---

### Task 7: CREATE `docs/mcp-integration.md`

**Required sections:**

#### What MCP Enables
One paragraph: any MCP-compatible client (Claude Desktop, Cursor, VS Code Copilot, custom apps) can invoke AgentForge agent tools without knowing the FastAPI endpoint or implementation details.

#### Available Tools

| Tool | Description | Returns |
|------|-------------|---------|
| `ask_agent` | Ask the YouTube research agent a question | Answer string |
| `search_videos` | Full-text video database search | List of video dicts |
| `get_channel_summary` | Channel stats (video count, views, latest upload) | Stats dict or error string |
| `run_research_workflow` | Multi-agent research → analysis → synthesis | Synthesised answer string |

#### Running the Server

```bash
# stdio (for Claude Desktop and local clients):
uv run python scripts/mcp_server.py

# HTTP (for remote clients):
uv run python scripts/mcp_server.py --transport http --port 8001

# Via environment variable:
MCP_TRANSPORT=http MCP_PORT=8001 uv run python scripts/mcp_server.py
```

#### Claude Desktop Configuration

Exact JSON with Windows and macOS paths:

**macOS** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "agentforge": {
      "command": "uv",
      "args": ["run", "python", "scripts/mcp_server.py"],
      "cwd": "/absolute/path/to/agentforge"
    }
  }
}
```

**Windows** (`%APPDATA%\Claude\claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "agentforge": {
      "command": "uv",
      "args": ["run", "python", "scripts/mcp_server.py"],
      "cwd": "C:\\path\\to\\agentforge"
    }
  }
}
```

Restart Claude Desktop after editing. The agentforge server should appear in the tools panel.

#### Mounting into FastAPI (Optional)

For teams that prefer a single process serving both REST and MCP:

```python
# In src/api/main.py, after create_app():
from src.mcp.server import mcp

app.mount("/mcp", mcp.http_app(path="/"))
```

Note: the MCP server's own lifespan (DB pool) is independent of the FastAPI lifespan — both run. See FastMCP docs on `combine_lifespans()` if pool sharing is needed.

#### Testing MCP Connectivity

```bash
# Verify server starts (should print tool list and wait):
uv run python scripts/mcp_server.py --transport http &
curl http://localhost:8001/  # or use an MCP inspector tool
```

#### Security Guidance

- The MCP server exposes **read-only** tools only — no data mutation, no admin operations
- stdio transport (default) is local-only — safe for personal use without auth
- HTTP transport exposes the server on the network — add a reverse proxy with auth before exposing publicly
- Never expose mutation tools (upsert_*, delete_*) via MCP

- **VALIDATE**: File exists with correct markdown headings

---

## VALIDATION COMMANDS

```bash
# Level 1 — style (test_patterns files only)
uv run ruff check tests/test_patterns/
uv run ruff format --check tests/test_patterns/

# Level 2 — new test patterns
uv run pytest tests/test_patterns/ -v --tb=short

# Level 3 — full regression
uv run pytest tests/ -v --tb=short

# Level 4 — doc files exist
test -f docs/testing-patterns.md && echo "ok" || echo "MISSING"
test -f docs/evaluation-guide.md && echo "ok" || echo "MISSING"
test -f docs/mcp-integration.md && echo "ok" || echo "MISSING"
```

## ACCEPTANCE CRITERIA

- [ ] `tests/test_patterns/__init__.py` exists
- [ ] `tests/test_patterns/test_agent_unit.py` passes — boundary test included
- [ ] `tests/test_patterns/test_agent_integration.py` passes — uses `client` fixture
- [ ] `tests/test_patterns/test_workflow_e2e.py` passes — patches `_graph.ainvoke`
- [ ] `docs/testing-patterns.md` exists and covers all 8 required sections
- [ ] `docs/evaluation-guide.md` exists and covers prerequisites through acting on scores
- [ ] `docs/mcp-integration.md` exists and includes Claude Desktop JSON for both platforms
- [ ] `uv run pytest tests/ -v` all pass (zero regressions from Runs 1 and 2)
- [ ] `uv run ruff check .` zero errors
- [ ] `uv run ruff format --check .` zero formatting issues

## PHASE 5 COMPLETE WHEN

All three runs' acceptance criteria are met:
- Run 1: Ragas evaluation pipeline working, `tests/test_evaluation.py` passing
- Run 2: MCP server with 4 tools, `tests/test_mcp_server.py` passing
- Run 3: Test patterns + docs complete, `tests/test_patterns/` passing
- `uv run pytest tests/ -v` — all tests green, zero regressions
- `uv run ruff check .` — zero errors
