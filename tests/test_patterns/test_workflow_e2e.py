"""
Multi-agent workflow end-to-end test patterns.

Reference examples for testing LangGraph workflows. Patches the compiled
graph's ainvoke() method to control state output — this tests the graph
wiring and result extraction logic without real LLM calls.

Key patterns demonstrated:
  1. Patch _graph.ainvoke to return a controlled state dict
  2. Verify run_workflow() maps state dict -> AgentResponse correctly
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
