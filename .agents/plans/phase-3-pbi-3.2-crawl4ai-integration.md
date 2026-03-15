# PBI 3.2 — Crawl4AI Integration (Web Scraping Collector)

The following plan should be complete, but validate documentation and codebase patterns before implementing.

## Feature Description

Add a web scraping collector using Crawl4AI that scrapes configured web pages on a schedule and stores structured content in Postgres. Uses rule-based extraction only — zero LLM imports in the collector module. The collector follows the existing `BaseCollector` pattern and is registered with APScheduler alongside the YouTube collector.

## User Story

As a Python developer building AI agents
I want my collectors to scrape web pages for structured data on a schedule
So that my agents can answer questions about web content without me building scraping infrastructure

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `src/collector/`, `src/db/queries.py`, `src/db/migrations/`, `src/config.py`
**Dependencies**: `crawl4ai>=0.8.0`
**Branch**: `feat/pbi-3.2-crawl4ai` (from `main`)
**Prerequisite PBIs**: None (independent of 3.1 and 3.3)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING!

- `CLAUDE.md` — Coding conventions, boundary rules. READ FIRST.
- `docs/Phase3.md` (lines 227-305) — PBI 3.2 specification
- `src/collector/base.py` (lines 1-33) — BaseCollector ABC: `__init__(pool)`, `async collect() -> int`
- `src/collector/youtube.py` (lines 1-283) — Full collector implementation to mirror: error handling, per-item logging, async patterns
- `src/collector/models.py` (lines 1-33) — Collector-layer Pydantic model pattern
- `src/collector/scheduler.py` (lines 1-63) — Scheduler registration pattern for new jobs
- `src/db/queries.py` (lines 1-268) — Repository pattern: typed functions, Pydantic model returns, all SQL here
- `src/db/migrations/versions/0001_initial.py` (lines 1-66) — Migration file format
- `src/config.py` (lines 1-91) — Config pattern
- `tests/test_collector.py` (lines 1-164) — Boundary test + collector test patterns
- `.env.example` — Env var docs

### New Files to Create

- `src/collector/web_scraper.py` — WebScrapingCollector implementation
- `src/db/migrations/versions/0002_scraped_pages.py` — Table migration
- `tests/test_web_scraper.py` — Scraper tests

### Files to Modify

- `pyproject.toml` — Add `crawl4ai` dependency
- `src/config.py` — Add `SCRAPE_URLS`, `SCRAPE_INTERVAL_MINUTES`
- `.env.example` — Document scraping env vars
- `src/db/queries.py` — Add scraped page query functions
- `src/collector/scheduler.py` — Register web scraper schedule
- `docker-compose.yml` — Add scraping env vars
- `.github/workflows/ci.yml` — Add scraping env vars
- `Dockerfile` — Add Playwright system deps for Crawl4AI

### Relevant Documentation — READ BEFORE IMPLEMENTING!

