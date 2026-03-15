"""
Cross-agent tracing tests.

Verifies that run_workflow() creates a parent Langfuse trace, that per-node
child spans are created and ended, and that the trace is marked ERROR on
failure. All LLM and Langfuse calls are mocked — no real API calls are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.orchestration.state import WorkflowState

# ---------------------------------------------------------------------------
# run_workflow — parent trace lifecycle
# ---------------------------------------------------------------------------


async def test_run_workflow_creates_langfuse_trace_when_configured(mock_pool):
    """run_workflow() creates a parent Langfuse trace when keys are configured."""
    final_dict = {
        "final_answer": "answer",
        "final_sources": [],
        "final_confidence": 0.9,
        "steps_completed": 2,
    }

    mock_trace = MagicMock()
    mock_trace.id = "trace-123"

    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=mock_lf),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(return_value=final_dict),
        ),
    ):
        from src.orchestration.graph import run_workflow

        result = await run_workflow("test query", mock_pool)

    mock_lf.trace.assert_called_once()
    trace_call_kwargs = mock_lf.trace.call_args.kwargs
    assert trace_call_kwargs["name"] == "multi-agent-workflow"
    assert trace_call_kwargs["input"] == {"query": "test query"}
    mock_lf.flush.assert_called_once()
    assert result.answer == "answer"


async def test_run_workflow_flushes_langfuse_even_on_success(mock_pool):
    """run_workflow() always flushes Langfuse in the finally block."""
    final_dict = {"final_answer": "ok", "final_sources": [], "final_confidence": 0.8}

    mock_lf = MagicMock()
    mock_lf.trace.return_value = MagicMock(id="t1")

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=mock_lf),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(return_value=final_dict),
        ),
    ):
        from src.orchestration.graph import run_workflow

        await run_workflow("q", mock_pool)

    mock_lf.flush.assert_called_once()


async def test_run_workflow_marks_trace_error_and_flushes_on_failure(mock_pool):
    """run_workflow() marks trace as ERROR and still flushes when graph raises."""
    mock_trace = MagicMock()
    mock_trace.id = "trace-err"

    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=mock_lf),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(side_effect=RuntimeError("graph failure")),
        ),
        pytest.raises(RuntimeError),
    ):
        from src.orchestration.graph import run_workflow

        await run_workflow("q", mock_pool)

    mock_trace.update.assert_called_once()
    update_kwargs = mock_trace.update.call_args.kwargs
    assert update_kwargs.get("level") == "ERROR"
    mock_lf.flush.assert_called_once()


async def test_run_workflow_passes_trace_id_through_state(mock_pool):
    """run_workflow() sets trace_id in WorkflowState so nodes can create child spans."""
    captured_states = []

    mock_trace = MagicMock()
    mock_trace.id = "trace-xyz"

    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    async def capture(state):
        captured_states.append(state)
        return {"final_answer": "ok", "final_sources": [], "final_confidence": 0.9}

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=mock_lf),
        patch("src.orchestration.graph._graph.ainvoke", side_effect=capture),
    ):
        from src.orchestration.graph import run_workflow

        await run_workflow("q", mock_pool)

    assert captured_states[0].trace_id == "trace-xyz"


# ---------------------------------------------------------------------------
# research_node — child span creation
# ---------------------------------------------------------------------------


async def test_research_node_creates_child_span_when_trace_id_set(mock_pool):
    """research_node creates a named child span when trace_id is in state."""
    from src.agent.research_agent import ResearchAgentOutput

    mock_result = MagicMock()
    mock_result.output = ResearchAgentOutput(
        findings=["fact 1"], sources=["vid1"], confidence=0.9
    )
    mock_result.usage.return_value = MagicMock(
        request_tokens=50, response_tokens=20, total_tokens=70
    )

    mock_span = MagicMock()
    mock_lf = MagicMock()
    mock_lf.span.return_value = mock_span

    state = WorkflowState(query="test query", pool=mock_pool, trace_id="trace-abc")

    with (
        patch("src.orchestration.nodes.get_langfuse", return_value=mock_lf),
        patch(
            "src.orchestration.nodes.research_agent.run",
            AsyncMock(return_value=mock_result),
        ),
    ):
        from src.orchestration.nodes import research_node

        updates = await research_node(state)

    mock_lf.span.assert_called_once_with(
        name="research_node",
        trace_id="trace-abc",
        input={"query": "test query"},
    )
    mock_span.end.assert_called_once()
    assert updates["research_output"].findings == ["fact 1"]
    assert updates["steps_completed"] == 1


async def test_research_node_skips_span_when_trace_id_is_none(mock_pool):
    """research_node does not create a span when no trace_id is set."""
    from src.agent.research_agent import ResearchAgentOutput

    mock_result = MagicMock()
    mock_result.output = ResearchAgentOutput(findings=[], sources=[], confidence=0.1)
    mock_result.usage.return_value = MagicMock(
        request_tokens=10, response_tokens=5, total_tokens=15
    )

    mock_lf = MagicMock()
    state = WorkflowState(query="q", pool=mock_pool, trace_id=None)

    with (
        patch("src.orchestration.nodes.get_langfuse", return_value=mock_lf),
        patch(
            "src.orchestration.nodes.research_agent.run",
            AsyncMock(return_value=mock_result),
        ),
    ):
        from src.orchestration.nodes import research_node

        await research_node(state)

    mock_lf.span.assert_not_called()


async def test_research_node_ends_span_with_error_on_failure(mock_pool):
    """research_node ends the span with ERROR level when the agent raises."""
    mock_span = MagicMock()
    mock_lf = MagicMock()
    mock_lf.span.return_value = mock_span

    state = WorkflowState(query="q", pool=mock_pool, trace_id="trace-fail")

    with (
        patch("src.orchestration.nodes.get_langfuse", return_value=mock_lf),
        patch(
            "src.orchestration.nodes.research_agent.run",
            AsyncMock(side_effect=RuntimeError("agent error")),
        ),
        pytest.raises(RuntimeError),
    ):
        from src.orchestration.nodes import research_node

        await research_node(state)

    mock_span.end.assert_called_once()
    call_kwargs = mock_span.end.call_args.kwargs
    assert call_kwargs.get("level") == "ERROR"
