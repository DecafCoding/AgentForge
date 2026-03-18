"""
API route definitions.

Defines all HTTP endpoints for the AgentForge application. Routes are
thin — they validate input, delegate to the agent, and shape the response.
No business logic lives here. This module belongs to the Application Layer.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from src.agent.agent import run_agent
from src.agent.memory_agent import run_memory_agent
from src.api.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    MemoryAskRequest,
    MemoryAskResponse,
    ResearchRequest,
    WorkflowResponse,
)
from src.orchestration.graph import run_workflow

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health(request: Request) -> HealthResponse:
    """Health check endpoint for Docker and load balancers."""
    pool = getattr(request.app.state, "pool", None)
    db_status = "unknown"

    if pool is not None:
        try:
            await pool.fetchval("SELECT 1")
            db_status = "healthy"
        except Exception:
            db_status = "unhealthy"

    return HealthResponse(
        status="healthy" if db_status != "unhealthy" else "degraded",
        database=db_status,
        version="0.6.0",
    )


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
        raise HTTPException(
            status_code=500, detail="Agent failed to process the request."
        ) from exc

    return AskResponse(answer=response.answer, sources=response.sources)


@router.post("/api/research", response_model=WorkflowResponse, tags=["orchestration"])
async def research(request: Request, body: ResearchRequest) -> WorkflowResponse:
    """Submit a query to the multi-agent research workflow.

    Runs a three-node LangGraph pipeline (research → analysis → synthesis)
    and returns a structured, source-cited answer. The full workflow is
    traced as a single Langfuse trace with per-node child spans.

    Args:
        request: FastAPI request object (used to access app.state.pool).
        body: Validated request body containing the research query.

    Returns:
        Structured response with the synthesised answer and cited sources.
    """
    pool = request.app.state.pool
    logger.info("Received research query", extra={"query": body.query[:120]})

    try:
        response = await run_workflow(body.query, pool)
    except Exception as exc:
        logger.error("Workflow failed to process query", extra={"error": str(exc)})
        raise HTTPException(
            status_code=500, detail="Workflow failed to process the request."
        ) from exc

    return WorkflowResponse(
        answer=response.answer,
        sources=response.sources,
        confidence=response.confidence,
    )


@router.post("/api/ask/memory", response_model=MemoryAskResponse, tags=["agent"])
async def ask_with_memory(
    request: Request, body: MemoryAskRequest
) -> MemoryAskResponse:
    """Submit a question to the memory-aware agent.

    Runs a Pydantic AI agent with memory context injected from previous
    sessions. Requires MEMORY_ENABLED=true. The interaction is stored
    as a new memory for future retrieval.

    Args:
        request: FastAPI request object (used to access app.state).
        body: Validated request body with question and user_id.

    Returns:
        Structured response with answer, sources, and confidence.
    """
    pool = request.app.state.pool
    memory_store = getattr(request.app.state, "memory", None)

    if memory_store is None:
        raise HTTPException(
            status_code=503,
            detail="Memory is not enabled. Set MEMORY_ENABLED=true to use this endpoint.",
        )

    logger.info(
        "Received memory-aware question",
        extra={"question": body.question[:120], "user_id": body.user_id},
    )

    try:
        response = await run_memory_agent(
            body.question, body.user_id, pool, memory_store
        )
    except Exception as exc:
        logger.error("Memory agent failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=500,
            detail="Memory agent failed to process the request.",
        ) from exc

    return MemoryAskResponse(
        answer=response.answer,
        sources=response.sources,
        confidence=response.confidence,
    )
