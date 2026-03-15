"""
Pydantic AI agent definition and traced runner.

Creates the YouTube research agent with tool registration, structured
output, and model-agnostic provider support. Also exposes ``run_agent()``,
the entry point used by the API layer — it wraps agent.run() with a
Langfuse trace so every call is observable.

This module must not import apscheduler, httpx, or any collector dependency.
"""

import logging

from asyncpg import Pool
from pydantic_ai import Agent

from src.agent.models import AgentResponse
from src.agent.tools import (
    get_channel_statistics,
    query_recent_videos,
    search_videos_by_query,
)
from src.config import MODEL_NAME, MODEL_PROVIDER, get_model_string
from src.observability.tracing import get_client as get_langfuse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent
#
# deps_type=Pool  — the asyncpg pool is injected per-request via agent.run()
# result_type=AgentResponse  — forces structured JSON output matching the schema
#
# The model string ("openai:gpt-4o", "groq:llama-3.1-70b-versatile", etc.)
# is resolved at import time from config. Pydantic AI reads the corresponding
# API key from the environment automatically (OPENAI_API_KEY, GROQ_API_KEY).
# ---------------------------------------------------------------------------

agent: Agent[Pool, AgentResponse] = Agent(
    model=get_model_string(),
    deps_type=Pool,
    output_type=AgentResponse,
    defer_model_check=True,
    system_prompt=(
        "You are a YouTube content research assistant. "
        "You have access to a database of YouTube video metadata and transcripts "
        "collected from configured channels.\n\n"
        "Guidelines:\n"
        "- Always use your tools to look up data before answering. "
        "Do not guess or make up video titles, statistics, or dates.\n"
        "- Cite every video you reference in the ``sources`` field using its "
        "exact title and video_id.\n"
        "- If the database has no relevant data, say so clearly — do not invent content.\n"
        "- Set ``confidence`` to reflect how well the available data supports your answer: "
        "1.0 for a direct data match, 0.5 for a partial match, 0.1 if you are mostly guessing."
    ),
    tools=[
        query_recent_videos,
        search_videos_by_query,
        get_channel_statistics,
    ],
)


async def run_agent(question: str, pool: Pool) -> AgentResponse:
    """Run the agent and record a Langfuse trace for the full call.

    This is the single entry point the API layer uses — it keeps tracing
    concerns out of the route handlers while respecting the layer hierarchy
    (agent may import observability; API may import agent).

    Args:
        question: The user's natural-language question.
        pool: asyncpg connection pool to inject as agent dependencies.

    Returns:
        Structured AgentResponse with answer, sources, and confidence.
    """
    lf = get_langfuse()

    if lf is None:
        # Langfuse not configured — run without tracing.
        result = await agent.run(question, deps=pool)
        return result.output

    trace = lf.trace(
        name="agent_run",
        input={"question": question},
        metadata={"provider": MODEL_PROVIDER, "model": MODEL_NAME},
    )
    generation = trace.generation(
        name="youtube_research_agent",
        model=f"{MODEL_PROVIDER}/{MODEL_NAME}",
        input=question,
    )

    try:
        result = await agent.run(question, deps=pool)
        usage = result.usage()

        generation.end(
            output=result.output.model_dump(),
            usage={
                "input": usage.request_tokens or 0,
                "output": usage.response_tokens or 0,
                "total": usage.total_tokens or 0,
                "unit": "TOKENS",
            },
        )
        trace.update(output={"answer": result.output.answer})

        logger.info(
            "Agent run complete",
            extra={
                "tokens_total": usage.total_tokens,
                "sources": len(result.output.sources),
                "confidence": result.output.confidence,
            },
        )
        return result.output

    except Exception as exc:
        generation.end(level="ERROR", status_message=str(exc))
        trace.update(level="ERROR", status_message=str(exc))
        logger.error("Agent run failed", extra={"error": str(exc)})
        raise

    finally:
        lf.flush()
