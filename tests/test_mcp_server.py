"""
MCP server tool tests.

Tests each MCP tool function directly by mocking the underlying
agent, workflow, and database calls. No real MCP transport is involved —
tools are called as plain async functions.
"""

from unittest.mock import AsyncMock, MagicMock, patch


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
        sources=[
            Source(
                title="Python Tutorial",
                video_id="abc",
                url="https://yt.be/abc",
            )
        ],
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

    with patch("src.mcp.server.db_search_videos", AsyncMock(return_value=mock_videos)):
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
        call_args = mock_search.call_args
        # Third positional arg should be capped at 20
        called_limit = call_args[0][2]
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

    with patch("src.mcp.server.run_workflow", AsyncMock(return_value=mock_response)):
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
