"""
Memory store interface and Mem0 implementation.

BaseMemoryStore defines the async contract for memory backends.
Mem0MemoryStore wraps the Mem0 AsyncMemory client. All public methods
are async. This module belongs to the Memory layer.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseMemoryStore(ABC):
    """Abstract base for memory storage backends.

    Implementations wrap a specific memory provider (Mem0, etc.) and
    expose a uniform async interface for storing and retrieving memories.
    """

    @abstractmethod
    async def add(
        self, content: str, user_id: str, metadata: dict | None = None
    ) -> str:
        """Store a memory and return its ID."""
        ...

    @abstractmethod
    async def search(self, query: str, user_id: str, limit: int = 5) -> list[dict]:
        """Search memories relevant to a query for a specific user."""
        ...

    @abstractmethod
    async def get_all(self, user_id: str) -> list[dict]:
        """Return all memories for a user."""
        ...

    @abstractmethod
    async def delete(self, memory_id: str) -> None:
        """Delete a specific memory by ID."""
        ...


class Mem0MemoryStore(BaseMemoryStore):
    """Mem0-backed memory store using AsyncMemory.

    Wraps Mem0's async API and handles response parsing. Mem0's add()
    returns a dict with a results list; search() returns a list of dicts
    with 'memory' and 'score' keys.
    """

    def __init__(self, client: object) -> None:
        self._client = client

    async def add(
        self, content: str, user_id: str, metadata: dict | None = None
    ) -> str:
        """Store a memory via Mem0 and return its ID."""
        result = await self._client.add(
            content, user_id=user_id, metadata=metadata or {}
        )
        logger.debug("Memory stored", extra={"user_id": user_id, "result": result})
        # Mem0 returns {"results": [{"id": "...", "memory": "...", ...}]}
        results = result.get("results", [])
        if results:
            return results[0].get("id", "")
        return ""

    async def search(self, query: str, user_id: str, limit: int = 5) -> list[dict]:
        """Search for relevant memories via Mem0."""
        results = await self._client.search(query, user_id=user_id, limit=limit)
        logger.debug(
            "Memory search complete",
            extra={"user_id": user_id, "results": len(results)},
        )
        return results

    async def get_all(self, user_id: str) -> list[dict]:
        """Return all memories for a user via Mem0."""
        results = await self._client.get_all(user_id=user_id)
        return results

    async def delete(self, memory_id: str) -> None:
        """Delete a memory by ID via Mem0."""
        await self._client.delete(memory_id)
        logger.debug("Memory deleted", extra={"memory_id": memory_id})
