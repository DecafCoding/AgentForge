"""
API integration tests.

Tests the FastAPI routes end-to-end using an in-process ASGI client.
The database pool, scheduler, and agent are mocked so no external
services are required.
"""

from unittest.mock import AsyncMock, patch

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


async def test_health_returns_200(client):
    """GET /health returns 200 with healthy status."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data
    assert data["version"] == "0.6.0"


# ---------------------------------------------------------------------------
# POST /api/ask — happy path
# ---------------------------------------------------------------------------


async def test_ask_returns_answer_and_sources(client):
    """POST /api/ask returns the agent's answer and sources on success."""
    from src.agent.models import AgentResponse, Source

    mocked_response = AgentResponse(
        answer="The latest video is about Python async.",
        sources=[
            Source(
                title="Python Async Explained",
                video_id="vid001",
                url="https://www.youtube.com/watch?v=vid001",
            )
        ],
        confidence=0.95,
    )

    with patch("src.api.routes.run_agent", AsyncMock(return_value=mocked_response)):
        response = await client.post(
            "/api/ask",
            json={"question": "What is the latest video about?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "The latest video is about Python async."
    assert len(data["sources"]) == 1
    assert data["sources"][0]["video_id"] == "vid001"


async def test_ask_does_not_expose_confidence(client):
    """POST /api/ask response does not include the internal confidence field."""
    from src.agent.models import AgentResponse, Source

    mocked_response = AgentResponse(
        answer="Some answer.",
        sources=[
            Source(
                title="Video", video_id="v1", url="https://www.youtube.com/watch?v=v1"
            )
        ],
        confidence=0.5,
    )

    with patch("src.api.routes.run_agent", AsyncMock(return_value=mocked_response)):
        response = await client.post("/api/ask", json={"question": "Any question?"})

    assert response.status_code == 200
    assert "confidence" not in response.json()


# ---------------------------------------------------------------------------
# POST /api/ask — input validation
# ---------------------------------------------------------------------------


async def test_ask_rejects_empty_question(client):
    """POST /api/ask returns 422 when question is an empty string."""
    response = await client.post("/api/ask", json={"question": ""})

    assert response.status_code == 422


async def test_ask_rejects_missing_question_field(client):
    """POST /api/ask returns 422 when the question field is absent."""
    response = await client.post("/api/ask", json={})

    assert response.status_code == 422


async def test_ask_rejects_wrong_content_type(client):
    """POST /api/ask returns 422 for non-JSON bodies."""
    response = await client.post(
        "/api/ask",
        content="not json",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code in {415, 422}


# ---------------------------------------------------------------------------
# POST /api/ask — error handling
# ---------------------------------------------------------------------------


async def test_ask_returns_500_when_agent_raises(client):
    """POST /api/ask returns 500 when the agent throws an unexpected error."""
    with patch(
        "src.api.routes.run_agent",
        AsyncMock(side_effect=RuntimeError("model unavailable")),
    ):
        response = await client.post(
            "/api/ask",
            json={"question": "Will this fail?"},
        )

    assert response.status_code == 500
    assert "Agent failed" in response.json()["detail"]
