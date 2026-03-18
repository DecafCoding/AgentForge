# Testing Patterns

*AgentForge — Comprehensive Testing Guide*

---

## 1. Overview — When to Use Which Test Type

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

**Rule of thumb:** Unit tests for logic and contracts, integration tests for HTTP layer, E2E tests for multi-node workflows. All tests mock external dependencies (LLM providers, Langfuse, databases).

Reference example files live in `tests/test_patterns/` and demonstrate each category.

---

## 2. Mocking the Agent (No Real LLM Calls)

Agent tests never call a real LLM. The pattern is:

```python
from unittest.mock import AsyncMock, MagicMock, patch

mock_result = MagicMock()
mock_result.output = expected_response  # .output — NOT .data

with (
    patch("src.agent.agent.get_langfuse", return_value=None),
    patch("src.agent.agent.agent.run", AsyncMock(return_value=mock_result)),
):
    from src.agent.agent import run_agent
    result = await run_agent("question", mock_pool)
```

**Why `.output` not `.data`?** Pydantic AI >= 1.0 changed the result accessor from `result.data` to `result.output`. All AgentForge code uses `.output`.

**Why patch `get_langfuse` to `None`?** Suppresses tracing setup in unit tests. Without this, the test would attempt to initialise a Langfuse client and create trace objects — noisy and unnecessary for verifying agent logic.

**Verifying tool invocation:** To check that the agent called a specific tool, inspect the mock:

```python
mock_agent.run.assert_called_once_with("question", deps=mock_pool)
```

See `tests/test_patterns/test_agent_unit.py` for complete working examples.

---

## 3. Testing the Collector/Reasoning Boundary

The collector/reasoning separation is a core architectural invariant:

- `src/collector/` must **never** import `pydantic_ai`, `langfuse`, or `openai`
- `src/agent/` must **never** import `apscheduler` or `httpx`

This is verified with AST-based import scanning:

```python
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
            assert root not in forbidden
    elif isinstance(node, ast.ImportFrom):
        root = (node.module or "").split(".")[0]
        assert root not in forbidden
```

**Why this matters:** The boundary was almost violated during Phase 1 when someone considered importing `langfuse` in a collector for structured logging. This would have broken the zero-token-spend guarantee for collectors. The AST test catches this at CI time — no manual review required.

The forbidden module set: `{"pydantic_ai", "langfuse", "openai"}` for collectors; `{"apscheduler", "httpx"}` for agents.

See `tests/test_patterns/test_agent_unit.py::test_collector_module_has_no_llm_imports` and `tests/test_collector.py` for the full implementations.

---

## 4. Testing LangGraph Workflows

Workflow tests patch `_graph.ainvoke` — the compiled graph instance — rather than individual nodes:

```python
with (
    patch("src.orchestration.graph.get_langfuse", return_value=None),
    patch(
        "src.orchestration.graph._graph.ainvoke",
        AsyncMock(return_value={
            "final_answer": "Synthesised answer.",
            "final_sources": ["vid1", "vid2"],
            "final_confidence": 0.8,
            "steps_completed": 3,
        }),
    ),
):
    result = await run_workflow("query", mock_pool)
```

**Why patch `_graph.ainvoke`?** The compiled graph (`_graph`) is a module-level object in `src/orchestration/graph.py` (line 66). It is the single interception point for the entire workflow. Patching individual node functions would require mocking three separate agent calls — fragile and verbose. Patching `ainvoke` lets you control the entire output in one mock.

**What to test:**
- State dict → `AgentResponse` mapping (happy path)
- Fallback when `final_answer` is `None` (low-quality result)
- Pool injection into `WorkflowState`
- Exception propagation from graph failures

See `tests/test_patterns/test_workflow_e2e.py` for complete working examples.

---

## 5. Using the Shared Fixtures

All shared fixtures live in `tests/conftest.py`.

### `mock_pool`

A `MagicMock` simulating an asyncpg `Pool` with async methods:

- `pool.fetch` → returns `[]` (empty result set)
- `pool.fetchrow` → returns `None` (no row found)
- `pool.execute` → returns `None` (no-op write)
- `pool.close` → async no-op

**Override for populated results:**

