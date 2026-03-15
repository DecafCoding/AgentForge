"""
Memory layer tests.

Covers the BaseMemoryStore interface, Mem0MemoryStore implementation,
helper functions, and client factory. All Mem0 calls are mocked — no
real LLM or Postgres connections are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.memory.client import _parse_database_url
from src.memory.helpers import get_relevant_context, store_interaction
from src.memory.store import Mem0MemoryStore

# ---------------------------------------------------------------------------
# URL parser tests
# ---------------------------------------------------------------------------


def test_parse_database_url_extracts_components():
    """Standard postgresql:// URL is parsed into individual fields."""
    result = _parse_database_url("postgresql://myuser:mypass@dbhost:5433/mydb")
    assert result == {
        "host": "dbhost",
        "port": 5433,
        "user": "myuser",
        "password": "mypass",
        "dbname": "mydb",
    }


def test_parse_database_url_handles_defaults():
    """Missing components fall back to sensible defaults."""
    result = _parse_database_url("postgresql://localhost/")
    assert result["host"] == "localhost"
    assert result["port"] == 5432
    assert result["user"] == "postgres"
    assert result["password"] == "postgres"
    assert result["dbname"] == "agentforge"


# ---------------------------------------------------------------------------
# Client factory tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_memory_client_returns_none_when_disabled():
    """create_memory_client() returns None when MEMORY_ENABLED is False."""
    from src.memory.client import create_memory_client

    with patch("src.memory.client.MEMORY_ENABLED", False):
        result = await create_memory_client()
    assert result is None


@pytest.mark.asyncio
async def test_create_memory_client_returns_none_when_no_api_key():
    """create_memory_client() returns None when OPENAI_API_KEY is empty."""
    from src.memory.client import create_memory_client

    with (
        patch("src.memory.client.MEMORY_ENABLED", True),
        patch("src.memory.client.MODEL_PROVIDER", "openai"),
        patch("src.memory.client.OPENAI_API_KEY", ""),
    ):
        result = await create_memory_client()
    assert result is None


# ---------------------------------------------------------------------------
# Mem0MemoryStore tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mem0_store_add_calls_client_and_returns_id():
    """Mem0MemoryStore.add() delegates to the Mem0 client and returns the memory ID."""
    mock_client = MagicMock()
    mock_client.add = AsyncMock(
        return_value={"results": [{"id": "mem-abc", "memory": "stored"}]}
    )
    store = Mem0MemoryStore(mock_client)

    result = await store.add("test content", user_id="user-1")

    mock_client.add.assert_called_once_with(
        "test content", user_id="user-1", metadata={}
    )
    assert result == "mem-abc"


@pytest.mark.asyncio
async def test_mem0_store_add_returns_empty_string_on_empty_results():
    """Mem0MemoryStore.add() returns empty string when results list is empty."""
    mock_client = MagicMock()
    mock_client.add = AsyncMock(return_value={"results": []})
    store = Mem0MemoryStore(mock_client)

    result = await store.add("test content", user_id="user-1")

    assert result == ""


@pytest.mark.asyncio
async def test_mem0_store_search_delegates_to_client():
    """Mem0MemoryStore.search() delegates to the Mem0 client."""
    expected = [{"memory": "some memory", "score": 0.9}]
    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value=expected)
    store = Mem0MemoryStore(mock_client)

    result = await store.search("query", user_id="user-1", limit=3)

    mock_client.search.assert_called_once_with("query", user_id="user-1", limit=3)
    assert result == expected


@pytest.mark.asyncio
async def test_mem0_store_get_all_delegates_to_client():
    """Mem0MemoryStore.get_all() delegates to the Mem0 client."""
    expected = [{"memory": "m1"}, {"memory": "m2"}]
    mock_client = MagicMock()
    mock_client.get_all = AsyncMock(return_value=expected)
    store = Mem0MemoryStore(mock_client)

    result = await store.get_all(user_id="user-1")

    mock_client.get_all.assert_called_once_with(user_id="user-1")
    assert result == expected


@pytest.mark.asyncio
async def test_mem0_store_delete_delegates_to_client():
    """Mem0MemoryStore.delete() delegates to the Mem0 client."""
    mock_client = MagicMock()
    mock_client.delete = AsyncMock()
    store = Mem0MemoryStore(mock_client)

    await store.delete("mem-123")

    mock_client.delete.assert_called_once_with("mem-123")


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_relevant_context_formats_memories(mock_memory_store):
    """get_relevant_context returns formatted context string."""
    mock_memory_store.search = AsyncMock(
        return_value=[
            {"memory": "User likes Python tutorials"},
            {"memory": "User asked about async patterns"},
        ]
    )

    result = await get_relevant_context(mock_memory_store, "python", "user-1")

    assert "Relevant context from previous conversations:" in result
    assert "User likes Python tutorials" in result
    assert "User asked about async patterns" in result


@pytest.mark.asyncio
async def test_get_relevant_context_returns_empty_for_no_results(mock_memory_store):
    """get_relevant_context returns empty string when no memories match."""
    mock_memory_store.search = AsyncMock(return_value=[])

    result = await get_relevant_context(mock_memory_store, "query", "user-1")

    assert result == ""


@pytest.mark.asyncio
async def test_get_relevant_context_returns_empty_on_search_error(mock_memory_store):
    """get_relevant_context returns empty string when search raises."""
    mock_memory_store.search = AsyncMock(side_effect=RuntimeError("db down"))

    result = await get_relevant_context(mock_memory_store, "query", "user-1")

    assert result == ""


@pytest.mark.asyncio
async def test_store_interaction_formats_and_stores(mock_memory_store):
    """store_interaction formats content and calls store.add()."""
    mock_memory_store.add = AsyncMock(return_value="mem-xyz")

    result = await store_interaction(
        mock_memory_store, "What is Python?", "A programming language.", "user-1"
    )

    assert result == "mem-xyz"
    call_args = mock_memory_store.add.call_args
    content = call_args[0][0]
    assert "User asked: What is Python?" in content
    assert "Assistant answered: A programming language." in content
    assert call_args[1]["user_id"] == "user-1"
    assert call_args[1]["metadata"] == {"type": "interaction"}


@pytest.mark.asyncio
async def test_store_interaction_returns_none_on_error(mock_memory_store):
    """store_interaction returns None when add() raises."""
    mock_memory_store.add = AsyncMock(side_effect=RuntimeError("write failed"))

    result = await store_interaction(mock_memory_store, "question", "answer", "user-1")

    assert result is None
