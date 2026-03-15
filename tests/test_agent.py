"""
Agent module tests.

Tests agent behaviour using mocked LLM responses. No real API calls are
made. Covers structured output validation, the traced runner, and tool
delegation to the database layer.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_response(answer: str = "Test answer", confidence: float = 0.9):
    from src.agent.models import AgentResponse, Source

    return AgentResponse(
        answer=answer,
        sources=[
            Source(
                title="Test Video",
                video_id="abc123",
                url="https://www.youtube.com/watch?v=abc123",
            )
        ],
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# AgentResponse model validation
# ---------------------------------------------------------------------------


def test_agent_response_rejects_confidence_above_one():
    """AgentResponse must reject confidence values greater than 1.0."""
    from src.agent.models import AgentResponse

    with pytest.raises(ValidationError):
        AgentResponse(answer="test", sources=[], confidence=1.5)


def test_agent_response_rejects_confidence_below_zero():
    """AgentResponse must reject negative confidence values."""
    from src.agent.models import AgentResponse

    with pytest.raises(ValidationError):
        AgentResponse(answer="test", sources=[], confidence=-0.1)


def test_agent_response_accepts_boundary_values():
    """AgentResponse accepts exactly 0.0 and 1.0 as confidence."""
    from src.agent.models import AgentResponse

    low = AgentResponse(answer="low", sources=[], confidence=0.0)
    high = AgentResponse(answer="high", sources=[], confidence=1.0)
    assert low.confidence == 0.0
    assert high.confidence == 1.0


# ---------------------------------------------------------------------------
# run_agent — no tracing
# ---------------------------------------------------------------------------


async def test_run_agent_returns_agent_response_when_tracing_disabled(mock_pool):
    """run_agent() returns AgentResponse when Langfuse is not configured."""
    expected = _make_agent_response()

    mock_result = MagicMock()
    mock_result.data = expected

    with (
        patch("src.agent.agent.get_langfuse", return_value=None),
        patch("src.agent.agent.agent.run", AsyncMock(return_value=mock_result)),
    ):
        from src.agent.agent import run_agent

        result = await run_agent("what are the latest videos?", mock_pool)

    assert result.answer == "Test answer"
    assert result.confidence == 0.9
    assert len(result.sources) == 1


async def test_run_agent_passes_pool_as_deps(mock_pool):
    """run_agent() injects the pool as the agent dependency."""
    expected = _make_agent_response()

    mock_result = MagicMock()
    mock_result.data = expected

    with (
        patch("src.agent.agent.get_langfuse", return_value=None),
        patch("src.agent.agent.agent.run", AsyncMock(return_value=mock_result)) as mock_run,
    ):
        from src.agent.agent import run_agent

        await run_agent("test question", mock_pool)
        mock_run.assert_called_once_with("test question", deps=mock_pool)


# ---------------------------------------------------------------------------
# run_agent — with tracing
# ---------------------------------------------------------------------------


async def test_run_agent_creates_langfuse_trace_on_success(mock_pool):
    """run_agent() creates a trace and generation in Langfuse on success."""
    expected = _make_agent_response()

    mock_result = MagicMock()
    mock_result.data = expected
    mock_result.usage.return_value = MagicMock(
        request_tokens=100,
        response_tokens=50,
        total_tokens=150,
    )

    mock_generation = MagicMock()
    mock_trace = MagicMock()
    mock_trace.generation.return_value = mock_generation

    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with (
        patch("src.agent.agent.get_langfuse", return_value=mock_lf),
        patch("src.agent.agent.agent.run", AsyncMock(return_value=mock_result)),
    ):
        from src.agent.agent import run_agent

        result = await run_agent("traced question", mock_pool)

    assert result.answer == "Test answer"
    mock_lf.trace.assert_called_once()
    mock_trace.generation.assert_called_once()
    mock_generation.end.assert_called_once()
    mock_lf.flush.assert_called_once()


async def test_run_agent_ends_trace_with_error_on_failure(mock_pool):
    """run_agent() marks the Langfuse trace as ERROR when the agent raises."""
    mock_generation = MagicMock()
    mock_trace = MagicMock()
    mock_trace.generation.return_value = mock_generation

    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with (
        patch("src.agent.agent.get_langfuse", return_value=mock_lf),
        patch(
            "src.agent.agent.agent.run",
            AsyncMock(side_effect=RuntimeError("model error")),
        ),
        pytest.raises(RuntimeError, match="model error"),
    ):
        from src.agent.agent import run_agent

        await run_agent("failing question", mock_pool)

    mock_generation.end.assert_called_once()
    call_kwargs = mock_generation.end.call_args.kwargs
    assert call_kwargs.get("level") == "ERROR"
    # flush still called in finally
    mock_lf.flush.assert_called_once()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


async def test_query_recent_videos_delegates_to_db(mock_pool):
    """query_recent_videos tool calls get_videos with the injected pool."""
    from pydantic_ai import RunContext

    from src.agent.tools import query_recent_videos

    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_pool

    with patch("src.agent.tools.get_videos", AsyncMock(return_value=[])) as mock_get:
        result = await query_recent_videos(ctx, channel_id="UCtest", limit=5)
        mock_get.assert_called_once_with(mock_pool, "UCtest", 5)

    assert result == []


async def test_search_videos_by_query_delegates_to_db(mock_pool):
    """search_videos_by_query tool calls search_videos with the injected pool."""
    from pydantic_ai import RunContext

    from src.agent.tools import search_videos_by_query

    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_pool

    with patch("src.agent.tools.search_videos", AsyncMock(return_value=[])) as mock_search:
        result = await search_videos_by_query(ctx, query="python tutorial")
        mock_search.assert_called_once_with(mock_pool, "python tutorial", 10)

    assert result == []
