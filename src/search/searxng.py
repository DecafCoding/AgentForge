"""
SearXNG search API client.

Provides async web search via a self-hosted SearXNG instance. Results
are returned as typed Pydantic models matching the same SearchResult
interface used by the Brave Search client. This module belongs to the
Search layer. It is used by agent tools during reasoning — not by
collectors on a schedule.
"""

import logging

import httpx
from pydantic import BaseModel

from src.config import SEARXNG_HOST

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """A single web search result from SearXNG."""

    title: str
    url: str
    description: str


class SearXNGSearchError(Exception):
    """Raised when SearXNG returns an error."""


async def search_web(query: str, count: int = 5) -> list[SearchResult]:
    """Search the web using a self-hosted SearXNG instance.

    Returns an empty list when SearXNG is unreachable or returns an error.
    Never raises to callers — search failure should not crash the agent.

    Args:
        query: Search query string.
        count: Maximum results to return.

    Returns:
        List of search results with title, url, and description.
    """
    if not SEARXNG_HOST:
        logger.warning("SEARXNG_HOST not configured — SearXNG search unavailable")
        return []

    count = min(count, 20)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SEARXNG_HOST}/search",
                params={
                    "q": query,
                    "format": "json",
                    "number_of_results": count,
                },
                timeout=10.0,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "SearXNG API error",
            extra={"status": exc.response.status_code, "query": query},
        )
        return []
    except httpx.RequestError as exc:
        logger.error(
            "SearXNG request failed",
            extra={"error": str(exc), "query": query},
        )
        return []

    data = response.json()
    raw_results = data.get("results", [])

    results = []
    for item in raw_results[:count]:
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                description=item.get("content", ""),
            )
        )

    logger.info(
        "SearXNG search complete",
        extra={"query": query, "results": len(results)},
    )
    return results
