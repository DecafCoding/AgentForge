# Phase 5 — Evaluation & Quality

*AgentForge Starter Kit*

---

## Purpose of This Document

This document contains everything an AI or developer needs to build Phase 5 of AgentForge. It is self-contained. Phase 5 adds evaluation pipelines (Ragas), MCP server exposure (FastMCP), and comprehensive testing documentation — giving developers the tools to measure, improve, and expose agent quality.

---

## Prerequisites (Phases 1–4 Complete)

Phase 5 assumes the following are already built and working:

**From Phase 1:**
- Project structure with `uv`, `ruff`, Docker Compose (bundled + shared profiles)
- Postgres 15 + pgvector with Alembic migrations and asyncpg driver
- Pydantic AI agent with tool registration and structured output (Pattern 1)
- FastAPI API layer with lifespan hook and APScheduler
- Langfuse observability wired into all agent calls
- Collector/reasoning separation enforced by module structure
- Multi-provider support (OpenAI, Groq) via env vars
- Pytest skeleton and GitHub Actions CI

**From Phase 2:**
- LangGraph multi-agent orchestration (Pattern 2)
- Cross-agent Langfuse traces with per-agent child spans

**From Phase 3:**
- Mem0 long-term memory with Postgres backend
- Crawl4AI web scraping collector
- Brave Search web search tool

**From Phase 4:**
- Ollama local model serving
- SearXNG self-hosted web search
- Redis/Valkey caching layer (if bottleneck was identified)

---

## What Phase 5 Delivers

Three capabilities focused on quality and interoperability:

1. **Ragas Evaluation Pipelines** — Measure agent quality with real metrics (faithfulness, answer relevancy, context recall) against actual agent interactions. Not a theoretical framework — evaluation runs against real data.
2. **FastMCP Server Exposure** — Agent capabilities exposed as MCP (Model Context Protocol) tools, making them composable with other AI systems and MCP clients (Claude Desktop, Cursor, etc.).
3. **Testing Patterns Documentation** — Comprehensive guide covering unit testing agents, integration testing multi-agent workflows, and evaluation as a continuous practice.

---

## Technology Additions

| Layer | Tool | Role |
|-------|------|------|
| Agent Development | `ragas` | Evaluation pipelines for measuring agent quality |
| Agent Development | `fastmcp` | MCP server for exposing agent tools to external clients |

Add to `pyproject.toml`:
```toml
[project]
dependencies = [
    # ... existing Phase 1-4 deps ...
    "ragas",
    "fastmcp",
    "datasets",  # Required by Ragas for dataset handling
]
```

---

## Project Structure Changes

```
agentforge/
├── src/
│   ├── evaluation/                 # NEW — Agent quality measurement
│   │   ├── __init__.py
│   │   ├── pipeline.py             # Ragas evaluation pipeline setup
│   │   ├── dataset.py              # Dataset creation from real agent interactions
│   │   ├── metrics.py              # Custom metrics and metric selection
│   │   └── reporter.py             # Evaluation results formatting and storage
│   │
│   ├── mcp/                        # NEW — MCP server exposure
│   │   ├── __init__.py
│   │   ├── server.py               # FastMCP server definition
│   │   └── tools.py                # Agent capabilities exposed as MCP tools
│   │
│   ├── agent/                      # EXISTING
│   │   ├── agent.py                # Unchanged
│   │   └── tools.py                # Unchanged — MCP tools call these
│
├── scripts/
│   ├── evaluate.py                 # NEW — Run evaluation pipeline manually
│   └── export_dataset.py           # NEW — Export agent interactions for evaluation
│
├── docs/
│   ├── testing-patterns.md         # NEW — Comprehensive testing guide
│   ├── evaluation-guide.md         # NEW — How to run and interpret evaluations
│   └── mcp-integration.md          # NEW — Using AgentForge agents from MCP clients
│
└── tests/
    ├── test_evaluation.py          # NEW — Evaluation pipeline tests
    ├── test_mcp_server.py          # NEW — MCP server tests
    └── test_patterns/              # NEW — Example test patterns
        ├── test_agent_unit.py      # Unit test patterns for agents
        ├── test_agent_integration.py  # Integration test patterns
        └── test_workflow_e2e.py    # End-to-end multi-agent workflow tests
```

