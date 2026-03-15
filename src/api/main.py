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
from src.collector.scheduler import shutdown_scheduler, start_scheduler
from src.config import validate_provider_config
from src.db.client import close_pool, create_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup and shutdown of shared application resources.

    Startup order:
      1. Create asyncpg connection pool
      2. Start APScheduler with the pool injected into collector jobs

    Shutdown order (reverse):
      1. Stop APScheduler gracefully
      2. Close the connection pool
    """
    logger.info("Starting up AgentForge")
    validate_provider_config()

    app.state.pool = await create_pool()
    await start_scheduler(app.state.pool)

    logger.info("AgentForge ready")
    yield

    logger.info("Shutting down AgentForge")
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
