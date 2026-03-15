"""
Web page scraping collector.

Uses Crawl4AI's AsyncWebCrawler to scrape configured web pages and store
their content as markdown in Postgres. Uses rule-based extraction only —
no LLM dependencies. This module belongs to the Collector layer and must
not import pydantic_ai, langfuse, or any LLM-related dependency.
"""

import logging

from asyncpg import Pool

from src.collector.base import BaseCollector
from src.db import queries

logger = logging.getLogger(__name__)


class WebScrapingCollector(BaseCollector):
    """Scrapes web pages using Crawl4AI and stores content in Postgres.

    Implements BaseCollector for scheduled web scraping. Each collect()
    cycle iterates over the configured URLs, scrapes each page, and
    upserts the markdown content into the scraped_pages table. Individual
    URL failures are logged and do not abort the cycle.
    """

    def __init__(self, pool: Pool, urls: list[str]) -> None:
        super().__init__(pool)
        self._urls = urls

    async def collect(self) -> int:
        """Scrape all configured URLs and store results in Postgres.

        Returns:
            Number of pages successfully scraped and stored.
        """
        if not self._urls:
            logger.info("No URLs configured — skipping web scrape")
            return 0

        from crawl4ai import AsyncWebCrawler

        count = 0
        async with AsyncWebCrawler() as crawler:
            for url in self._urls:
                try:
                    count += await self._scrape_url(crawler, url)
                except Exception as exc:
                    logger.error(
                        "Failed to scrape URL",
                        extra={"url": url, "error": str(exc)},
                    )

        logger.info("Web scrape cycle complete", extra={"pages_scraped": count})
        return count

    async def _scrape_url(self, crawler: object, url: str) -> int:
        """Scrape a single URL and store the result.

        Args:
            crawler: An active AsyncWebCrawler instance.
            url: The URL to scrape.

        Returns:
            1 if the page was successfully scraped and stored, 0 otherwise.
        """
        logger.info("Scraping URL", extra={"url": url})
        result = await crawler.arun(url=url)

        if not result.success:
            logger.warning(
                "Scrape failed",
                extra={
                    "url": url,
                    "status_code": getattr(result, "status_code", None),
                    "error": getattr(result, "error_message", "unknown"),
                },
            )
            return 0

        title = result.metadata.get("title", "") if result.metadata else ""
        content = result.markdown.raw_markdown if result.markdown else ""

        await queries.upsert_scraped_page(
            self._pool,
            url=url,
            title=title,
            content=content,
            metadata=result.metadata or {},
        )

        logger.info("Page scraped and stored", extra={"url": url, "title": title[:80]})
        return 1
