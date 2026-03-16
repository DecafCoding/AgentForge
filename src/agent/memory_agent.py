"""
Memory-aware agent — reference implementation.

Demonstrates how agent design changes with long-term memory: the system
prompt becomes dynamic (injected with relevant memories from previous
sessions), and each interaction is stored for future retrieval. Reuses
the existing tools and AgentResponse model for consistency with Pattern 1.

The agent is created fresh per-call because the system prompt varies
with the user's memory context. This is intentional and differs from
Pattern 1/2 where agents are module-level singletons.

This module belongs to the Agent layer and must not import apscheduler,
httpx, or any collector dependency.
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
from src.memory.helpers import get_relevant_context, store_interaction
from src.memory.store import BaseMemoryStore
from src.observability.tracing import get_client as get_langfuse

logger = logging.getLogger(__name__)

_BASE_SYSTEM_PROMPT = (
    "You are a YouTube content research assistant with memory. "
    "You remember previous conversations and can reference them.\n\n"
    "Guidelines:\n"
    "- Use your tools to look up data before answering. "
    "Do not guess or make up information.\n"
    "- Cite every video you reference in the sources field.\n"
    "- If the database has no relevant data, say so clearly.\n"
    "- Use the memory context below (if present) to provide "
    "continuity across sessions.\n"
    "- Set confidence to reflect how well the data supports your answer."
)

_TOOLS = [query_recent_videos, search_videos_by_query, get_channel_statistics]
try:
    from src.agent.tools import web_search

    _TOOLS.append(web_search)
except ImportError:
    pass


async def run_memory_agent(
    question: str,
    user_id: str,
    pool: Pool,
    memory_store: BaseMemoryStore,
) -> AgentResponse:
    """Run a memory-aware agent that injects context from previous sessions.

    Creates a parent Langfuse trace spanning the full interaction. Memory
    retrieval and storage are logged as metadata in the trace. The agent
    is created fresh per-call because the system prompt is dynamic.

    Args:
        question: The user's natural-language question.
        user_id: User identifier for scoping memory context.
        pool: asyncpg connection pool for database tools.
        memory_store: Memory store for retrieving and storing memories.

    Returns:
        Structured AgentResponse with answer, sources, and confidence.
    """
    # 1. Retrieve relevant memories
    memory_context = await get_relevant_context(memory_store, question, user_id)

    # 2. Build dynamic system prompt
    if memory_context:
        system_prompt = f"{_BASE_SYSTEM_PROMPT}\n\n{memory_context}"
    else:
        system_prompt = _BASE_SYSTEM_PROMPT

    # 3. Create agent with memory-augmented prompt
    agent: Agent[Pool, AgentResponse] = Agent(
        model=get_model_string(),
        deps_type=Pool,
        output_type=AgentResponse,
        defer_model_check=True,
        system_prompt=system_prompt,
        tools=_TOOLS,
    )

    # 4. Run with Langfuse tracing
    lf = get_langfuse()

    if lf is None:
        result = await agent.run(question, deps=pool)
        await store_interaction(memory_store, question, result.output.answer, user_id)
        return result.output

    trace = lf.trace(
        name="memory_agent_run",
        input={"question": question, "user_id": user_id},
        metadata={
            "provider": MODEL_PROVIDER,
            "model": MODEL_NAME,
            "memory_context_length": len(memory_context),
            "has_memory": bool(memory_context),
        },
    )
    generation = trace.generation(
        name="memory_aware_agent",
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

        # 5. Store this interaction (fire-and-forget — don't block on failure)
        await store_interaction(memory_store, question, result.output.answer, user_id)

        logger.info(
            "Memory agent run complete",
            extra={
                "user_id": user_id,
                "tokens_total": usage.total_tokens,
                "has_memory": bool(memory_context),
                "confidence": result.output.confidence,
            },
        )
        return result.output

    except Exception as exc:
        generation.end(level="ERROR", status_message=str(exc))
        trace.update(level="ERROR", status_message=str(exc))
        logger.error("Memory agent run failed", extra={"error": str(exc)})
        raise

    finally:
        lf.flush()