---

## Product Backlog Items (PBIs)

### PBI 5.1 — Ragas Evaluation Pipelines

**Description:** Evaluation setup, metrics against real agent output.

**Done when:** Pipeline produces actionable metrics from real agent interactions.

**Implementation details:**

**Why evaluation matters now (and not before):**

Evaluation is meaningless without data. By Phase 5, the kit has been running with real agents producing real interactions logged in Langfuse. There is now enough data to evaluate. Ragas provides standardized metrics for RAG and agent quality without building a custom evaluation framework.

**`src/evaluation/dataset.py`** — Creating evaluation datasets from real interactions:

```python
from datasets import Dataset
from langfuse import Langfuse
from pydantic import BaseModel
from typing import Optional

class EvalSample(BaseModel):
    question: str
    answer: str
    contexts: list[str]
    ground_truth: Optional[str] = None

async def create_dataset_from_langfuse(
    langfuse: Langfuse,
    limit: int = 100,
    trace_name: Optional[str] = None,
) -> Dataset:
    """Extract agent interactions from Langfuse traces into a Ragas-compatible dataset.

    Each trace becomes one evaluation sample:
    - question: the user's input
    - answer: the agent's response
    - contexts: the data retrieved by tools (from child spans)
    - ground_truth: manually annotated (optional, for supervised metrics)
    """
    traces = langfuse.fetch_traces(name=trace_name, limit=limit)

    samples = []
    for trace in traces.data:
        # Extract input/output from trace
        question = trace.input.get("question", "") if trace.input else ""
        answer = trace.output.get("answer", "") if trace.output else ""

        # Extract contexts from tool call spans
        contexts = []
        observations = langfuse.fetch_observations(trace_id=trace.id)
        for obs in observations.data:
            if obs.type == "tool" and obs.output:
                contexts.append(str(obs.output))

        samples.append(EvalSample(
            question=question,
            answer=answer,
            contexts=contexts,
        ))

    return Dataset.from_dict({
        "question": [s.question for s in samples],
        "answer": [s.answer for s in samples],
        "contexts": [s.contexts for s in samples],
    })
```

**`src/evaluation/pipeline.py`** — Ragas evaluation pipeline:

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset

# Default metrics for agent evaluation
DEFAULT_METRICS = [
    faithfulness,       # Is the answer faithful to the retrieved context?
    answer_relevancy,   # Is the answer relevant to the question?
    context_precision,  # Are the retrieved contexts relevant?
]

# Additional metrics when ground truth is available
SUPERVISED_METRICS = [
    context_recall,     # Did we retrieve all relevant context?
]

async def run_evaluation(
    dataset: Dataset,
    metrics: list = None,
    model: str = "gpt-4o",
) -> dict:
    """Run Ragas evaluation on a dataset of agent interactions.

    Args:
        dataset: Ragas-compatible dataset with question, answer, contexts
        metrics: List of Ragas metrics to compute (defaults to DEFAULT_METRICS)
        model: LLM used by Ragas for metric computation (evaluator model)

    Returns:
        Dictionary with metric names and scores
    """
    if metrics is None:
        # Use supervised metrics only if ground_truth is present
        if "ground_truth" in dataset.column_names:
            metrics = DEFAULT_METRICS + SUPERVISED_METRICS
        else:
            metrics = DEFAULT_METRICS

    results = evaluate(dataset=dataset, metrics=metrics, llm=model)
    return results.to_pandas().to_dict()
```

**`src/evaluation/reporter.py`** — Results formatting:

```python
from datetime import datetime

