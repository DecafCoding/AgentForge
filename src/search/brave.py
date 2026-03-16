"""
Brave Search API client.

Provides async web search via the Brave Search REST API. Results are
returned as typed Pydantic models. This module belongs to the Search
layer. It is used by agent tools during reasoning — not by collectors
on a schedule.
"""

import logging

import httpx
from pydantic import BaseModel

from src.config import BRAVE_SEARCH_API_KEY, BRAVE_SEARCH_ENABLED

logger = logging.getLogger(__name__)

_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


class SearchResult(BaseModel):
    """A single web search result from Brave Search."""

    title: str
    url: str
    description: str


class WebSearchError(Exception):
    """Raised when the Brave Search API returns an error."""


async def search_web(query: str, count: int = 5) -> list[SearchResult]:
    """Search the web using the Brave Search API.

    Returns an empty list when search is disabled, the API key is missing,
    or the API returns an error. Never raises to callers — search failure
    should not crash the agent.

    Args:
        query: Search query string.
        count: Maximum results to return (max 20).

    Returns:
        List of search results with title, url, and description.
    """
    if not BRAVE_SEARCH_ENABLED:
        logger.debug("Web search disabled via BRAVE_SEARCH_ENABLED=false")
        return []

    if not BRAVE_SEARCH_API_KEY:
        logger.warning("BRAVE_SEARCH_API_KEY not set — web search unavailable")
        return []

    count = min(count, 20)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                _BRAVE_SEARCH_URL,
                headers={
                    "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
                    "Accept": "application/json",
                },
                params={"q": query, "count": count},
                timeout=10.0,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Brave Search API error",
            extra={"status": exc.response.status_code, "query": query},
        )
        return []
    except httpx.RequestError as exc:
        logger.error(
            "Brave Search request failed",
            extra={"error": str(exc), "query": query},
        )
        return []

    data = response.json()
    raw_results = data.get("web", {}).get("results", [])

    results = []
    for item in raw_results:
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                description=item.get("description", ""),
            )
        )

    logger.info(
        "Web search complete",
        extra={"query": query, "results": len(results)},
    )
    return results
