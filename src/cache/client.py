"""
Redis/Valkey cache client.

Provides async cache operations (get, set, delete) with automatic TTL.
The cache pool is created during FastAPI startup and stored in app.state.
Returns None for all operations when caching is disabled — callers do
not need to check CACHE_ENABLED themselves.

This module belongs to the Cache layer. It imports from src.config only.
"""

import json
import logging

import redis.asyncio as redis

from src.config import CACHE_ENABLED, REDIS_URL

logger = logging.getLogger(__name__)

# Default TTL: 1 hour. Every cached value must have a TTL.
DEFAULT_TTL_SECONDS: int = 3600


async def create_cache_pool() -> redis.Redis | None:
    """Create an async Redis connection pool.

    Returns None when caching is disabled via CACHE_ENABLED=false.
    The caller should store the result in app.state.cache.
    """
    if not CACHE_ENABLED:
        logger.info("Caching disabled via CACHE_ENABLED=false")
        return None

    try:
        pool = redis.from_url(REDIS_URL, decode_responses=True)
        # Verify connectivity
        await pool.ping()
        logger.info("Redis cache pool created", extra={"url": REDIS_URL})
        return pool
    except Exception as exc:
        logger.error(
            "Failed to connect to Redis — continuing without cache",
            extra={"error": str(exc), "url": REDIS_URL},
        )
        return None


async def close_cache_pool(pool: redis.Redis | None) -> None:
    """Close the Redis connection pool gracefully."""
    if pool is not None:
        await pool.aclose()
        logger.info("Redis cache pool closed")


async def cache_get(pool: redis.Redis | None, key: str) -> str | None:
    """Get a value from cache.

    Returns None on cache miss, cache disabled, or any Redis error.
    Cache failures are silently logged — never raised to callers.

    Args:
        pool: Redis connection pool, or None if caching is disabled.
        key: Cache key.

    Returns:
        Cached string value, or None.
    """
    if pool is None:
        return None
    try:
        return await pool.get(key)
    except Exception as exc:
        logger.error("Cache get failed", extra={"key": key, "error": str(exc)})
        return None


async def cache_set(
    pool: redis.Redis | None,
    key: str,
    value: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Set a value in cache with TTL.

    No-ops when caching is disabled. Cache failures are logged but
    never raised — a failed cache write should never affect the response.

    Args:
        pool: Redis connection pool, or None if caching is disabled.
        key: Cache key.
        value: String value to cache.
        ttl_seconds: Time-to-live in seconds (default 3600).
    """
    if pool is None:
        return
    try:
        await pool.set(key, value, ex=ttl_seconds)
    except Exception as exc:
        logger.error("Cache set failed", extra={"key": key, "error": str(exc)})


async def cache_delete(pool: redis.Redis | None, key: str) -> None:
    """Delete a value from cache.

    No-ops when caching is disabled.

    Args:
        pool: Redis connection pool, or None if caching is disabled.
        key: Cache key to delete.
    """
    if pool is None:
        return
    try:
        await pool.delete(key)
    except Exception as exc:
        logger.error("Cache delete failed", extra={"key": key, "error": str(exc)})


async def cache_get_json(pool: redis.Redis | None, key: str) -> dict | list | None:
    """Get a JSON-deserialised value from cache.

    Args:
        pool: Redis connection pool, or None if caching is disabled.
        key: Cache key.

    Returns:
        Deserialised JSON value, or None on miss/error.
    """
    raw = await cache_get(pool, key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def cache_set_json(
    pool: redis.Redis | None,
    key: str,
    value: dict | list,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Serialise a value to JSON and store in cache with TTL.

    Args:
        pool: Redis connection pool, or None if caching is disabled.
        key: Cache key.
        value: JSON-serialisable value.
        ttl_seconds: Time-to-live in seconds (default 3600).
    """
    try:
        serialised = json.dumps(value)
    except (TypeError, ValueError) as exc:
        logger.error(
            "Cache JSON serialisation failed", extra={"key": key, "error": str(exc)}
        )
        return
    await cache_set(pool, key, serialised, ttl_seconds)
