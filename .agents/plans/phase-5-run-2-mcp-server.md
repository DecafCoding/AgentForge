# Phase 5 — Run 2: FastMCP Server Exposure (PBI 5.2)

The following plan should be complete, but validate documentation and codebase patterns before implementing.

Pay special attention to FastMCP `Context` injection and `lifespan` pattern. After `uv sync`, run the API verification commands below before writing any tool code.

## What This Run Delivers

- `src/mcp/` module with FastMCP server and 4 agent tools
- `scripts/mcp_server.py` standalone runner
- `tests/test_mcp_server.py`

**Does NOT include:** Ragas evaluation (Run 1), test patterns, or documentation (Run 3).

## Prerequisites

- Run 1 complete (deps installed, migration applied, `src/evaluation/` module exists)
- All existing tests passing: `uv run pytest tests/ -v`
- Branch: `feat/phase-5-evaluation-mcp`

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/agent/agent.py` (lines 39–62, 65–129) — Agent definition and `run_agent()` pattern. Note: **`result.output`** is the correct Pydantic AI ≥1.0 accessor — NOT `result.data`. The MCP `ask_agent` tool calls `agent.run()` directly (not `run_agent()`) to avoid Langfuse coupling.
- `src/agent/models.py` — `AgentResponse.answer` (str), `Source` — what MCP tools return
- `src/db/client.py` — `create_pool()` and `close_pool()` — MCP lifespan calls these directly
- `src/db/queries.py` — `search_videos()` (line 156), `get_channel_stats()` (line 182), `VideoSummary`, `ChannelStats` — MCP tools call these query functions
- `src/orchestration/graph.py` (lines 69–143) — `run_workflow(query, pool)` returns `AgentResponse` directly. **NOT a dict.** Use `result.answer`, not `result.get("final_answer")`.
- `src/config.py` — `MCP_TRANSPORT` and `MCP_PORT` already added in Run 1
- `tests/conftest.py` — `mock_pool` fixture; `test_mcp_server.py` uses this
- `tests/test_agent.py` (lines 69–107) — `patch("src.agent.agent.agent.run", AsyncMock(...))` — follow this mock pattern exactly for `ask_agent` test

### New Files to Create

- `src/mcp/__init__.py`
- `src/mcp/server.py`
- `scripts/mcp_server.py`
- `tests/test_mcp_server.py`

### Patterns to Follow

**MCP lifespan with DB pool** (FastMCP 2.x):
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
```

**Accessing pool in tools** — via `ctx: Context` parameter:
```python
@mcp.tool
async def my_tool(param: str, ctx: Context) -> str:
    pool = ctx.state.pool
    ...
```

**Pydantic AI result access** — `result.output` not `result.data`:
```python
result = await agent.run(question, deps=pool)
return result.output.answer   # ✓ correct
# return result.data.answer   # ✗ old API (pre-1.0)
```

**Workflow result** — `AgentResponse`, not a dict:
```python
result = await run_workflow(query, pool)
return result.answer          # ✓ correct (AgentResponse.answer)
# return result.get("final_answer")  # ✗ wrong type
```

---

## FASTMCP API VERIFICATION (do this before writing server code)

```bash
uv run python -c "from fastmcp import FastMCP, Context; print('FastMCP ok')"
uv run python -c "import fastmcp; print('version:', fastmcp.__version__)"
uv run python -c "from fastmcp import FastMCP; mcp = FastMCP('test'); print('tools:', mcp.list_tools())"
```

**If `Context` is not in `fastmcp`:** try `from fastmcp.server import Context`.
**If `mcp.state` is not available:** check FastMCP docs for the correct lifespan state access pattern for the installed version.

---

## STEP-BY-STEP TASKS

### Task 1: CREATE `src/mcp/__init__.py`

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

### Task 2: CREATE `src/mcp/server.py`

