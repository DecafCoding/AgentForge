"""
Database connection pool management.

Creates and manages the asyncpg connection pool for the application.
This module belongs to the Data Layer and is the single point of entry
for database connectivity. The pool lifecycle is driven by the FastAPI
lifespan hook in src/api/main.py — do not create pools elsewhere.
"""

import logging

import asyncpg
from asyncpg import Pool

from src.config import DATABASE_URL

logger = logging.getLogger(__name__)


async def create_pool() -> Pool:
    """Create and return an asyncpg connection pool.

    Returns:
        A live asyncpg Pool connected to the configured DATABASE_URL.
    """
    logger.info("Creating database connection pool")
    return await asyncpg.create_pool(DATABASE_URL)


async def close_pool(pool: Pool) -> None:
    """Drain and close the asyncpg connection pool.

    Args:
        pool: The pool to close.
    """
    logger.info("Closing database connection pool")
    await pool.close()
