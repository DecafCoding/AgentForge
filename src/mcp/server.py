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

from src.agent.agent import agent
from src.db.queries import get_channel_stats
from src.db.queries import search_videos as db_search_videos
from src.orchestration.graph import run_workflow

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
    pool = ctx.state.pool
    result = await agent.run(question, deps=pool)
    return result.output.answer


@mcp.tool
async def search_videos(
    query: str, ctx: Context, limit: int = 5
) -> list[dict[str, Any]]:
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
    pool = ctx.state.pool
    result = await run_workflow(query, pool)
    return result.answer
