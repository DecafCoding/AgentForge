"""
SearXNG search module tests.

Covers the SearXNG search client. All HTTP calls are mocked — no real
API calls or SearXNG instances are needed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.mark.asyncio
async def test_searxng_returns_results():
    """search_web returns SearchResult list from SearXNG JSON response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "title": "SearXNG Result 1",
                "url": "https://example.com/1",
                "content": "Description from SearXNG",
            },
            {
                "title": "SearXNG Result 2",
                "url": "https://example.com/2",
                "content": "Another description",
            },
        ]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch("src.search.searxng.SEARXNG_HOST", "http://localhost:8080"),
        patch("src.search.searxng.httpx.AsyncClient", return_value=mock_client),
    ):
        from src.search.searxng import search_web

        results = await search_web("test query")

    assert len(results) == 2
    assert results[0].title == "SearXNG Result 1"
    assert results[0].description == "Description from SearXNG"
    assert results[1].url == "https://example.com/2"


@pytest.mark.asyncio
async def test_searxng_returns_empty_when_host_not_configured():
    """search_web returns empty list when SEARXNG_HOST is empty."""
    with patch("src.search.searxng.SEARXNG_HOST", ""):
        from src.search.searxng import search_web

        results = await search_web("test")

    assert results == []


@pytest.mark.asyncio
async def test_searxng_returns_empty_on_http_error():
    """search_web returns empty list on HTTP status errors."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "server error", request=MagicMock(), response=mock_response
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch("src.search.searxng.SEARXNG_HOST", "http://localhost:8080"),
        patch("src.search.searxng.httpx.AsyncClient", return_value=mock_client),
    ):
        from src.search.searxng import search_web

        results = await search_web("test")

    assert results == []


@pytest.mark.asyncio
async def test_searxng_returns_empty_on_request_error():
    """search_web returns empty list on network failures."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("connection refused"))

    with (
        patch("src.search.searxng.SEARXNG_HOST", "http://localhost:8080"),
        patch("src.search.searxng.httpx.AsyncClient", return_value=mock_client),
    ):
        from src.search.searxng import search_web

        results = await search_web("test")

    assert results == []


@pytest.mark.asyncio
async def test_searxng_maps_content_to_description():
    """SearXNG 'content' field is mapped to SearchResult.description."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Test",
                "url": "https://example.com",
                "content": "This is the content field",
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch("src.search.searxng.SEARXNG_HOST", "http://localhost:8080"),
        patch("src.search.searxng.httpx.AsyncClient", return_value=mock_client),
    ):
        from src.search.searxng import search_web

        results = await search_web("test")

    assert results[0].description == "This is the content field"


@pytest.mark.asyncio
async def test_searxng_limits_results_to_count():
    """search_web respects the count parameter."""
    many_results = [
        {"title": f"R{i}", "url": f"https://example.com/{i}", "content": f"D{i}"}
        for i in range(10)
    ]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"results": many_results}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with (
        patch("src.search.searxng.SEARXNG_HOST", "http://localhost:8080"),
        patch("src.search.searxng.httpx.AsyncClient", return_value=mock_client),
    ):
        from src.search.searxng import search_web

        results = await search_web("test", count=3)

    assert len(results) == 3
