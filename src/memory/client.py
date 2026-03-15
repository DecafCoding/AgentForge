"""
Mem0 client initialisation.

Creates an AsyncMemory instance configured with Postgres/pgvector as the
vector store. Uses the same Postgres instance as the main application but
with a separate collection_name to avoid table conflicts. Mem0 auto-creates
its tables on first use — no Alembic migration is needed for Mem0's storage.

This module belongs to the Memory layer. It imports from src.config only.
"""

import logging
from urllib.parse import urlparse

from src.config import (
    DATABASE_URL,
    MEMORY_ENABLED,
    MEMORY_MODEL,
    MODEL_PROVIDER,
    OPENAI_API_KEY,
)

logger = logging.getLogger(__name__)


def _parse_database_url(url: str) -> dict[str, str | int]:
    """Extract connection parameters from a postgresql:// URL.

    Mem0's pgvector config requires individual fields, not a connection string.
    """
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "user": parsed.username or "postgres",
        "password": parsed.password or "postgres",
        "dbname": parsed.path.lstrip("/") or "agentforge",
    }


async def create_memory_client() -> object | None:
    """Create and return a Mem0 AsyncMemory client, or None if disabled.

    Returns None when MEMORY_ENABLED is False or when required configuration
    (API key for the LLM provider) is missing. The caller should store the
    result in app.state and wrap it in a Mem0MemoryStore.
    """
    if not MEMORY_ENABLED:
        logger.info("Memory disabled via MEMORY_ENABLED=false")
        return None

    if MODEL_PROVIDER == "openai" and not OPENAI_API_KEY:
        logger.warning("Memory requires OPENAI_API_KEY for embeddings — disabled")
        return None

    from mem0 import AsyncMemory

    db_params = _parse_database_url(DATABASE_URL)

    config = {
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "host": db_params["host"],
                "port": db_params["port"],
                "user": db_params["user"],
                "password": db_params["password"],
                "dbname": db_params["dbname"],
                "collection_name": "agentforge_memories",
                "embedding_model_dims": 1536,
            },
        },
        "llm": {
            "provider": MODEL_PROVIDER,
            "config": {
                "model": MEMORY_MODEL,
                "api_key": OPENAI_API_KEY,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small",
                "api_key": OPENAI_API_KEY,
            },
        },
    }

    logger.info(
        "Initialising Mem0 memory client",
        extra={
            "provider": MODEL_PROVIDER,
            "model": MEMORY_MODEL,
            "db_host": db_params["host"],
            "collection": "agentforge_memories",
        },
    )

    return AsyncMemory.from_config(config)
