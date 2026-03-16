"""
FastAPI application factory and lifespan hook.

Creates the FastAPI application, wires up the database pool and APScheduler
via the lifespan context manager, and registers all routes. The module-level
``app`` instance is what Uvicorn serves. This module belongs to the
Application Layer.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import router
from src.cache.client import close_cache_pool, create_cache_pool
from src.collector.scheduler import shutdown_scheduler, start_scheduler
from src.config import validate_provider_config
from src.db.client import close_pool, create_pool
from src.memory.client import create_memory_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown of shared application resources.

    Startup order:
      1. Create asyncpg connection pool
      2. Start APScheduler with the pool injected into collector jobs
      3. Initialise Mem0 memory client (if enabled)
      4. Create Redis cache pool (if enabled)

    Shutdown order (reverse):
      1. Close cache pool
      2. Release memory store reference
      3. Stop APScheduler gracefully
      4. Close the connection pool
    """
    logger.info("Starting up AgentForge")
    validate_provider_config()

    app.state.pool = await create_pool()
    await start_scheduler(app.state.pool)

    try:
        memory_client = await create_memory_client()
        if memory_client is not None:
            from src.memory.store import Mem0MemoryStore

            app.state.memory = Mem0MemoryStore(memory_client)
            logger.info("Memory store initialised")
        else:
            app.state.memory = None
    except Exception as exc:
        logger.error(
            "Memory initialisation failed — continuing without memory",
            extra={"error": str(exc)},
        )
        app.state.memory = None

    try:
        app.state.cache = await create_cache_pool()
    except Exception as exc:
        logger.error(
            "Cache initialisation failed — continuing without cache",
            extra={"error": str(exc)},
        )
        app.state.cache = None

    logger.info("AgentForge ready")
    yield

    logger.info("Shutting down AgentForge")
    await close_cache_pool(getattr(app.state, "cache", None))
    app.state.memory = None
    await shutdown_scheduler()
    await close_pool(app.state.pool)
    logger.info("AgentForge stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A fully configured FastAPI instance ready to be served by Uvicorn.
    """
    application = FastAPI(
        title="AgentForge",
        description=(
            "An opinionated, open-source, code-first Python stack for building "
            "AI agents. Pre-integrated with Postgres, Pydantic AI, APScheduler, "
            "and Langfuse."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    application.include_router(router)

    return application


# Module-level app instance for Uvicorn:
#   uvicorn src.api.main:app --host 0.0.0.0 --port 8000
app = create_app()
