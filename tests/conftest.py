"""
Shared test fixtures.

Provides mocked infrastructure (database pool, HTTP client) so that unit
and integration tests can run without external services. Tests that
require a real database should opt in via a separate fixture.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_pool():
    """Return a mock asyncpg Pool with no-op async methods.

    The default return values (empty list / None) cover the common case
    where the database has no data. Override specific methods per test
    when populated results are needed.
    """
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock(return_value=None)
    pool.close = AsyncMock()
    return pool


@pytest.fixture
def mock_cache():
    """Return a mock Redis connection for cache tests."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    cache.ping = AsyncMock()
    cache.aclose = AsyncMock()
    return cache


@pytest.fixture
def mock_memory_store():
    """Return a mock BaseMemoryStore with no-op async methods."""
    store = MagicMock()
    store.add = AsyncMock(return_value="mem-test-123")
    store.search = AsyncMock(return_value=[])
    store.get_all = AsyncMock(return_value=[])
    store.delete = AsyncMock()
    return store


@pytest.fixture
async def client(mock_pool):
    """Return an httpx AsyncClient backed by the FastAPI app.

    The database pool, APScheduler, and memory client are mocked so no
    external services are needed. Langfuse validation is also suppressed
    so missing keys do not produce warning noise in test output.
    """
    # ASGITransport sends only "http" scope events — it never triggers the ASGI
    # lifespan protocol, so the lifespan context manager never runs and
    # app.state.pool is never set. Inject the pool directly so route handlers
    # that access request.app.state.pool work without a real database.
    from src.api.main import app

    with (
        patch("src.api.main.create_pool", AsyncMock(return_value=mock_pool)),
        patch("src.api.main.create_memory_client", AsyncMock(return_value=None)),
        patch("src.api.main.create_cache_pool", AsyncMock(return_value=None)),
        patch("src.api.main.close_cache_pool", AsyncMock()),
        patch("src.api.main.start_scheduler", AsyncMock()),
        patch("src.api.main.shutdown_scheduler", AsyncMock()),
        patch("src.api.main.validate_provider_config"),
    ):
        app.state.pool = mock_pool
        app.state.memory = None  # Memory disabled in API tests by default
        app.state.cache = None  # Cache disabled in API tests by default
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
        del app.state.pool
        if hasattr(app.state, "memory"):
            del app.state.memory
        if hasattr(app.state, "cache"):
            del app.state.cache
