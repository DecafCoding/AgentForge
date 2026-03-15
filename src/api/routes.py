"""
API route definitions.

Defines all HTTP endpoints for the AgentForge application. Routes are
thin — they validate input, delegate to the agent, and shape the response.
No business logic lives here. This module belongs to the Application Layer.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from src.agent.agent import run_agent
from src.api.schemas import AskRequest, AskResponse, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok")


@router.post("/api/ask", response_model=AskResponse, tags=["agent"])
async def ask(request: Request, body: AskRequest) -> AskResponse:
    """Submit a question to the YouTube research agent.

    The agent queries the collected video database, synthesises an answer,
    and returns it with cited sources. Every call is traced in Langfuse.

    Args:
        request: FastAPI request object (used to access app.state.pool).
        body: Validated request body containing the user's question.

    Returns:
        Structured response with the agent's answer and cited sources.
    """
    pool = request.app.state.pool

    logger.info("Received question", extra={"question": body.question[:120]})

    try:
        response = await run_agent(body.question, pool)
    except Exception as exc:
        logger.error("Agent failed to answer question", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Agent failed to process the request.") from exc

    return AskResponse(answer=response.answer, sources=response.sources)
