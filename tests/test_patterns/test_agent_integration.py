"""
Agent integration test patterns.

Reference examples for testing the full API stack end-to-end using an
httpx AsyncClient backed by the FastAPI ASGI app. The database pool and
LLM are mocked — no external services required.

Key patterns demonstrated:
  1. Use the shared 'client' fixture from conftest.py
  2. Patch at the route layer (src.api.routes.run_agent) not the agent layer
  3. Test both happy path and error path for each endpoint
  4. Verify response shape matches the schema

These are the concrete examples referenced in docs/testing-patterns.md.
"""

from unittest.mock import AsyncMock, patch


async def test_ask_endpoint_returns_200_with_structured_response(client):
    """POST /api/ask returns 200 and an answer + sources on success."""
    from src.agent.models import AgentResponse, Source

    mock_response = AgentResponse(
        answer="The channel has covered Python, FastAPI, and AI.",
        sources=[
            Source(
                title="Python Tutorial",
                video_id="abc123",
                url="https://youtube.com/watch?v=abc123",
            )
        ],
        confidence=0.85,
    )

    with patch("src.api.routes.run_agent", AsyncMock(return_value=mock_response)):
        response = await client.post(
            "/api/ask",
            json={"question": "What topics has this channel covered?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert "sources" in body
    assert len(body["sources"]) == 1
    assert body["sources"][0]["video_id"] == "abc123"


async def test_ask_endpoint_returns_500_when_agent_raises(client):
    """POST /api/ask returns 500 when the agent raises an exception.

    Verifies that agent errors are caught and converted to HTTP 500
    rather than crashing the server or leaking tracebacks.
    """
    with patch(
        "src.api.routes.run_agent",
        AsyncMock(side_effect=RuntimeError("model timeout")),
    ):
        response = await client.post("/api/ask", json={"question": "Test"})

    assert response.status_code == 500
    assert "detail" in response.json()


async def test_research_endpoint_returns_workflow_response(client):
    """POST /api/research returns answer, sources, and confidence."""
    from src.agent.models import AgentResponse, Source

    mock_response = AgentResponse(
        answer="Multi-agent research result.",
        sources=[Source(title="Video", video_id="xyz", url="https://yt.be/xyz")],
        confidence=0.75,
    )

    with patch("src.api.routes.run_workflow", AsyncMock(return_value=mock_response)):
        response = await client.post(
            "/api/research",
            json={"query": "Research Python trends"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Multi-agent research result."
    assert "confidence" in body


async def test_health_endpoint_returns_ok(client):
    """GET /health returns 200 with healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


async def test_ask_endpoint_rejects_empty_question(client):
    """POST /api/ask rejects requests with missing question field."""
    response = await client.post("/api/ask", json={})
    assert response.status_code == 422  # FastAPI validation error