- [Crawl4AI Documentation (v0.8.x)](https://docs.crawl4ai.com/)
  - AsyncWebCrawler API, BrowserConfig, CrawlerRunConfig
  - Why: Core API for the web scraping collector
- [Crawl4AI CrawlResult](https://docs.crawl4ai.com/api/crawl-result/)
  - Fields: `success`, `markdown.raw_markdown`, `metadata`, `status_code`
  - Why: Understanding what `arun()` returns
- [Crawl4AI No-LLM Extraction](https://docs.crawl4ai.com/extraction/no-llm-strategies/)
  - JsonCssExtractionStrategy for rule-based extraction
  - Why: Collector MUST NOT import LLM dependencies
- [Crawl4AI Installation](https://docs.crawl4ai.com/core/installation/)
  - `crawl4ai-setup` post-install step, Playwright browsers
  - Why: Docker and CI need Playwright system deps

### Patterns to Follow

**Collector Pattern** (from `src/collector/youtube.py`):
```python
class YouTubeCollector(BaseCollector):
    def __init__(self, pool: Pool, api_key: str) -> None:
        super().__init__(pool)
        self._api_key = api_key

    async def collect(self) -> int:
        if not self._api_key:
            logger.warning("...not set — skipping")
            return 0
        # ... per-item: try/except, log error, continue ...
```

**Scheduler Registration** (from `src/collector/scheduler.py`):
```python
await _scheduler.add_schedule(
    collector.collect,
    IntervalTrigger(minutes=COLLECTION_INTERVAL_MINUTES),
    id="youtube_collector",
)
```

**Query Function Pattern** (from `src/db/queries.py`):
```python
async def upsert_video(pool: Pool, video_id: str, ...) -> None:
    await pool.execute("INSERT INTO ... ON CONFLICT ... DO UPDATE ...", ...)
```

---

## STEP-BY-STEP TASKS

### Task 1: UPDATE `pyproject.toml` — Add crawl4ai dependency

- **IMPLEMENT**: Add `"crawl4ai>=0.8.0"` to `[project] dependencies`:
  ```
  # Web scraping (collectors)
  "crawl4ai>=0.8.0",
  ```
- **GOTCHA**: Crawl4AI requires a post-install step: `crawl4ai-setup` installs Playwright browsers (~400MB). This is needed for Docker and CI but NOT for `uv sync`.
- **VALIDATE**: `uv sync --dev`

---

### Task 2: UPDATE `src/config.py` — Add scraping env vars

- **IMPLEMENT**: Add after existing config sections:
  ```python
  # ---------------------------------------------------------------------------
  # Web Scraping (Phase 3)
  # ---------------------------------------------------------------------------
  SCRAPE_URLS: list[str] = [
      u.strip() for u in os.getenv("SCRAPE_URLS", "").split(",") if u.strip()
  ]
  SCRAPE_INTERVAL_MINUTES: int = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "360"))
  ```
- **GOTCHA**: `SCRAPE_URLS` is comma-separated string → `list[str]`. Filter empty strings.
- **VALIDATE**: `uv run python -c "from src.config import SCRAPE_URLS, SCRAPE_INTERVAL_MINUTES; print(f'urls={SCRAPE_URLS}, interval={SCRAPE_INTERVAL_MINUTES}')"`

---

### Task 3: UPDATE `.env.example` — Document scraping env vars

- **IMPLEMENT**: Append:
  ```env
  # -----------------------------------------------------------------------------
  # Web Scraping (Phase 3)
  # Comma-separated URLs for the web scraping collector.
  # SCRAPE_INTERVAL_MINUTES: How often the scraper runs (default: 360 = 6 hours).
  # Leave SCRAPE_URLS empty to disable the web scraper.
  # -----------------------------------------------------------------------------
  SCRAPE_URLS=
  SCRAPE_INTERVAL_MINUTES=360
  ```
- **VALIDATE**: Visual review

---

### Task 4: CREATE `src/db/migrations/versions/0002_scraped_pages.py` — Migration

- **IMPLEMENT**:
  ```python
  """Add scraped_pages table for web scraping collector.

  Revision ID: 0002
  Revises: 0001
  Create Date: 2026-03-15
  """

  from collections.abc import Sequence

  from alembic import op

  revision: str = "0002"
  down_revision: str = "0001"
  branch_labels: str | Sequence[str] | None = None
  depends_on: str | Sequence[str] | None = None


  def upgrade() -> None:
      """Create the scraped_pages table."""
      op.execute(
          """
          CREATE TABLE scraped_pages (
              id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
              url        VARCHAR     NOT NULL UNIQUE,
              title      VARCHAR,
              content    TEXT,
              metadata   JSONB       DEFAULT '{}',
              embedding  vector(1536),
              scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
          )
          """
      )
      op.execute("CREATE INDEX idx_scraped_pages_url ON scraped_pages(url)")


  def downgrade() -> None:
      """Drop the scraped_pages table."""
      op.execute("DROP TABLE IF EXISTS scraped_pages")
  ```
- **PATTERN**: Mirror `0001_initial.py` exactly — raw `op.execute()` SQL, same docstring format
- **GOTCHA**: `down_revision = "0001"` — must chain correctly
- **GOTCHA**: `embedding vector(1536)` uses pgvector extension from migration 0001
- **VALIDATE**: `uv run alembic heads` (should show 0002)

---

### Task 5: UPDATE `src/db/queries.py` — Add scraped page queries

- **IMPLEMENT**: Add after existing video queries:

  **Model:**
  ```python
  class ScrapedPageRecord(BaseModel):
      """A scraped web page row from the scraped_pages table."""

      id: UUID
      url: str
      title: str | None = None
      content: str | None = None
      metadata: dict = Field(default_factory=dict)
      scraped_at: datetime
  ```

  **Upsert function:**
  ```python
  async def upsert_scraped_page(
      pool: Pool,
      url: str,
      title: str | None,
      content: str | None,
      metadata: dict | None = None,
  ) -> None:
      """Insert a scraped page or update its content if the URL already exists.

      Args:
          pool: asyncpg connection pool.
          url: Page URL (unique key).
          title: Page title extracted from metadata.
          content: Page content as markdown text.
          metadata: Additional page metadata as JSON.
      """
      import json

      await pool.execute(
          """
          INSERT INTO scraped_pages (url, title, content, metadata, scraped_at)
          VALUES ($1, $2, $3, $4::jsonb, NOW())
          ON CONFLICT (url) DO UPDATE SET
              title      = EXCLUDED.title,
              content    = EXCLUDED.content,
              metadata   = EXCLUDED.metadata,
              scraped_at = NOW()
          """,
          url,
          title,
          content,
          json.dumps(metadata or {}),
      )
      logger.debug("Upserted scraped page", extra={"url": url})
  ```

  **Search function:**
  ```python
  async def search_scraped_pages(
      pool: Pool,
      query: str,
      limit: int = 10,
  ) -> list[ScrapedPageRecord]:
      """Search scraped pages by title and content using full-text search.

      Args:
          pool: asyncpg connection pool.
          query: Search terms to match against title and content.
          limit: Maximum number of results.

      Returns:
          List of matching scraped page records.
      """
      rows = await pool.fetch(
          """
          SELECT id, url, title, content, metadata, scraped_at
          FROM scraped_pages
          WHERE to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(content, ''))
                @@ plainto_tsquery('english', $1)
          ORDER BY scraped_at DESC
          LIMIT $2
          """,
          query,
          limit,
      )
      return [ScrapedPageRecord(**dict(row)) for row in rows]
  ```

  **Get by URL:**
  ```python
  async def get_scraped_page(pool: Pool, url: str) -> ScrapedPageRecord | None:
      """Fetch a single scraped page by URL.

      Args:
          pool: asyncpg connection pool.
          url: The page URL to look up.

      Returns:
          The scraped page record, or None if not found.
      """
      row = await pool.fetchrow(
          "SELECT id, url, title, content, metadata, scraped_at FROM scraped_pages WHERE url = $1",
          url,
      )
      if row is None:
          return None
      return ScrapedPageRecord(**dict(row))
  ```

- **GOTCHA**: `metadata` is JSONB — must `json.dumps()` before passing to asyncpg.
- **GOTCHA**: asyncpg returns `Record` objects — convert with `dict(row)`.
- **PATTERN**: Mirror `upsert_video()` and `search_videos()` exactly
- **VALIDATE**: `uv run python -c "from src.db.queries import upsert_scraped_page, search_scraped_pages, get_scraped_page, ScrapedPageRecord; print('OK')"`

---

### Task 6: CREATE `src/collector/web_scraper.py` — WebScrapingCollector

- **IMPLEMENT**:
  ```python
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
  ```
- **FORBIDDEN IMPORTS**: `pydantic_ai`, `langfuse` — boundary violation. The boundary test at `test_collector.py:17-45` auto-scans all `src/collector/*.py` files.
- **GOTCHA**: Import `AsyncWebCrawler` inside `collect()` to avoid import-time Playwright dependency when the scraper isn't used.
- **GOTCHA**: `result.markdown` is a `MarkdownGenerationResult` with `.raw_markdown`. Guard against None.
- **GOTCHA**: `result.metadata` may be None or a dict. Use `.get()` with defaults.
- **VALIDATE**: `uv run python -c "from src.collector.web_scraper import WebScrapingCollector; print('OK')"` AND `uv run pytest tests/test_collector.py::test_collector_has_no_llm_imports -v`

---

### Task 7: UPDATE `src/collector/scheduler.py` — Register scraper schedule

- **IMPLEMENT**: Add after YouTube collector registration:
  ```python
  from src.collector.web_scraper import WebScrapingCollector
  from src.config import SCRAPE_INTERVAL_MINUTES, SCRAPE_URLS
  ```
  In `start_scheduler()`, after the YouTube schedule block:
  ```python
  if SCRAPE_URLS:
      scraper = WebScrapingCollector(pool=pool, urls=SCRAPE_URLS)
      await _scheduler.add_schedule(
          scraper.collect,
          IntervalTrigger(minutes=SCRAPE_INTERVAL_MINUTES),
          id="web_scraper",
      )
      logger.info(
          "Web scraper scheduled",
          extra={"urls": len(SCRAPE_URLS), "interval_minutes": SCRAPE_INTERVAL_MINUTES},
      )
  ```
- **GOTCHA**: Only register when `SCRAPE_URLS` is non-empty.
- **VALIDATE**: `uv run python -c "from src.collector.scheduler import start_scheduler; print('OK')"`

---

### Task 8: UPDATE `docker-compose.yml` — Add scraping env vars

- **IMPLEMENT**: Add to `app` service `environment`:
  ```yaml
  SCRAPE_URLS: ${SCRAPE_URLS:-}
  SCRAPE_INTERVAL_MINUTES: ${SCRAPE_INTERVAL_MINUTES:-360}
  ```
- **VALIDATE**: Visual review

---

### Task 9: UPDATE `Dockerfile` — Add Playwright deps for Crawl4AI

- **IMPLEMENT**: Read the existing Dockerfile first. After the dependency install step, add:
  ```dockerfile
  # Crawl4AI requires Playwright browsers for web scraping.
  # Install system deps and browsers. The || true prevents build failure
  # in minimal environments where browsers cannot be installed.
  RUN apt-get update && apt-get install -y --no-install-recommends \
      libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
      libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
      libgbm1 libpango-1.0-0 libcairo2 libasound2 \
      && rm -rf /var/lib/apt/lists/*
  RUN crawl4ai-setup || true
  ```
- **GOTCHA**: Adds ~400MB to Docker image. Consider documenting this trade-off.
- **VALIDATE**: `docker build .` (or defer to CI)

---

### Task 10: UPDATE `.github/workflows/ci.yml` — Add scraping env vars

- **IMPLEMENT**: Add to test job `env`:
  ```yaml
  SCRAPE_URLS: ""
  SCRAPE_INTERVAL_MINUTES: "360"
  ```
- **GOTCHA**: Empty `SCRAPE_URLS` means scraper won't be registered in scheduler.
- **VALIDATE**: Visual review

---

### Task 11: CREATE `tests/test_web_scraper.py` — Web scraper tests

- **IMPLEMENT**:
  ```python
  """
  Web scraping collector tests.

  Covers the WebScrapingCollector behaviour and architectural boundary
  compliance. Crawl4AI and database calls are mocked throughout.
  """

  import ast
  import pathlib
  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest
  ```

  **Boundary test:**
  ```python
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
      assert not violations, f"web_scraper.py imports LLM deps:\n" + "\n".join(violations)
  ```

  **Behavior tests (mock Crawl4AI + queries):**
  - `test_scraper_returns_zero_when_no_urls`:
    ```python
    async def test_scraper_returns_zero_when_no_urls(mock_pool):
        """Collector returns 0 without crawling when URL list is empty."""
        from src.collector.web_scraper import WebScrapingCollector
        collector = WebScrapingCollector(pool=mock_pool, urls=[])
        assert await collector.collect() == 0
    ```
  - `test_scraper_scrapes_and_stores_page` — Mock crawler context manager + arun() success
  - `test_scraper_handles_failed_crawl` — result.success=False
  - `test_scraper_continues_on_single_url_failure` — One URL raises, others succeed

  **Mocking pattern for AsyncWebCrawler:**
  ```python
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
  ```

- **VALIDATE**: `uv run pytest tests/test_web_scraper.py -v`

---

### Task 12: RUN full validation

- **VALIDATE**:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  uv run pytest tests/ -v --tb=short
  uv run pytest tests/test_collector.py::test_collector_has_no_llm_imports -v
  uv run alembic heads
  ```

---

## TESTING STRATEGY

### Unit Tests
- Mock `AsyncWebCrawler` entirely — no real browser or network
- Mock `src.db.queries.upsert_scraped_page` — no real database
- Verify boundary compliance with AST scanning

### Edge Cases
- Empty URL list → 0 count, no crawler created
- Single URL fails → others still scraped
- `result.success=False` → logged, skipped
- `result.markdown` is None → empty content stored
- `result.metadata` is None → empty title

---

## ACCEPTANCE CRITERIA

- [ ] `crawl4ai` is in `pyproject.toml` and resolves via `uv sync`
- [ ] `scraped_pages` table created via Alembic migration 0002
- [ ] `upsert_scraped_page()`, `search_scraped_pages()`, `get_scraped_page()` in queries.py
- [ ] `WebScrapingCollector` extends `BaseCollector` with `collect() -> int`
- [ ] Collector has ZERO `pydantic_ai` or `langfuse` imports (boundary test passes)
- [ ] Scraper registered with APScheduler when `SCRAPE_URLS` is non-empty
- [ ] Individual URL failures don't abort the collection cycle
- [ ] Playwright deps documented for Docker
- [ ] All existing tests still pass
- [ ] New tests cover: boundary, empty URLs, success, failure, continuation

---

## NOTES

- **Playwright image bloat**: Crawl4AI + Playwright adds ~400MB to Docker image. Consider multi-stage builds or a separate scraper container for production.
- **crawl4ai-setup**: Must run after `uv sync` to install Playwright browsers. In CI, this step may need to be added to the workflow. Alternatively, mock all Crawl4AI calls in tests so Playwright isn't needed for CI.
- **Lazy import**: `AsyncWebCrawler` is imported inside `collect()` to avoid import-time Playwright dependency issues when the module is imported but scraping isn't used.
