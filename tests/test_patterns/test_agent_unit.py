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