```python
"""
FastMCP server definition.

Exposes four AgentForge capabilities as MCP tools:
  - ask_agent: Single-agent question answering (Pattern 1)
  - search_videos: Direct database video search (no LLM)
  - get_channel_summary: Aggregated channel statistics
  - run_research_workflow: Multi-agent LangGraph pipeline (Pattern 2)

The server manages its own asyncpg pool via a lifespan context manager.
Run standalone via scripts/mcp_server.py (stdio or HTTP transport).
Optionally mountable into FastAPI — see docs/mcp-integration.md.

This module belongs to the Application layer.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(mcp: FastMCP):
    """Manage database pool lifecycle for the MCP server.

    Pool is stored on mcp.state.pool and accessed by tools via ctx.state.pool.
    """
    from src.db.client import close_pool, create_pool

    logger.info("MCP server starting — creating database pool")
    pool = await create_pool()
    mcp.state.pool = pool
    yield
    logger.info("MCP server stopping — closing database pool")
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
async def search_videos(query: str, ctx: Context, limit: int = 5) -> list[dict[str, Any]]:
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
        Channel statistics dict, or a descriptive string if not tracked.
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
- **GOTCHA**: `result.output.answer` — Pydantic AI ≥1.0. If you see `result.data`, the code is wrong.
- **GOTCHA**: `run_workflow` returns `AgentResponse` (see `src/orchestration/graph.py:102-115`), not a dict. `.answer` not `.get("final_answer")`.
- **GOTCHA**: FastMCP `@mcp.tool` (no parentheses) for basic tools. Both `@mcp.tool` and `@mcp.tool()` work in FastMCP 2.x — use the no-parens form for consistency.
- **VALIDATE**: `uv run python -c "from src.mcp.server import mcp; print('name:', mcp.name)"`

---

### Task 3: CREATE `scripts/mcp_server.py`

```python
"""Start the AgentForge MCP server as a standalone process.

Supports both stdio transport (for local MCP clients like Claude Desktop)
and HTTP transport (for remote clients).

Usage:
    # stdio — for Claude Desktop and local MCP clients (default):
    uv run python scripts/mcp_server.py

    # HTTP — for remote clients and browser-based MCP clients:
    uv run python scripts/mcp_server.py --transport http

Claude Desktop configuration (~/.config/claude/claude_desktop_config.json
or %APPDATA%/Claude/claude_desktop_config.json on Windows):

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
    """Parse transport args and start the MCP server."""
    parser = argparse.ArgumentParser(description="Start the AgentForge MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=None,
        help="Transport protocol (default: MCP_TRANSPORT env var, falls back to stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for HTTP transport (default: MCP_PORT env var, falls back to 8001)",
    )
    args = parser.parse_args()

    from src.config import MCP_PORT, MCP_TRANSPORT
    from src.mcp.server import mcp

    transport = args.transport or MCP_TRANSPORT
    port = args.port or MCP_PORT

    if transport == "http":
        mcp.run(transport="http", port=port)
    else:
        mcp.run()  # stdio is FastMCP's default


if __name__ == "__main__":
    main()
```
- **VALIDATE**: `uv run python scripts/mcp_server.py --help`

---

### Task 4: CREATE `tests/test_mcp_server.py`

```python
"""
MCP server tool tests.

Tests each MCP tool function directly by mocking the underlying
agent, workflow, and database calls. No real MCP transport is involved —
tools are called as plain async functions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_mock_ctx(pool):
    """Build a mock FastMCP Context with pool attached to state."""
    ctx = MagicMock()
    ctx.state = MagicMock()
    ctx.state.pool = pool
    return ctx


# ---------------------------------------------------------------------------
# ask_agent
# ---------------------------------------------------------------------------