```python
async def test_search_returns_videos(mock_pool):
    mock_pool.fetch = AsyncMock(return_value=[
        {"video_id": "abc", "channel_id": "UC1", "title": "Test", ...}
    ])
    # ... test with populated data
```

### `mock_cache`

A mock Redis connection. Use only in cache-specific tests (`tests/test_cache.py`). Methods: `get`, `set`, `delete`, `ping`, `aclose`.

### `mock_memory_store`

A mock `BaseMemoryStore`. Use in memory agent tests (`tests/test_memory_agent.py`). Methods: `add`, `search`, `get_all`, `delete`.

### `client`

An `httpx.AsyncClient` backed by the FastAPI ASGI app with all external services mocked:

- Database pool → `mock_pool`
- APScheduler → no-op
- Memory client → `None` (disabled)
- Cache pool → `None` (disabled)
- Langfuse validation → suppressed

The `client` fixture does **not** run the FastAPI lifespan — it injects `app.state` directly. This means startup/shutdown logic is not tested; use it for route-level integration tests only.

---

## 6. Running the Full Test Suite

```bash
# All tests
uv run pytest tests/ -v --tb=short

# Test patterns only
uv run pytest tests/test_patterns/ -v

# Single test by name
uv run pytest tests/test_agent.py::test_run_agent_returns_agent_response_when_tracing_disabled

# With coverage (if pytest-cov is installed)
uv run pytest tests/ --cov=src --cov-report=term-missing

# Lint check (must pass before commit)
uv run ruff check .
uv run ruff format --check .
```

---

## 7. Evaluation in CI

Evaluation should run as a **scheduled GitHub Actions job** — not on every PR.

**Why not on every PR?**
- Evaluation requires real Langfuse traces (not available in fresh CI environments)
- Ragas uses LLM calls for metric computation → costs real tokens
- Scores are only meaningful with ≥ 20 samples → requires a populated database

**Recommended approach:** Run evaluation weekly or nightly against a staging environment with accumulated traces.

**Sample GitHub Actions workflow:**

```yaml
name: Evaluation
on:
  schedule:
    - cron: "0 6 * * 1"  # Every Monday at 6 AM UTC
  workflow_dispatch: {}    # Allow manual triggers

jobs:
  evaluate:
    runs-on: ubuntu-latest
    env:
      DATABASE_URL: ${{ secrets.STAGING_DATABASE_URL }}
      LANGFUSE_HOST: ${{ secrets.STAGING_LANGFUSE_HOST }}
      LANGFUSE_PUBLIC_KEY: ${{ secrets.STAGING_LANGFUSE_PUBLIC_KEY }}
      LANGFUSE_SECRET_KEY: ${{ secrets.STAGING_LANGFUSE_SECRET_KEY }}
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      EVAL_MODEL: gpt-4o
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run python scripts/evaluate.py --limit 50 --save-to-db
```

---

## 8. Interpreting Ragas Metrics

| Metric | Healthy range | Low score means |
|--------|---------------|-----------------|
| Faithfulness | ≥ 0.8 | Answers not grounded in retrieved context — review system prompt |
| Response Relevancy | ≥ 0.7 | Answers don't address the question — check tool selection |
| Context Precision | ≥ 0.6 | Irrelevant chunks retrieved — improve search queries |
| Context Recall | ≥ 0.7 | Missing relevant context — increase search limit or improve query |

**Faithfulness** measures whether the agent's answer is supported by the contexts its tools retrieved. A low score means the agent is hallucinating beyond what the data shows. Fix: tighten the system prompt with explicit instructions like "only use data from your tools."

**Response Relevancy** measures whether the answer addresses the actual question asked. A low score means the agent goes off-topic. Fix: improve tool descriptions so the LLM selects the right tool, or add a clarification step.

**Context Precision** measures whether the retrieved documents are relevant to the question. A low score means the search is returning noise. Fix: improve `plainto_tsquery` precision, add semantic similarity filtering, or reduce the search limit.

**Context Recall** (supervised — requires ground truth) measures whether all relevant context was retrieved. A low score means the search is missing data. Fix: increase the search limit, improve query expansion, or add more data sources.

See `docs/evaluation-guide.md` for detailed instructions on running evaluations and acting on results.
