"""
Orchestration module tests.

Covers WorkflowState model validation, all branches of should_continue
conditional routing, and the run_workflow() runner (success, early
termination, exception propagation). No real LLM calls or database
connections are made — agents and the pool are mocked throughout.
"""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.orchestration.state import AnalysisOutput, ResearchOutput, WorkflowState

# ---------------------------------------------------------------------------
# WorkflowState validation
# ---------------------------------------------------------------------------


def test_workflow_state_initialises_with_defaults(mock_pool):
    """WorkflowState initialises with sensible defaults for all optional fields."""
    state = WorkflowState(query="test query", pool=mock_pool)
    assert state.query == "test query"
    assert state.steps_completed == 0
    assert state.max_retries == 3
    assert state.research_output is None
    assert state.analysis_output is None
    assert state.trace_id is None


def test_workflow_state_pool_excluded_from_serialisation(mock_pool):
    """Pool must not appear in model_dump() — it is a runtime dependency."""
    state = WorkflowState(query="q", pool=mock_pool)
    dumped = state.model_dump()
    assert "pool" not in dumped


def test_research_output_rejects_confidence_above_one():
    """ResearchOutput must reject confidence values greater than 1.0."""
    with pytest.raises(ValidationError):
        ResearchOutput(findings=[], sources=[], confidence=1.5)


def test_research_output_rejects_confidence_below_zero():
    """ResearchOutput must reject negative confidence values."""
    with pytest.raises(ValidationError):
        ResearchOutput(findings=[], sources=[], confidence=-0.1)


def test_analysis_output_rejects_quality_score_out_of_range():
    """AnalysisOutput must reject quality_score outside 0-1."""
    with pytest.raises(ValidationError):
        AnalysisOutput(assessment="ok", gaps=[], quality_score=1.1, confidence=0.9)


def test_analysis_output_rejects_confidence_out_of_range():
    """AnalysisOutput must reject confidence outside 0-1."""
    with pytest.raises(ValidationError):
        AnalysisOutput(assessment="ok", gaps=[], quality_score=0.5, confidence=-0.1)


# ---------------------------------------------------------------------------
# should_continue — all routing branches
# ---------------------------------------------------------------------------


def test_should_continue_returns_continue_when_quality_is_high(mock_pool):
    """should_continue returns 'continue' when quality_score >= 0.3."""
    from src.orchestration.nodes import should_continue

    state = WorkflowState(
        query="q",
        pool=mock_pool,
        analysis_output=AnalysisOutput(
            assessment="good", gaps=[], quality_score=0.8, confidence=0.9
        ),
        steps_completed=1,
    )
    assert should_continue(state) == "continue"


def test_should_continue_returns_continue_at_exact_threshold(mock_pool):
    """should_continue returns 'continue' when quality_score is exactly 0.3."""
    from src.orchestration.nodes import should_continue

    state = WorkflowState(
        query="q",
        pool=mock_pool,
        analysis_output=AnalysisOutput(
            assessment="borderline", gaps=[], quality_score=0.3, confidence=0.7
        ),
        steps_completed=1,
    )
    assert should_continue(state) == "continue"


def test_should_continue_returns_retry_when_quality_low_and_retries_available(
    mock_pool,
):
    """should_continue returns 'retry' when quality < 0.3 and steps < max_retries."""
    from src.orchestration.nodes import should_continue

    state = WorkflowState(
        query="q",
        pool=mock_pool,
        analysis_output=AnalysisOutput(
            assessment="poor", gaps=["x"], quality_score=0.2, confidence=0.5
        ),
        steps_completed=1,
        max_retries=3,
    )
    assert should_continue(state) == "retry"


def test_should_continue_returns_end_when_quality_low_and_max_retries_reached(
    mock_pool,
):
    """should_continue returns 'end' when quality < 0.3 and steps >= max_retries."""
    from src.orchestration.nodes import should_continue

    state = WorkflowState(
        query="q",
        pool=mock_pool,
        analysis_output=AnalysisOutput(
            assessment="poor", gaps=["x"], quality_score=0.2, confidence=0.5
        ),
        steps_completed=3,
        max_retries=3,
    )
    assert should_continue(state) == "end"


def test_should_continue_defaults_to_continue_when_no_analysis(mock_pool):
    """should_continue returns 'continue' when analysis_output is None."""
    from src.orchestration.nodes import should_continue

    state = WorkflowState(query="q", pool=mock_pool)
    assert should_continue(state) == "continue"


# ---------------------------------------------------------------------------
# run_workflow — no tracing
# ---------------------------------------------------------------------------


async def test_run_workflow_returns_agent_response_on_success(mock_pool):
    """run_workflow() returns an AgentResponse when the graph completes."""
    final_dict = {
        "final_answer": "The answer is 42.",
        "final_sources": ["vid1", "vid2"],
        "final_confidence": 0.85,
        "steps_completed": 2,
    }

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=None),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(return_value=final_dict),
        ),
    ):
        from src.orchestration.graph import run_workflow

        result = await run_workflow("test query", mock_pool)

    assert result.answer == "The answer is 42."
    assert result.confidence == 0.85
    assert len(result.sources) == 2
    assert result.sources[0].video_id == "vid1"


async def test_run_workflow_returns_default_response_on_early_termination(mock_pool):
    """run_workflow() returns a low-confidence default when workflow ends early."""
    early_termination = {
        "final_answer": None,
        "final_sources": None,
        "final_confidence": None,
        "steps_completed": 3,
    }

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=None),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(return_value=early_termination),
        ),
    ):
        from src.orchestration.graph import run_workflow

        result = await run_workflow("q", mock_pool)

    assert result.confidence == 0.1
    assert result.sources == []
    assert "sufficient" in result.answer.lower()


async def test_run_workflow_propagates_graph_exception(mock_pool):
    """run_workflow() re-raises exceptions from graph.ainvoke()."""
    with (
        patch("src.orchestration.graph.get_langfuse", return_value=None),
        patch(
            "src.orchestration.graph._graph.ainvoke",
            AsyncMock(side_effect=RuntimeError("graph error")),
        ),
        pytest.raises(RuntimeError, match="graph error"),
    ):
        from src.orchestration.graph import run_workflow

        await run_workflow("q", mock_pool)


async def test_run_workflow_injects_pool_into_initial_state(mock_pool):
    """run_workflow() passes the pool inside the WorkflowState to the graph."""
    captured_states = []

    async def capture_state(state):
        captured_states.append(state)
        return {"final_answer": "ok", "final_sources": [], "final_confidence": 0.9}

    with (
        patch("src.orchestration.graph.get_langfuse", return_value=None),
        patch("src.orchestration.graph._graph.ainvoke", side_effect=capture_state),
    ):
        from src.orchestration.graph import run_workflow

        await run_workflow("q", mock_pool)

    assert len(captured_states) == 1
    assert captured_states[0].pool is mock_pool
    assert captured_states[0].query == "q"
