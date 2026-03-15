"""
Web scraping collector tests.

Covers the WebScrapingCollector behaviour and architectural boundary
compliance. Crawl4AI and database calls are mocked throughout.
"""

import ast
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Boundary test
# ---------------------------------------------------------------------------


def test_web_scraper_has_no_llm_imports():
    """Verify web_scraper.py has no pydantic_ai or langfuse imports."""
    forbidden = {"pydantic_ai", "langfuse"}
    source = pathlib.Path("src/collector/web_scraper.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for pkg in forbidden:
                    if alias.name == pkg or alias.name.startswith(f"{pkg}."):
                        violations.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for pkg in forbidden:
                if module == pkg or module.startswith(f"{pkg}."):
                    violations.append(f"line {node.lineno}: from {module}")
    assert not violations, "web_scraper.py imports LLM deps:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_crawl_result(success: bool, title: str = "", content: str = ""):
    """Create a mock CrawlResult."""
    result = MagicMock()
    result.success = success
    if success:
        result.metadata = {"title": title} if title else {}
        md = MagicMock()
        md.raw_markdown = content
        result.markdown = md
    else:
        result.metadata = None
        result.markdown = None
        result.status_code = 404
        result.error_message = "Not found"
    return result


def _make_mock_crawler(results_by_url):
    """Create a mock AsyncWebCrawler context manager."""
    mock_crawler = MagicMock()

    async def mock_arun(url, **kwargs):
        return results_by_url.get(url, MagicMock(success=False))

    mock_crawler.arun = AsyncMock(side_effect=mock_arun)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm


# ---------------------------------------------------------------------------
# Behaviour tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scraper_returns_zero_when_no_urls(mock_pool):
    """Collector returns 0 without crawling when URL list is empty."""
    from src.collector.web_scraper import WebScrapingCollector

    collector = WebScrapingCollector(pool=mock_pool, urls=[])
    assert await collector.collect() == 0


@pytest.mark.asyncio
async def test_scraper_scrapes_and_stores_page(mock_pool):
    """Collector scrapes a URL and upserts content into the database."""
    from src.collector.web_scraper import WebScrapingCollector

    url = "https://example.com/page"
    result = _make_crawl_result(success=True, title="Example", content="# Hello")
    mock_cm = _make_mock_crawler({url: result})

    with (
        patch("crawl4ai.AsyncWebCrawler", return_value=mock_cm),
        patch(
            "src.collector.web_scraper.queries.upsert_scraped_page", AsyncMock()
        ) as mock_upsert,
    ):
        collector = WebScrapingCollector(pool=mock_pool, urls=[url])
        count = await collector.collect()

    assert count == 1
    mock_upsert.assert_called_once_with(
        mock_pool,
        url=url,
        title="Example",
        content="# Hello",
        metadata={"title": "Example"},
    )


@pytest.mark.asyncio
async def test_scraper_handles_failed_crawl(mock_pool):
    """Collector returns 0 when the crawl result indicates failure."""
    from src.collector.web_scraper import WebScrapingCollector

    url = "https://example.com/missing"
    result = _make_crawl_result(success=False)
    mock_cm = _make_mock_crawler({url: result})

    with (
        patch("crawl4ai.AsyncWebCrawler", return_value=mock_cm),
        patch(
            "src.collector.web_scraper.queries.upsert_scraped_page", AsyncMock()
        ) as mock_upsert,
    ):
        collector = WebScrapingCollector(pool=mock_pool, urls=[url])
        count = await collector.collect()

    assert count == 0
    mock_upsert.assert_not_called()


@pytest.mark.asyncio
async def test_scraper_continues_on_single_url_failure(mock_pool):
    """One URL raising an exception doesn't prevent others from being scraped."""
    from src.collector.web_scraper import WebScrapingCollector

    url_ok = "https://example.com/ok"
    url_bad = "https://example.com/bad"

    result_ok = _make_crawl_result(success=True, title="OK", content="content")

    mock_crawler = MagicMock()
    call_count = 0

    async def mock_arun(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if url == url_bad:
            raise RuntimeError("connection refused")
        return result_ok

    mock_crawler.arun = AsyncMock(side_effect=mock_arun)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("crawl4ai.AsyncWebCrawler", return_value=mock_cm),
        patch("src.collector.web_scraper.queries.upsert_scraped_page", AsyncMock()),
    ):
        collector = WebScrapingCollector(pool=mock_pool, urls=[url_bad, url_ok])
        count = await collector.collect()

    assert count == 1
    assert call_count == 2
