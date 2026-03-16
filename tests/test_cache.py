"""
Cache client tests.

Covers Redis cache operations: pool creation, get/set/delete, JSON
helpers, and graceful degradation when caching is disabled.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_create_cache_pool_returns_none_when_disabled():
    """create_cache_pool returns None when CACHE_ENABLED=false."""
    with patch("src.cache.client.CACHE_ENABLED", False):
        from src.cache.client import create_cache_pool

        result = await create_cache_pool()

    assert result is None


@pytest.mark.asyncio
async def test_cache_get_returns_none_when_pool_is_none():
    """cache_get returns None when pool is None (caching disabled)."""
    from src.cache.client import cache_get

    result = await cache_get(None, "some-key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_noop_when_pool_is_none():
    """cache_set silently no-ops when pool is None."""
    from src.cache.client import cache_set

    await cache_set(None, "key", "value")


@pytest.mark.asyncio
async def test_cache_delete_noop_when_pool_is_none():
    """cache_delete silently no-ops when pool is None."""
    from src.cache.client import cache_delete

    await cache_delete(None, "key")


@pytest.mark.asyncio
async def test_cache_get_delegates_to_redis(mock_cache):
    """cache_get calls Redis get with the correct key."""
    mock_cache.get = AsyncMock(return_value="cached-value")

    from src.cache.client import cache_get

    result = await cache_get(mock_cache, "test-key")

    assert result == "cached-value"
    mock_cache.get.assert_called_once_with("test-key")


@pytest.mark.asyncio
async def test_cache_set_delegates_to_redis_with_ttl(mock_cache):
    """cache_set calls Redis set with key, value, and TTL."""
    from src.cache.client import cache_set

    await cache_set(mock_cache, "key", "value", ttl_seconds=300)

    mock_cache.set.assert_called_once_with("key", "value", ex=300)


@pytest.mark.asyncio
async def test_cache_delete_delegates_to_redis(mock_cache):
    """cache_delete calls Redis delete with the correct key."""
    from src.cache.client import cache_delete

    await cache_delete(mock_cache, "test-key")

    mock_cache.delete.assert_called_once_with("test-key")


@pytest.mark.asyncio
async def test_cache_get_returns_none_on_redis_error(mock_cache):
    """cache_get returns None and logs error on Redis failure."""
    mock_cache.get = AsyncMock(side_effect=ConnectionError("redis down"))

    from src.cache.client import cache_get

    result = await cache_get(mock_cache, "key")

    assert result is None


@pytest.mark.asyncio
async def test_cache_set_does_not_raise_on_redis_error(mock_cache):
    """cache_set silently logs errors without raising."""
    mock_cache.set = AsyncMock(side_effect=ConnectionError("redis down"))

    from src.cache.client import cache_set

    await cache_set(mock_cache, "key", "value")


@pytest.mark.asyncio
async def test_cache_get_json_deserialises_value(mock_cache):
    """cache_get_json returns deserialised JSON from cache."""
    mock_cache.get = AsyncMock(return_value='{"name": "test", "count": 42}')

    from src.cache.client import cache_get_json

    result = await cache_get_json(mock_cache, "json-key")

    assert result == {"name": "test", "count": 42}


@pytest.mark.asyncio
async def test_cache_get_json_returns_none_on_invalid_json(mock_cache):
    """cache_get_json returns None when cached value is not valid JSON."""
    mock_cache.get = AsyncMock(return_value="not-json")

    from src.cache.client import cache_get_json

    result = await cache_get_json(mock_cache, "bad-json")

    assert result is None


@pytest.mark.asyncio
async def test_cache_get_json_returns_none_when_pool_is_none():
    """cache_get_json returns None when caching is disabled."""
    from src.cache.client import cache_get_json

    result = await cache_get_json(None, "key")

    assert result is None


@pytest.mark.asyncio
async def test_cache_set_json_serialises_value(mock_cache):
    """cache_set_json serialises dict to JSON string before storing."""
    from src.cache.client import cache_set_json

    await cache_set_json(mock_cache, "json-key", {"data": [1, 2, 3]}, ttl_seconds=600)

    mock_cache.set.assert_called_once()
    call_args = mock_cache.set.call_args
    assert '"data"' in call_args[0][1]
