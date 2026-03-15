"""
Base collector interface.

Defines the contract that all collectors must implement. Collectors are
deterministic data-fetching components that run on a schedule and write
to Postgres. This module must never import pydantic_ai, langfuse, or any
LLM-related dependency.
"""

from abc import ABC, abstractmethod

from asyncpg import Pool


class BaseCollector(ABC):
    """Abstract base for all data collectors.

    Subclasses implement ``collect()`` for their specific data source.
    The pool is injected at construction and used for all database writes
    via ``src.db.queries`` — collectors must not open their own connections.
    """

    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    @abstractmethod
    async def collect(self) -> int:
        """Run one collection cycle.

        Returns:
            The number of items upserted during this cycle.
        """
        ...
