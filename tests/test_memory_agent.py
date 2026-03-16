"""
Memory-aware agent tests.

Covers run_memory_agent() with mocked LLM, memory store, and Langfuse.
Also covers the /api/ask/memory API route. No real API calls or database
connections are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.models import AgentResponse, Source

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MOCK_RESPONSE = AgentResponse(
    answer="Test answer",
    sources=[
        Source(title="Video 1", video_id="v1", url="https://youtube.com/watch?v=v1")
    ],
    confidence=0.9,
)


def _mock_agent_run_result(output: AgentResponse = _MOCK_RESPONSE):
    """Create a mock Pydantic AI agent.run() result."""
    result = MagicMock()
    result.output = output
    usage = MagicMock()
    usage.request_tokens = 100
    usage.response_tokens = 50
    usage.total_tokens = 150
    result.usage.return_value = usage
    return result


# ---------------------------------------------------------------------------
# run_memory_agent tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_memory_agent_returns_response_without_tracing(
    mock_pool, mock_memory_store
):
    """run_memory_agent returns AgentResponse when Langfuse is not configured."""
    mock_result = _mock_agent_run_result()

    with (
        patch("src.agent.memory_agent.get_langfuse", return_value=None),
        patch(
            "src.agent.memory_agent.get_relevant_context", AsyncMock(return_value="")
        ),
        patch(
            "src.agent.memory_agent.store_interaction", AsyncMock(return_value="mem-1")
        ),
        patch("src.agent.memory_agent.Agent") as MockAgent,
    ):
        MockAgent.return_value.run = AsyncMock(return_value=mock_result)

        from src.agent.memory_agent import run_memory_agent

        result = await run_memory_agent("test?", "user-1", mock_pool, mock_memory_store)

    assert result.answer == "Test answer"
    assert result.confidence == 0.9


@pytest.mark.asyncio
async def test_run_memory_agent_injects_memory_context(mock_pool, mock_memory_store):
    """run_memory_agent injects memory context into the system prompt."""
    mock_result = _mock_agent_run_result()
    memory_text = "Relevant context from previous conversations:\n- User likes Python"

    captured_kwargs = {}

    def capture_agent(**kwargs):
        captured_kwargs.update(kwargs)
        agent = MagicMock()
        agent.run = AsyncMock(return_value=mock_result)
        return agent

    with (
        patch("src.agent.memory_agent.get_langfuse", return_value=None),
        patch(
            "src.agent.memory_agent.get_relevant_context",
            AsyncMock(return_value=memory_text),
        ),
        patch(
            "src.agent.memory_agent.store_interaction", AsyncMock(return_value="mem-1")
        ),
        patch("src.agent.memory_agent.Agent", side_effect=capture_agent),
    ):
        from src.agent.memory_agent import run_memory_agent

        await run_memory_agent("test?", "user-1", mock_pool, mock_memory_store)

    assert "User likes Python" in captured_kwargs["system_prompt"]


@pytest.mark.asyncio
async def test_run_memory_agent_stores_interaction_after_response(
    mock_pool, mock_memory_store
):
    """run_memory_agent calls store_interaction with question, answer, and user_id."""
    mock_result = _mock_agent_run_result()
    mock_store_fn = AsyncMock(return_value="mem-1")

    with (
        patch("src.agent.memory_agent.get_langfuse", return_value=None),
        patch(
            "src.agent.memory_agent.get_relevant_context", AsyncMock(return_value="")
        ),
        patch("src.agent.memory_agent.store_interaction", mock_store_fn),
        patch("src.agent.memory_agent.Agent") as MockAgent,
    ):
        MockAgent.return_value.run = AsyncMock(return_value=mock_result)

        from src.agent.memory_agent import run_memory_agent

        await run_memory_agent(
            "What is Python?", "user-1", mock_pool, mock_memory_store
        )

    mock_store_fn.assert_called_once_with(
        mock_memory_store, "What is Python?", "Test answer", "user-1"
    )


@pytest.mark.asyncio
async def test_run_memory_agent_creates_langfuse_trace_with_memory_metadata(
    mock_pool, mock_memory_store
):
    """run_memory_agent logs memory metadata in the Langfuse trace."""
    mock_result = _mock_agent_run_result()
    memory_text = "Some memory context"

    mock_lf = MagicMock()
    mock_trace = MagicMock()
    mock_generation = MagicMock()
    mock_lf.trace.return_value = mock_trace
    mock_trace.generation.return_value = mock_generation

    with (
        patch("src.agent.memory_agent.get_langfuse", return_value=mock_lf),
        patch(
            "src.agent.memory_agent.get_relevant_context",
            AsyncMock(return_value=memory_text),
        ),
        patch(
            "src.agent.memory_agent.store_interaction", AsyncMock(return_value="mem-1")
        ),
        patch("src.agent.memory_agent.Agent") as MockAgent,
    ):
        MockAgent.return_value.run = AsyncMock(return_value=mock_result)

        from src.agent.memory_agent import run_memory_agent

        await run_memory_agent("test?", "user-1", mock_pool, mock_memory_store)

    trace_kwargs = mock_lf.trace.call_args
    metadata = trace_kwargs.kwargs["metadata"]
    assert metadata["has_memory"] is True
    assert metadata["memory_context_length"] == len(memory_text)


@pytest.mark.asyncio
async def test_run_memory_agent_works_with_empty_memory(mock_pool, mock_memory_store):
    """run_memory_agent works normally when memory returns no context (new user)."""
    mock_result = _mock_agent_run_result()

    with (
        patch("src.agent.memory_agent.get_langfuse", return_value=None),
        patch(
            "src.agent.memory_agent.get_relevant_context", AsyncMock(return_value="")
        ),
        patch(
            "src.agent.memory_agent.store_interaction", AsyncMock(return_value="mem-1")
        ),
        patch("src.agent.memory_agent.Agent") as MockAgent,
    ):
        MockAgent.return_value.run = AsyncMock(return_value=mock_result)

        from src.agent.memory_agent import run_memory_agent

        result = await run_memory_agent("test?", "user-1", mock_pool, mock_memory_store)

    assert result.answer == "Test answer"


@pytest.mark.asyncio
async def test_run_memory_agent_propagates_agent_exception(
    mock_pool, mock_memory_store
):
    """run_memory_agent propagates exceptions from the agent."""
    mock_lf = MagicMock()
    mock_trace = MagicMock()
    mock_generation = MagicMock()
    mock_lf.trace.return_value = mock_trace
    mock_trace.generation.return_value = mock_generation

    with (
        patch("src.agent.memory_agent.get_langfuse", return_value=mock_lf),
        patch(
            "src.agent.memory_agent.get_relevant_context", AsyncMock(return_value="")
        ),
        patch("src.agent.memory_agent.store_interaction", AsyncMock()),
        patch("src.agent.memory_agent.Agent") as MockAgent,
    ):
        MockAgent.return_value.run = AsyncMock(side_effect=RuntimeError("LLM down"))

        from src.agent.memory_agent import run_memory_agent

        with pytest.raises(RuntimeError, match="LLM down"):
            await run_memory_agent("test?", "user-1", mock_pool, mock_memory_store)

    mock_generation.end.assert_called_once()
    assert mock_generation.end.call_args.kwargs["level"] == "ERROR"
    mock_lf.flush.assert_called_once()


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ask_memory_returns_503_when_memory_disabled(client):
    """POST /api/ask/memory returns 503 when app.state.memory is None."""
    response = await client.post(
        "/api/ask/memory",
        json={"question": "test", "user_id": "user-1"},
    )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_ask_memory_returns_answer_on_success(client):
    """POST /api/ask/memory returns structured response on success."""
    from src.api.main import app

    mock_store = MagicMock()
    app.state.memory = mock_store

    try:
        with patch(
            "src.api.routes.run_memory_agent",
            AsyncMock(return_value=_MOCK_RESPONSE),
        ):
            response = await client.post(
                "/api/ask/memory",
                json={"question": "What is Python?", "user_id": "user-1"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Test answer"
        assert data["confidence"] == 0.9
        assert len(data["sources"]) == 1
    finally:
        app.state.memory = None


@pytest.mark.asyncio
async def test_ask_memory_rejects_empty_question(client):
    """POST /api/ask/memory returns 422 for empty question."""
    response = await client.post(
        "/api/ask/memory",
        json={"question": "", "user_id": "user-1"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ask_memory_rejects_missing_user_id(client):
    """POST /api/ask/memory returns 422 when user_id is missing."""
    response = await client.post(
        "/api/ask/memory",
        json={"question": "test"},
    )
    assert response.status_code == 422