class EvalReport:
    """Format and store evaluation results."""

    def __init__(self, results: dict, dataset_size: int):
        self.results = results
        self.dataset_size = dataset_size
        self.timestamp = datetime.utcnow()

    def summary(self) -> str:
        """Human-readable summary of evaluation results."""
        lines = [
            f"Evaluation Report — {self.timestamp.isoformat()}",
            f"Dataset size: {self.dataset_size} samples",
            "",
        ]
        for metric, scores in self.results.items():
            if isinstance(scores, dict):
                avg = sum(scores.values()) / len(scores) if scores else 0
                lines.append(f"  {metric}: {avg:.3f} (avg)")
            else:
                lines.append(f"  {metric}: {scores:.3f}")
        return "\n".join(lines)

    async def save_to_db(self, pool):
        """Store evaluation results in Postgres for tracking over time."""
        await pool.execute(
            """INSERT INTO evaluation_runs (timestamp, dataset_size, results)
               VALUES ($1, $2, $3)""",
            self.timestamp, self.dataset_size, json.dumps(self.results)
        )
```

**`scripts/evaluate.py`** — Manual evaluation runner:

```python
"""Run evaluation pipeline against real agent interactions.

Usage:
    uv run python scripts/evaluate.py --limit 50 --trace-name "ask"
"""
import asyncio
import argparse
from src.evaluation.dataset import create_dataset_from_langfuse
from src.evaluation.pipeline import run_evaluation
from src.evaluation.reporter import EvalReport

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--trace-name", type=str, default=None)
    args = parser.parse_args()

    # Create dataset from Langfuse traces
    dataset = await create_dataset_from_langfuse(langfuse, limit=args.limit, trace_name=args.trace_name)
    print(f"Created dataset with {len(dataset)} samples")

    # Run evaluation
    results = await run_evaluation(dataset)

    # Report
    report = EvalReport(results, len(dataset))
    print(report.summary())

if __name__ == "__main__":
    asyncio.run(main())
```

**Database migration for evaluation tracking:**

```sql
CREATE TABLE evaluation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    dataset_size INTEGER NOT NULL,
    results JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### PBI 5.2 — FastMCP Server Exposure

**Description:** Agent capabilities exposed as MCP tools.

**Done when:** An agent tool is callable from an MCP client (e.g., Claude Desktop, Cursor).

**Implementation details:**

**What MCP enables:**

The Model Context Protocol (MCP) is a standard for exposing tool capabilities to AI systems. By wrapping AgentForge agent tools as MCP tools, any MCP-compatible client can use the agent's capabilities — asking questions, searching data, running workflows — without knowing the implementation details.

**`src/mcp/server.py`** — FastMCP server:

```python
from fastmcp import FastMCP

mcp = FastMCP("AgentForge")

@mcp.tool()
async def ask_agent(question: str) -> str:
    """Ask the YouTube research agent a question.

    The agent queries a database of YouTube video metadata and transcripts
    to provide source-cited answers about content trends, video performance,
    and channel analytics.
    """
    from src.agent.agent import agent
    from src.db.client import get_pool

    pool = await get_pool()
    result = await agent.run(question, deps=pool)
    return result.data.answer

@mcp.tool()
async def search_videos(query: str, limit: int = 5) -> list[dict]:
    """Search the video database for videos matching a query.

    Returns video titles, descriptions, view counts, and links.
    """
    from src.db.queries import search_videos_by_query
    from src.db.client import get_pool

    pool = await get_pool()
    videos = await search_videos_by_query(pool, query, limit)
    return [v.model_dump() for v in videos]

@mcp.tool()
async def get_channel_summary(channel_id: str) -> dict:
    """Get a summary of a YouTube channel's content and performance metrics."""
    from src.db.queries import get_channel_stats
    from src.db.client import get_pool

    pool = await get_pool()
    stats = await get_channel_stats(pool, channel_id)
    return stats.model_dump()

@mcp.tool()
async def run_research_workflow(query: str) -> str:
    """Run the multi-agent research workflow (research → analysis → synthesis).

    Uses multiple agents to research a topic, analyze the findings,
    and synthesize a comprehensive response.
    """
    from src.orchestration.graph import build_workflow, run_workflow
    from src.db.client import get_pool

    pool = await get_pool()
    result = await run_workflow(query, pool)
    return result.get("final_output", "No result produced")
```

**Running the MCP server:**

FastMCP can run as a standalone process or be integrated into the FastAPI app:

```python
# Standalone: scripts/mcp_server.py
if __name__ == "__main__":
    from src.mcp.server import mcp
    mcp.run(transport="stdio")  # For Claude Desktop / local clients
    # Or: mcp.run(transport="sse", port=8001)  # For remote clients
```

**MCP client configuration (for Claude Desktop):**

```json
{
  "mcpServers": {
    "agentforge": {
      "command": "uv",
      "args": ["run", "python", "scripts/mcp_server.py"],
      "cwd": "/path/to/agentforge"
    }
  }
}
```

**What tools to expose:**
- `ask_agent` — The primary agent interaction (Pattern 1)
- `search_videos` — Direct database search without LLM reasoning
- `get_channel_summary` — Aggregated channel data
- `run_research_workflow` — The Pattern 2 multi-agent workflow
- Only expose tools that are safe for external consumption — no admin/mutation tools

### PBI 5.3 — Testing Patterns Documentation

**Description:** Comprehensive guide for unit testing agents, integration testing multi-agent workflows, evaluation as practice.

**Done when:** Developer has clear patterns for testing every layer of the stack.

**Implementation details:**

**`docs/testing-patterns.md`** — Comprehensive testing guide covering:

**1. Unit Testing Agents**

```python
# tests/test_patterns/test_agent_unit.py
"""Unit test patterns for Pydantic AI agents."""
import pytest
from pydantic_ai.models.test import TestModel
from src.agent.agent import agent

@pytest.fixture
def test_model():
    """Use Pydantic AI's test model to avoid real LLM calls."""
    return TestModel(
        # Configure expected responses for deterministic testing
        custom_result_text="This video was published on January 15, 2026."
    )

@pytest.mark.asyncio
async def test_agent_returns_structured_output(test_model):
    """Agent should return a properly structured AgentResponse."""
    result = await agent.run(
        "When was the latest video published?",
        model=test_model,
        deps=mock_pool,
    )
    assert result.data.answer is not None
    assert isinstance(result.data.sources, list)
    assert isinstance(result.data.confidence, float)

@pytest.mark.asyncio
async def test_agent_tool_is_called(test_model):
    """Agent should call the query_videos tool for database questions."""
    result = await agent.run(
        "Show me videos from channel X",
        model=test_model,
        deps=mock_pool,
    )
    # Verify tool was invoked
    assert any(call.tool_name == "query_videos" for call in result.all_messages())
```

**2. Testing Collectors (No Mocking LLMs)**

```python
# tests/test_patterns/test_collector_unit.py
"""Collector tests are simpler — no LLM to mock."""
import pytest
from unittest.mock import AsyncMock, patch
from src.collector.youtube import YouTubeCollector

@pytest.mark.asyncio
async def test_collector_stores_data(mock_pool):
    """Collector should fetch from API and store in database."""
    with patch("src.collector.youtube.fetch_videos") as mock_fetch:
        mock_fetch.return_value = [{"video_id": "abc", "title": "Test"}]

        collector = YouTubeCollector(mock_pool, channels=["UCxyz"])
        count = await collector.collect()

        assert count == 1
        mock_pool.execute.assert_called_once()

def test_collector_has_no_llm_imports():
    """CRITICAL: Verify collector module boundary is intact."""
    import importlib
    import src.collector.youtube as mod
    source = importlib.util.find_spec(mod.__name__).origin

    with open(source) as f:
        content = f.read()

    assert "pydantic_ai" not in content
    assert "langfuse" not in content
    assert "openai" not in content
```

**3. Integration Testing Multi-Agent Workflows**

```python
# tests/test_patterns/test_workflow_e2e.py
"""End-to-end tests for LangGraph multi-agent workflows."""
import pytest
from src.orchestration.graph import build_workflow
from src.orchestration.state import WorkflowState

@pytest.mark.asyncio
async def test_workflow_runs_end_to_end(mock_pool, test_models):
    """Full workflow should execute all nodes and produce output."""
    workflow = build_workflow()
    state = WorkflowState(query="Test query", deps=mock_pool)

    result = await workflow.ainvoke(state)

    assert result["final_output"] is not None
    assert result["steps_completed"] >= 1

@pytest.mark.asyncio
async def test_workflow_retries_on_low_quality(mock_pool, test_models):
    """Workflow should retry research when analysis quality is low."""
    # Configure test model to return low quality score on first pass
    workflow = build_workflow()
    state = WorkflowState(query="Test query", deps=mock_pool)

    result = await workflow.ainvoke(state)

    assert result["steps_completed"] > 1  # Must have retried
```

