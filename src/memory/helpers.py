"""
Memory retrieval and injection helpers.

Utility functions for injecting relevant memories into agent prompts and
storing interaction history. Used by memory-aware agents to bridge the
memory store and the Pydantic AI system prompt.

This module belongs to the Memory layer.
"""

import logging

from src.memory.store import BaseMemoryStore

logger = logging.getLogger(__name__)


async def get_relevant_context(
    store: BaseMemoryStore,
    query: str,
    user_id: str,
    limit: int = 5,
) -> str:
    """Retrieve relevant memories and format as context for an agent prompt.

    Args:
        store: Memory store to search.
        query: The user's current query to match against.
        user_id: User identifier for scoping memory search.
        limit: Maximum number of memories to retrieve.

    Returns:
        Formatted context string, or empty string if no relevant memories.
    """
    try:
        memories = await store.search(query, user_id=user_id, limit=limit)
    except Exception as exc:
        logger.error("Memory search failed", extra={"error": str(exc)})
        return ""

    if not memories:
        return ""

    context_parts = ["Relevant context from previous conversations:"]
    for mem in memories:
        text = mem.get("memory", "")
        if text:
            context_parts.append(f"- {text}")

    logger.info(
        "Memory context retrieved",
        extra={"user_id": user_id, "memories_found": len(memories)},
    )
    return "\n".join(context_parts)


async def store_interaction(
    store: BaseMemoryStore,
    question: str,
    answer: str,
    user_id: str,
) -> str | None:
    """Store a question/answer interaction as a memory.

    Memory storage failure is logged but does not raise — a failed memory
    write should never crash the agent response.

    Args:
        store: Memory store to write to.
        question: The user's question.
        answer: The agent's answer.
        user_id: User identifier for scoping the memory.

    Returns:
        The memory ID, or None if storage failed.
    """
    content = f"User asked: {question}\nAssistant answered: {answer}"
    try:
        memory_id = await store.add(
            content, user_id=user_id, metadata={"type": "interaction"}
        )
        logger.info(
            "Interaction stored as memory",
            extra={"user_id": user_id, "memory_id": memory_id},
        )
        return memory_id
    except Exception as exc:
        logger.error(
            "Failed to store interaction memory",
            extra={"user_id": user_id, "error": str(exc)},
        )
        return None
