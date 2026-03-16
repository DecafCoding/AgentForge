"""
Web search module tests.

Covers the Brave Search API client and the web_search agent tool.
All HTTP calls are mocked — no real API calls are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.search.brave import SearchResult

# ---------------------------------------------------------------------------
# Brave Search client tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_web_returns_results():
    """search_web returns SearchResult list from Brave API response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "web": {
            "results": [
                {
                    "title": "Result 1",
                    "url": "https://example.com/1",
                    "description": "Desc 1",
                },
                {
                    "title": "Result 2",
                    "url": "https://example.com/2",
                    "description": "Desc 2",
                },
            ]
        }
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch("src.search.brave.BRAVE_SEARCH_ENABLED", True),
        patch("src.search.brave.BRAVE_SEARCH_API_KEY", "test-key"),
        patch("src.search.brave.httpx.AsyncClient", return_value=mock_client),
    ):
        from src.search.brave import search_web

        results = await search_web("test query")

    assert len(results) == 2
    assert results[0].title == "Result 1"
    assert results[0].url == "https://example.com/1"
    assert results[1].description == "Desc 2"


@pytest.mark.asyncio
async def test_search_web_returns_empty_when_disabled():
    """search_web returns empty list when BRAVE_SEARCH_ENABLED is False."""
    with patch("src.search.brave.BRAVE_SEARCH_ENABLED", False):
        from src.search.brave import search_web

        results = await search_web("test")

    assert results == []


@pytest.mark.asyncio
async def test_search_web_returns_empty_when_no_api_key():
    """search_web returns empty list when API key is empty."""
    with (
        patch("src.search.brave.BRAVE_SEARCH_ENABLED", True),
        patch("src.search.brave.BRAVE_SEARCH_API_KEY", ""),
    ):
        from src.search.brave import search_web

        results = await search_web("test")

    assert results == []


@pytest.mark.asyncio
async def test_search_web_returns_empty_on_http_error():
    """search_web returns empty list on HTTP status errors (429, 401, etc.)."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "rate limited", request=MagicMock(), response=mock_response
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch("src.search.brave.BRAVE_SEARCH_ENABLED", True),
        patch("src.search.brave.BRAVE_SEARCH_API_KEY", "test-key"),
        patch("src.search.brave.httpx.AsyncClient", return_value=mock_client),
    ):
        from src.search.brave import search_web

        results = await search_web("test")

    assert results == []


@pytest.mark.asyncio
async def test_search_web_returns_empty_on_request_error():
    """search_web returns empty list on network failures."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("connection refused"))

    with (
        patch("src.search.brave.BRAVE_SEARCH_ENABLED", True),
        patch("src.search.brave.BRAVE_SEARCH_API_KEY", "test-key"),
        patch("src.search.brave.httpx.AsyncClient", return_value=mock_client),
    ):
        from src.search.brave import search_web

        results = await search_web("test")

    assert results == []


@pytest.mark.asyncio
async def test_search_web_handles_missing_web_key():
    """search_web returns empty list when API response has no 'web' key."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"query": {"original": "test"}}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch("src.search.brave.BRAVE_SEARCH_ENABLED", True),
        patch("src.search.brave.BRAVE_SEARCH_API_KEY", "test-key"),
        patch("src.search.brave.httpx.AsyncClient", return_value=mock_client),
    ):
        from src.search.brave import search_web

        results = await search_web("test")

    assert results == []


# ---------------------------------------------------------------------------
# Agent tool test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_web_search_tool_returns_serializable_dicts(mock_pool):
    """web_search tool returns list of dicts (JSON-serializable for LLM)."""
    mock_results = [
        SearchResult(title="T1", url="https://example.com", description="D1")
    ]

    ctx = MagicMock()
    ctx.deps = mock_pool

    with patch("src.search.brave.search_web", AsyncMock(return_value=mock_results)):
        from src.agent.tools import web_search

        results = await web_search(ctx, query="test")

    assert isinstance(results, list)
    assert isinstance(results[0], dict)
    assert results[0]["title"] == "T1"