**4. Evaluation as Continuous Practice**

```python
# tests/test_evaluation.py
"""Evaluation pipeline tests — ensure eval infra works."""
import pytest
from datasets import Dataset
from src.evaluation.pipeline import run_evaluation, DEFAULT_METRICS

@pytest.mark.asyncio
async def test_evaluation_pipeline_runs():
    """Eval pipeline should produce scores for all default metrics."""
    # Create a minimal test dataset
    dataset = Dataset.from_dict({
        "question": ["What videos are trending?"],
        "answer": ["The top trending video is X with 1M views."],
        "contexts": [["Video X has 1,000,000 views and was published yesterday."]],
    })

    results = await run_evaluation(dataset, metrics=DEFAULT_METRICS)

    for metric in DEFAULT_METRICS:
        assert metric.name in results
```

**5. Documentation structure in `docs/testing-patterns.md`:**

- When to unit test vs integration test vs e2e test
- How to mock LLM providers using Pydantic AI's TestModel
- How to test the collector/reasoning boundary (import verification tests)
- How to test LangGraph workflows with conditional edges
- How to set up a test database for integration tests
- How to run evaluations in CI (as a scheduled job, not on every PR)
- How to interpret Ragas metrics and act on them

---

## Updated Environment Variables

Add to `.env.example`:

```env
# === Evaluation (Phase 5) ===
EVAL_MODEL=gpt-4o                 # Model used by Ragas for evaluation computation
EVAL_DATASET_LIMIT=100            # Max traces to include in evaluation dataset

# === MCP Server (Phase 5) ===
MCP_TRANSPORT=stdio               # stdio | sse
MCP_PORT=8001                     # Port for SSE transport (if used)
```

---

## Acceptance Criteria (Phase 5 Complete)

All of these must be true (in addition to all Phase 1–4 criteria still passing):

1. `ragas` and `fastmcp` are in `pyproject.toml` and resolve via `uv sync`
2. `scripts/export_dataset.py` extracts agent interactions from Langfuse into a Ragas-compatible dataset
3. `scripts/evaluate.py` runs the evaluation pipeline and prints metric scores
4. Evaluation results include faithfulness, answer relevancy, and context precision scores
5. Evaluation results can be stored in Postgres for tracking over time
6. FastMCP server starts and exposes at least 3 agent tools
7. `ask_agent` MCP tool accepts a question and returns an agent-generated answer
8. `run_research_workflow` MCP tool triggers the multi-agent workflow and returns results
9. MCP server is callable from an MCP client (tested with Claude Desktop config or programmatic client)
10. `docs/testing-patterns.md` covers unit testing, integration testing, workflow testing, and evaluation
11. `docs/evaluation-guide.md` covers running evaluations, interpreting metrics, and acting on results
12. `docs/mcp-integration.md` covers configuring MCP clients to connect to AgentForge
13. Example test files in `tests/test_patterns/` demonstrate all documented patterns
14. All existing Phase 1–4 tests still pass
15. New tests cover: evaluation pipeline, MCP server tools, boundary verification

---

## What Is NOT in Phase 5

These remain deferred:

- **Frontend / UI** → Phase 6
- **Reverse proxy / HTTPS** (Caddy) → Phase 6
- **Production Docker configuration** → Phase 6
- **Automated evaluation in CI** — Document how to do it, but don't enforce it in the default CI pipeline. Teams can add it when ready.
- **Custom Ragas metrics** — Start with built-in metrics. Custom metrics come from real evaluation needs.
- **MCP authentication** — The MCP server is intended for local/trusted use. Auth can be added later if remote access is needed.

---

*This document is the complete specification for Phase 5 of AgentForge. It contains everything needed to add evaluation pipelines and MCP server exposure without referencing external documents.*