async def test_ask_agent_returns_answer_string(mock_pool):
    """ask_agent calls agent.run() and returns result.output.answer."""
    from src.agent.models import AgentResponse, Source

    mock_output = AgentResponse(
        answer="The latest video is about Python.",
        sources=[Source(title="Python Tutorial", video_id="abc", url="https://yt.be/abc")],
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


async def test_ask_agent_uses_pool_from_context(mock_pool):
    """ask_agent injects pool from ctx.state.pool as agent deps."""
    mock_result = MagicMock()
    mock_result.output = MagicMock()
    mock_result.output.answer = "answer"

    ctx = _make_mock_ctx(mock_pool)

    with patch("src.mcp.server.agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_result)

        from src.mcp.server import ask_agent

        await ask_agent("test question", ctx)
        mock_agent.run.assert_called_once_with("test question", deps=mock_pool)


# ---------------------------------------------------------------------------
# search_videos
# ---------------------------------------------------------------------------


async def test_search_videos_returns_list_of_dicts(mock_pool):
    """search_videos returns serialised VideoSummary dicts."""
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

    with patch(
        "src.mcp.server.db_search_videos", AsyncMock(return_value=mock_videos)
    ):
        from src.mcp.server import search_videos

        result = await search_videos("python", ctx, limit=5)

    assert len(result) == 1
    assert result[0]["video_id"] == "vid1"
    assert result[0]["title"] == "Python Tutorial"


async def test_search_videos_caps_limit_at_20(mock_pool):
    """search_videos enforces a maximum limit of 20."""
    ctx = _make_mock_ctx(mock_pool)

    with patch(
        "src.mcp.server.db_search_videos", AsyncMock(return_value=[])
    ) as mock_search:
        from src.mcp.server import search_videos

        await search_videos("query", ctx, limit=100)
        call_kwargs = mock_search.call_args
        # Third positional arg (or 'limit' kwarg) should be capped at 20
        called_limit = call_kwargs[0][2] if call_kwargs[0] else call_kwargs[1].get("limit")
        assert called_limit == 20


# ---------------------------------------------------------------------------
# get_channel_summary
# ---------------------------------------------------------------------------


async def test_get_channel_summary_returns_stats_dict(mock_pool):
    """get_channel_summary returns channel stats as a serialisable dict."""
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


async def test_get_channel_summary_returns_string_for_unknown_channel(mock_pool):
    """get_channel_summary returns a descriptive string for unknown channel_id."""
    ctx = _make_mock_ctx(mock_pool)

    with patch("src.mcp.server.get_channel_stats", AsyncMock(return_value=None)):
        from src.mcp.server import get_channel_summary

        result = await get_channel_summary("UCunknown", ctx)

    assert isinstance(result, str)
    assert "UCunknown" in result


# ---------------------------------------------------------------------------
# run_research_workflow
# ---------------------------------------------------------------------------


async def test_run_research_workflow_returns_answer_string(mock_pool):
    """run_research_workflow calls run_workflow and returns AgentResponse.answer."""
    from src.agent.models import AgentResponse

    mock_response = AgentResponse(
        answer="Research complete.",
        sources=[],
        confidence=0.7,
    )
    ctx = _make_mock_ctx(mock_pool)

    with patch(
        "src.mcp.server.run_workflow", AsyncMock(return_value=mock_response)
    ):
        from src.mcp.server import run_research_workflow

        result = await run_research_workflow("Research AI trends", ctx)

    assert result == "Research complete."


async def test_run_research_workflow_passes_pool_to_run_workflow(mock_pool):
    """run_research_workflow injects pool into run_workflow correctly."""
    from src.agent.models import AgentResponse

    ctx = _make_mock_ctx(mock_pool)

    with patch(
        "src.mcp.server.run_workflow",
        AsyncMock(return_value=AgentResponse(answer="x", sources=[], confidence=0.5)),
    ) as mock_wf:
        from src.mcp.server import run_research_workflow

        await run_research_workflow("query", ctx)
        mock_wf.assert_called_once_with("query", mock_pool)


# ---------------------------------------------------------------------------
# Server smoke test
# ---------------------------------------------------------------------------


def test_mcp_server_module_has_correct_name():
    """The mcp module-level server instance has name 'AgentForge'."""
    from src.mcp.server import mcp

    assert mcp.name == "AgentForge"
```
- **GOTCHA**: The `db_search_videos` alias in `src/mcp/server.py` is imported as `from src.db.queries import search_videos as db_search_videos` — the patch target is `src.mcp.server.db_search_videos`.
- **GOTCHA**: `get_channel_stats` is imported inside the tool function — the patch target is `src.mcp.server.get_channel_stats`.
- **VALIDATE**: `uv run pytest tests/test_mcp_server.py -v --tb=short`

---

## VALIDATION COMMANDS

```bash
# Level 1 — style
uv run ruff check src/mcp/ scripts/mcp_server.py
uv run ruff format --check src/mcp/ scripts/mcp_server.py

# Level 2 — new tests only
uv run pytest tests/test_mcp_server.py -v --tb=short

# Level 3 — full regression (must include Run 1 tests)
uv run pytest tests/ -v --tb=short

# Level 4 — smoke
uv run python -c "from src.mcp.server import mcp; print('MCP server ok, name:', mcp.name)"
uv run python scripts/mcp_server.py --help
```

## ACCEPTANCE CRITERIA

- [ ] `src/mcp/server.py` defines `mcp` with exactly 4 tools: `ask_agent`, `search_videos`, `get_channel_summary`, `run_research_workflow`
- [ ] `mcp.name == "AgentForge"`
- [ ] All tools use `result.output.answer` (not `result.data`)
- [ ] `run_research_workflow` returns `result.answer` from `AgentResponse`
- [ ] `scripts/mcp_server.py --help` exits 0
- [ ] `tests/test_mcp_server.py` all pass
- [ ] `uv run pytest tests/ -v` all pass (zero regressions from Run 1)
- [ ] `uv run ruff check .` zero errors
