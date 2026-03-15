# Feature: Phase 3 — Memory & Web Intelligence

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Phase 3 adds three significant capability additions to AgentForge:

1. **Long-term memory (Mem0)** — Agents remember information across sessions using Postgres-backed vector storage. They can reference previous conversations, learn user preferences, and build context over time.
2. **Web scraping (Crawl4AI)** — Collectors can gather structured data from any web page, extending beyond API-only collection.
3. **Web search (Brave Search)** — Agents can search the web in real-time via Brave Search API and incorporate results into responses.

These additions fundamentally expand what agents can do — memory in particular changes agent design from stateless to stateful.

## User Story

As a Python developer building AI agents
I want my agents to remember across sessions, scrape web pages, and search the web
So that I can build more capable, context-aware AI applications without assembling these integrations myself

## Problem Statement

Phase 1-2 agents are stateless — they cannot remember previous conversations or access the open web. Collectors can only gather data from APIs with SDKs (YouTube). This limits the types of agents developers can build with the kit.

## Solution Statement

Add Mem0 for persistent cross-session memory with Postgres backend, Crawl4AI for web scraping as a collector, and Brave Search as a real-time agent tool. Each integration follows existing architectural patterns (collector/reasoning separation, typed models, async-first, Langfuse tracing).

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `src/memory/` (new), `src/search/` (new), `src/collector/`, `src/agent/`, `src/api/`, `src/config.py`, `src/db/`
**Dependencies**: `mem0ai`, `crawl4ai`, `httpx` (existing)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

**Architecture & Conventions:**
- `CLAUDE.md` — All coding conventions, architectural boundaries, naming rules. READ FIRST.
- `docs/Phase3.md` — Complete Phase 3 specification with PBI details and acceptance criteria.
- `docs/PRD.md` — Product requirements, architecture diagram, layer dependencies.

**Patterns to Mirror:**
- `src/collector/base.py` (lines 1-33) — Why: BaseCollector ABC pattern for WebScrapingCollector
- `src/collector/youtube.py` (lines 1-283) — Why: Full collector implementation to mirror (async patterns, error handling, pool injection)
- `src/collector/scheduler.py` (lines 1-63) — Why: Must register new web scraping job here
- `src/collector/models.py` (lines 1-33) — Why: Collector-layer Pydantic model pattern
- `src/agent/agent.py` (lines 65-129) — Why: run_agent() pattern with Langfuse tracing to mirror for memory agent
- `src/agent/tools.py` (lines 1-94) — Why: Pydantic AI tool pattern (RunContext[Pool]) for web search tool
- `src/agent/models.py` (lines 1-35) — Why: AgentResponse / Source models reused by memory agent
- `src/agent/research_agent.py` (lines 1-59) — Why: Standalone agent definition pattern
- `src/observability/tracing.py` (lines 1-62) — Why: Langfuse client singleton pattern
- `src/config.py` (lines 1-91) — Why: All config goes here — new env vars for Phase 3
- `src/db/client.py` (lines 1-37) — Why: Pool creation pattern
- `src/db/queries.py` (lines 1-268) — Why: Repository pattern — ALL SQL lives here, returns Pydantic models
- `src/db/migrations/versions/0001_initial.py` (lines 1-66) — Why: Migration pattern for new tables
- `src/api/main.py` (lines 1-76) — Why: Lifespan hook — must init/shutdown memory client here
- `src/api/routes.py` (lines 1-94) — Why: Thin route pattern, must add memory-aware endpoint
- `src/api/schemas.py` (lines 1-53) — Why: API schema pattern for new endpoints
- `tests/conftest.py` (lines 1-57) — Why: Fixture pattern for mock_pool, client
- `tests/test_collector.py` (lines 1-164) — Why: Boundary tests and collector test patterns
- `tests/test_agent.py` (lines 1-214) — Why: Agent mock patterns (MagicMock for result.output)
- `tests/test_api.py` (lines 1-127) — Why: API test patterns with httpx AsyncClient
- `.github/workflows/ci.yml` (lines 1-83) — Why: CI env vars need Phase 3 additions

### New Files to Create

**Memory Layer (`src/memory/`):**
- `src/memory/__init__.py` — Package init
- `src/memory/client.py` — Mem0 AsyncMemory client setup with Postgres backend
- `src/memory/store.py` — BaseMemoryStore ABC + Mem0MemoryStore implementation
- `src/memory/helpers.py` — Memory retrieval/injection helpers for agents

**Search Layer (`src/search/`):**
- `src/search/__init__.py` — Package init
- `src/search/brave.py` — Brave Search API client (async httpx)

**New Collector:**
- `src/collector/web_scraper.py` — Crawl4AI-based web scraping collector

**New Agent:**
- `src/agent/memory_agent.py` — Reference memory-aware agent with context injection

**Database:**
- `src/db/migrations/versions/0002_scraped_pages.py` — Migration for scraped_pages table

**Documentation:**
- `docs/memory-aware-agents.md` — Design changes, predictability, testing guidance

**Tests:**
- `tests/test_memory.py` — Memory store tests
- `tests/test_web_scraper.py` — Crawl4AI collector tests
- `tests/test_web_search.py` — Brave Search integration tests

### Relevant Documentation — YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [Mem0 Open-Source Configuration](https://docs.mem0.ai/open-source/configuration)
  - Exact config dict structure for pgvector + OpenAI
  - Why: Required for `src/memory/client.py` setup
- [Mem0 Async Memory](https://docs.mem0.ai/open-source/features/async-memory)
  - AsyncMemory class API (add, search, get_all, delete)
  - Why: CRITICAL — project is fully async, must use AsyncMemory not Memory
- [Mem0 pgvector docs](https://docs.mem0.ai/components/vectordbs/dbs/pgvector)
  - pgvector backend config, collection_name, embedding_model_dims
  - Why: Database configuration for memory storage
- [Crawl4AI Documentation (v0.8.x)](https://docs.crawl4ai.com/)
  - AsyncWebCrawler API, CrawlResult structure, BrowserConfig
  - Why: Core API for web scraping collector
- [Crawl4AI No-LLM Extraction Strategies](https://docs.crawl4ai.com/extraction/no-llm-strategies/)
  - JsonCssExtractionStrategy for rule-based extraction
  - Why: Collector module MUST NOT import LLM dependencies
- [Crawl4AI Installation](https://docs.crawl4ai.com/core/installation/)
  - `crawl4ai-setup` post-install step (Playwright browsers)
  - Why: Required post-install, Docker image needs Playwright deps
- [Brave Search API](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started)
  - Endpoint, headers, response JSON structure
  - Why: Web search integration for agent tools

### Patterns to Follow

**Naming Conventions:**
- Modules: `snake_case` — `web_scraper.py`, `brave.py`, `memory_agent.py`
- Classes: `PascalCase` — `WebScrapingCollector`, `Mem0MemoryStore`, `BaseMemoryStore`
- Functions: `snake_case` — `search_web`, `get_relevant_context`, `create_memory_client`
- Constants: `UPPER_SNAKE_CASE` — `BRAVE_SEARCH_API_KEY`, `MEMORY_ENABLED`

**Error Handling:**
```python
# Domain exceptions in the module where they originate
class MemoryError(Exception):
    """Raised when a memory operation fails."""

class WebSearchError(Exception):
    """Raised when the Brave Search API returns an error."""
```

**Logging Pattern:**
```python
import logging
logger = logging.getLogger(__name__)
# Use structured extra dict, never print()
logger.info("Memory stored", extra={"user_id": user_id, "memory_id": mem_id})
logger.error("Brave Search failed", extra={"query": query, "error": str(exc)})
```

**Module Docstring Pattern:**
```python
"""
Brave Search API client.

Provides async web search via the Brave Search REST API. Results are
returned as typed Pydantic models. This module belongs to the Search
layer and is imported by agent tools — it must not import collector
or scheduler dependencies.
"""
```

**Collector Pattern (from `src/collector/youtube.py`):**
- Inherit `BaseCollector`
- Accept `Pool` in `__init__` via `super().__init__(pool)`
- `async def collect(self) -> int:` returns count of items upserted
- Log and continue on per-item errors (one failure must not abort cycle)
- ZERO LLM imports (`pydantic_ai`, `langfuse` are FORBIDDEN)

**Agent Tool Pattern (from `src/agent/tools.py`):**
```python
async def web_search(
    ctx: RunContext[Pool],
    query: str,
    count: int = 5,
) -> list[SearchResult]:
    """Search the web for real-time information."""
    ...
```

**Config Pattern (from `src/config.py`):**
```python
# All env vars loaded here — no os.getenv elsewhere
BRAVE_SEARCH_API_KEY: str = os.getenv("BRAVE_SEARCH_API_KEY", "")
MEMORY_ENABLED: bool = os.getenv("MEMORY_ENABLED", "true").lower() == "true"
```

**Query Pattern (from `src/db/queries.py`):**
- All SQL in `src/db/queries.py` only
- Functions accept `Pool`, return typed Pydantic models
- Never raw rows or dicts

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — Configuration & Dependencies

Add new dependencies to `pyproject.toml`, add all new env vars to `src/config.py` and `.env.example`, create package directories and `__init__.py` files.

### Phase 2: Core Implementation — Memory, Search, Scraper

Build the three new capabilities:
1. Mem0 memory client and store (async)
2. Brave Search client
3. Crawl4AI web scraping collector

### Phase 3: Integration — Agent, API, Scheduler

Wire everything together:
1. Web search as agent tool
2. Memory-aware agent with context injection
3. API routes for memory endpoints
4. Scheduler registration for web scraper
5. Lifespan hook for memory client lifecycle

### Phase 4: Testing & Validation

Full test coverage:
1. Memory store tests (add, search, get_all, disabled mode)
2. Web scraper boundary + behavior tests
3. Web search tool tests
4. Memory-aware agent tests
5. API endpoint tests
6. Boundary verification updates

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: UPDATE `pyproject.toml` — Add Phase 3 dependencies

- **IMPLEMENT**: Add `mem0ai` and `crawl4ai` to `[project] dependencies`.
  - `"mem0ai>=1.0.0"` — long-term memory with Postgres backend
  - `"crawl4ai>=0.8.0"` — web scraping with Playwright
  - `httpx` is already present — used for Brave Search API calls
- **PATTERN**: Follow existing dependency format in `pyproject.toml` (lines 6-30)
- **GOTCHA**: `crawl4ai` requires a post-install step: `crawl4ai-setup` to install Playwright browsers. Add a note comment. For Docker, the Dockerfile will need Playwright system deps.
- **GOTCHA**: `mem0ai` pulls in many transitive dependencies. Pin `>=1.0.0` for the async API.
- **VALIDATE**: `uv sync --dev` (must resolve without errors)

---

### Task 2: UPDATE `src/config.py` — Add Phase 3 environment variables

- **IMPLEMENT**: Add these config constants after the existing Collector section:
  ```python
  # Memory (Phase 3)
  MEMORY_ENABLED: bool = os.getenv("MEMORY_ENABLED", "true").lower() == "true"
  MEMORY_MODEL: str = os.getenv("MEMORY_MODEL", "gpt-4o-mini")

  # Brave Search (Phase 3)
  BRAVE_SEARCH_API_KEY: str = os.getenv("BRAVE_SEARCH_API_KEY", "")
  BRAVE_SEARCH_ENABLED: bool = os.getenv("BRAVE_SEARCH_ENABLED", "true").lower() == "true"

  # Web Scraping (Phase 3)
  SCRAPE_URLS: list[str] = [u.strip() for u in os.getenv("SCRAPE_URLS", "").split(",") if u.strip()]
  SCRAPE_INTERVAL_MINUTES: int = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "360"))
  ```
- **PATTERN**: Mirror existing config pattern at `src/config.py:17-48` — module-level constants, typed, with sensible defaults
- **GOTCHA**: `MEMORY_ENABLED` and `BRAVE_SEARCH_ENABLED` must be booleans parsed from string env vars.
- **GOTCHA**: `SCRAPE_URLS` is a comma-separated string → `list[str]`. Filter out empty strings.
- **VALIDATE**: `uv run python -c "from src.config import MEMORY_ENABLED, BRAVE_SEARCH_API_KEY, SCRAPE_URLS; print('OK')"`

---

### Task 3: UPDATE `.env.example` — Document Phase 3 environment variables

- **IMPLEMENT**: Append a new Phase 3 section after the YouTube Collector section:
  ```env
  # -----------------------------------------------------------------------------
  # Memory (Phase 3)
  # Mem0 uses Postgres for vector storage. The same DATABASE_URL is used.
  # MEMORY_MODEL: Model used by Mem0 for memory extraction (low-cost model recommended).
  # MEMORY_ENABLED: Set to false to disable memory injection for testing.
  # -----------------------------------------------------------------------------
  MEMORY_ENABLED=true
  MEMORY_MODEL=gpt-4o-mini

  # -----------------------------------------------------------------------------
  # Web Search (Phase 3)
  # Brave Search API — https://brave.com/search/api/
  # Free tier: 2,000 queries/month.
  # BRAVE_SEARCH_ENABLED: Set to false to disable web search tool.
  # -----------------------------------------------------------------------------
  BRAVE_SEARCH_API_KEY=BSA-...
  BRAVE_SEARCH_ENABLED=true

  # -----------------------------------------------------------------------------
  # Web Scraping (Phase 3)
  # Comma-separated URLs for the web scraping collector to process on schedule.
  # SCRAPE_INTERVAL_MINUTES: How often to run the web scraping collector.
  # -----------------------------------------------------------------------------
  SCRAPE_URLS=
  SCRAPE_INTERVAL_MINUTES=360
  ```
- **PATTERN**: Mirror existing `.env.example` comment style — section header, description, example value
- **VALIDATE**: Visual review — file should be well-commented and follow existing structure

---

### Task 4: CREATE `src/memory/__init__.py` — Memory package init

- **IMPLEMENT**: Module docstring and public API exports:
  ```python
  """
  Long-term memory layer.

  Provides cross-session memory storage and retrieval backed by Mem0 with a
  Postgres/pgvector vector store. This module belongs to the Memory layer and
  sits alongside the Agent and Collector layers in the architecture.

  Public API:
    - create_memory_client() — initialise the Mem0 AsyncMemory instance
    - Mem0MemoryStore — async memory store wrapping the Mem0 client
    - BaseMemoryStore — ABC for alternative memory backends
    - get_relevant_context() — retrieve memories formatted for agent prompts
    - store_interaction() — persist a question/answer pair as memory
  """
  ```
- **VALIDATE**: `uv run python -c "import src.memory"`

---

### Task 5: CREATE `src/memory/client.py` — Mem0 AsyncMemory client setup

- **IMPLEMENT**: Create the Mem0 client factory using `AsyncMemory.from_config()`:
  ```python
  """
  Mem0 client initialisation.

  Creates an AsyncMemory instance configured with Postgres/pgvector as the
  vector store. Uses the same Postgres instance as the main application but
  with a separate collection_name to avoid table conflicts.

  This module belongs to the Memory layer. It imports from src.config only.
  """
  import logging
  from mem0 import AsyncMemory
  from src.config import (
      DATABASE_URL,
      MEMORY_ENABLED,
      MEMORY_MODEL,
      MODEL_PROVIDER,
      OPENAI_API_KEY,
  )
  logger = logging.getLogger(__name__)
  ```
- **KEY DESIGN DECISIONS**:
  - Use `AsyncMemory` (not `Memory`) — the project is fully async
  - Parse DATABASE_URL to extract host/port/user/password/dbname for Mem0's config dict (Mem0 doesn't accept a connection string — it needs individual fields)
  - Use `collection_name="agentforge_memories"` to namespace Mem0's tables
  - Set `embedding_model_dims=1536` for OpenAI `text-embedding-3-small`
  - Configure the embedder section explicitly
- **IMPLEMENT** `_parse_database_url(url: str) -> dict` helper to extract components from DATABASE_URL:
  ```python
  from urllib.parse import urlparse

  def _parse_database_url(url: str) -> dict[str, str | int]:
      """Extract connection parameters from a postgresql:// URL."""
      parsed = urlparse(url)
      return {
          "host": parsed.hostname or "localhost",
          "port": parsed.port or 5432,
          "user": parsed.username or "postgres",
          "password": parsed.password or "postgres",
          "dbname": parsed.path.lstrip("/") or "agentforge",
      }
  ```
- **IMPLEMENT** `async def create_memory_client() -> AsyncMemory | None`:
  - Return `None` if `MEMORY_ENABLED is False`
  - Build config dict with `vector_store`, `llm`, and `embedder` sections
  - Log the configuration (without secrets)
  - Return `AsyncMemory.from_config(config)`
- **GOTCHA**: Mem0's pgvector config takes individual fields, NOT a connection string. Must parse DATABASE_URL.
- **GOTCHA**: Must include `embedder` config section with `embedding_model_dims` matching the model. OpenAI `text-embedding-3-small` = 1536 dims.
- **GOTCHA**: Mem0 auto-creates tables on first use — no Alembic migration needed for Mem0's own tables.
- **GOTCHA**: The `llm` and `embedder` provider config needs the API key. For `openai` provider, the key is read from `OPENAI_API_KEY` env var by the underlying library, but it's safer to pass it explicitly in the config.
- **VALIDATE**: `uv run python -c "from src.memory.client import create_memory_client; print('OK')"`

---

### Task 6: CREATE `src/memory/store.py` — Memory store interface and implementation

- **IMPLEMENT**: Define `BaseMemoryStore` ABC and `Mem0MemoryStore` implementation:
  ```python
  """
  Memory store interface and Mem0 implementation.

  BaseMemoryStore defines the contract for memory backends. Mem0MemoryStore
  wraps the Mem0 AsyncMemory client. All methods are async. This module
  belongs to the Memory layer.
  """
  ```
- **BaseMemoryStore ABC methods**:
  - `async def add(self, content: str, user_id: str, metadata: dict | None = None) -> str` — Store a memory, return memory ID
  - `async def search(self, query: str, user_id: str, limit: int = 5) -> list[dict]` — Search relevant memories
  - `async def get_all(self, user_id: str) -> list[dict]` — Get all memories for a user
  - `async def delete(self, memory_id: str) -> None` — Delete a specific memory
- **Mem0MemoryStore implementation**:
  - Constructor takes `AsyncMemory` client
  - `add()` calls `await self._client.add(content, user_id=user_id, metadata=metadata or {})`
  - `search()` calls `await self._client.search(query, user_id=user_id, limit=limit)`
  - `get_all()` calls `await self._client.get_all(user_id=user_id)`
  - `delete()` calls `await self._client.delete(memory_id)`
- **GOTCHA**: Mem0's `add()` returns a dict with results — extract the ID from it. The exact shape may vary by version; check `result.get("results", [{}])[0].get("id", "")` or similar. Log the full return value at DEBUG level the first time.
- **GOTCHA**: Mem0's `search()` returns a list of dicts with `"memory"` and `"score"` keys (among others). Preserve this shape for the caller.
- **VALIDATE**: `uv run python -c "from src.memory.store import BaseMemoryStore, Mem0MemoryStore; print('OK')"`

---

### Task 7: CREATE `src/memory/helpers.py` — Memory retrieval and injection helpers

- **IMPLEMENT**: Two helper functions for agent-memory interaction:
  ```python
  """
  Memory retrieval and injection helpers.

  Provides utility functions for injecting relevant memories into agent
  prompts and storing interaction history. Used by memory-aware agents
  to bridge the memory store and the Pydantic AI agent system prompt.

  This module belongs to the Memory layer.
  """
  ```
- **`async def get_relevant_context(store: BaseMemoryStore, query: str, user_id: str, limit: int = 5) -> str`**:
  - Search the store for relevant memories
  - Format as a multi-line string prefixed with "Relevant context from previous conversations:"
  - Return empty string if no memories found
  - Log which memories were retrieved (for Langfuse metadata)
- **`async def store_interaction(store: BaseMemoryStore, question: str, answer: str, user_id: str) -> str | None`**:
  - Format as `"User asked: {question}\nAssistant answered: {answer}"`
  - Call `store.add()` with `metadata={"type": "interaction"}`
  - Return the memory ID or None on failure
  - Catch and log exceptions — memory storage failure should not crash the agent
- **VALIDATE**: `uv run python -c "from src.memory.helpers import get_relevant_context, store_interaction; print('OK')"`

---

### Task 8: CREATE `src/search/__init__.py` — Search package init

- **IMPLEMENT**: Package docstring:
  ```python
  """
  Web search integration layer.

  Provides async web search capabilities via external search APIs.
  Currently supports Brave Search. This module is imported by agent
  tools — it must not import collector or scheduler dependencies.
  """
  ```
- **VALIDATE**: `uv run python -c "import src.search"`

---

### Task 9: CREATE `src/search/brave.py` — Brave Search API client

- **IMPLEMENT**: Async Brave Search client using httpx:
  ```python
  """
  Brave Search API client.

  Provides async web search via the Brave Search REST API. Results are
  returned as typed Pydantic models. This module belongs to the Search
  layer. It is imported by agent tools — it must not import collector
  or scheduler dependencies.
  """
  ```
- **Define** `SearchResult` Pydantic model:
  ```python
  class SearchResult(BaseModel):
      """A single web search result from Brave Search."""
      title: str
      url: str
      description: str
  ```
- **Define** `WebSearchError(Exception)` for API errors
- **Implement** `async def search_web(query: str, count: int = 5) -> list[SearchResult]`:
  - Import `BRAVE_SEARCH_API_KEY` and `BRAVE_SEARCH_ENABLED` from `src.config`
  - Return empty list if `BRAVE_SEARCH_ENABLED is False` or API key is empty
  - Use `httpx.AsyncClient` to GET `https://api.search.brave.com/res/v1/web/search`
  - Headers: `{"X-Subscription-Token": BRAVE_SEARCH_API_KEY, "Accept": "application/json"}`
  - Params: `{"q": query, "count": count}`
  - Parse `response.json()["web"]["results"]` into `list[SearchResult]`
  - Handle `httpx.HTTPStatusError` (rate limiting 429, auth errors 401)
  - Log search execution at INFO level
- **GOTCHA**: Brave API returns `web.results` — the `web` key may be absent if no results. Use `.get("web", {}).get("results", [])`.
- **GOTCHA**: Free tier has 2,000 queries/month and 1 query/sec burst. Log rate limit headers at DEBUG.
- **GOTCHA**: The `description` field in Brave results may contain HTML entities — leave as-is for now (agent can handle it).
- **VALIDATE**: `uv run python -c "from src.search.brave import search_web, SearchResult; print('OK')"`

---

### Task 10: CREATE `src/db/migrations/versions/0002_scraped_pages.py` — Migration for scraped pages table

- **IMPLEMENT**: Alembic migration for the web scraping table:
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
- **PATTERN**: Mirror `0001_initial.py` migration format exactly
- **GOTCHA**: `down_revision` must be `"0001"` to chain correctly
- **GOTCHA**: `embedding vector(1536)` reuses the pgvector extension enabled in migration 0001
- **VALIDATE**: `uv run alembic heads` (should show 0002 as the head revision)

---

### Task 11: UPDATE `src/db/queries.py` — Add scraped page query functions

- **IMPLEMENT**: Add models and queries for scraped pages after existing video queries:
  - `ScrapedPageRecord` Pydantic model: `id: UUID`, `url: str`, `title: str | None`, `content: str | None`, `metadata: dict`, `scraped_at: datetime`
  - `async def upsert_scraped_page(pool, url, title, content, metadata=None) -> None` — UPSERT with ON CONFLICT (url)
  - `async def search_scraped_pages(pool, query, limit=10) -> list[ScrapedPageRecord]` — Full-text search on title + content
  - `async def get_scraped_page(pool, url) -> ScrapedPageRecord | None` — Fetch by URL
- **PATTERN**: Mirror `upsert_video()` at queries.py:212-267 and `search_videos()` at queries.py:156-179
- **GOTCHA**: All SQL lives here — the collector calls these functions, it does NOT write raw SQL.
- **VALIDATE**: `uv run python -c "from src.db.queries import upsert_scraped_page, search_scraped_pages; print('OK')"`

---

### Task 12: CREATE `src/collector/web_scraper.py` — Crawl4AI web scraping collector

- **IMPLEMENT**: WebScrapingCollector extending BaseCollector:
  ```python
  """
  Web page scraping collector.

  Uses Crawl4AI to scrape configured web pages and store their content
  in Postgres. Uses rule-based extraction only — no LLM dependencies.
  This module belongs to the Collector layer and must not import any
  LLM or observability dependencies.
  """
  ```
- **Class**: `WebScrapingCollector(BaseCollector)`:
  - `__init__(self, pool: Pool, urls: list[str]) -> None`
  - `async def collect(self) -> int`:
    - Return 0 if `urls` is empty
    - Use `async with AsyncWebCrawler() as crawler:`
    - For each URL: `result = await crawler.arun(url=url)`
    - If `result.success`: extract title from `result.metadata.get("title", "")`, content from `result.markdown.raw_markdown`
    - Call `upsert_scraped_page()` from `src.db.queries`
    - Log and continue on per-URL errors
    - Return total count of successful scrapes
- **IMPORTS** — ONLY these are allowed:
  ```python
  import logging
  from asyncpg import Pool
  from crawl4ai import AsyncWebCrawler
  from src.collector.base import BaseCollector
  from src.db import queries
  ```
- **FORBIDDEN IMPORTS**: `pydantic_ai`, `langfuse` — boundary violation
- **GOTCHA**: Crawl4AI's `result.markdown` is a `MarkdownGenerationResult` object. Access `.raw_markdown` for the text content.
- **GOTCHA**: Crawl4AI requires Playwright browsers installed. In CI, `crawl4ai-setup` must run. Consider making the collector graceful when Playwright is not available.
- **GOTCHA**: Some URLs may timeout or require JavaScript rendering. Set a reasonable timeout. Log failures and continue.
- **VALIDATE**: `uv run python -c "from src.collector.web_scraper import WebScrapingCollector; print('OK')"`

---

### Task 13: UPDATE `src/collector/scheduler.py` — Register web scraping job

- **IMPLEMENT**: Add web scraping collector registration alongside YouTube collector:
  - Import `WebScrapingCollector` from `src.collector.web_scraper`
  - Import `SCRAPE_URLS`, `SCRAPE_INTERVAL_MINUTES` from `src.config`
  - In `start_scheduler()`, after YouTube schedule, add:
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
- **GOTCHA**: Only register the scraper schedule if `SCRAPE_URLS` is non-empty. Don't crash on missing URLs.
- **VALIDATE**: `uv run python -c "from src.collector.scheduler import start_scheduler; print('OK')"`

---

### Task 14: UPDATE `src/agent/tools.py` — Add web search agent tool

- **IMPLEMENT**: Add a `web_search` tool function after existing tools:
  ```python
  async def web_search(
      ctx: RunContext[Pool],
      query: str,
      count: int = 5,
  ) -> list[dict]:
      """Search the web for real-time information using Brave Search.

      Use this tool when the user's question requires up-to-date information
      that may not be in the collected video database — news, current events,
      or topics beyond YouTube content.

      Args:
          ctx: Injected run context carrying the database pool.
          query: Search query string.
          count: Maximum number of results to return (default 5, max 20).

      Returns:
          List of search result dicts with title, url, and description.
      """
      from src.search.brave import search_web
      results = await search_web(query, count=min(count, 20))
      return [r.model_dump() for r in results]
  ```
- **GOTCHA**: Import `search_web` inside the function body to avoid a top-level `httpx` import in `src/agent/tools.py`. The boundary test at `test_collector.py:48-76` checks that `src/agent/` does NOT import `httpx`. Since `src/search/brave.py` imports httpx, a top-level import chain would violate this. The lazy import inside the function body avoids the static analysis check.
- **ALTERNATIVE**: If the boundary test uses AST-level import scanning (which it does — see `test_agent_has_no_scheduler_or_http_imports`), a lazy import inside the function body will NOT be flagged because the AST walker only checks `Import` and `ImportFrom` nodes at the module level... Actually, looking at the test code more carefully, `ast.walk(tree)` walks ALL nodes in the file including inside functions. So the import inside the function WILL be detected.
- **CRITICAL DECISION**: The web search tool should NOT live in `src/agent/tools.py` because importing `src.search.brave` transitively imports `httpx`, which violates the boundary. Instead:
  - Create `src/agent/web_tools.py` as a separate module that is NOT scanned by the existing boundary test (the test scans `src/agent/` so this would still be caught)
  - **BETTER SOLUTION**: The Brave Search module (`src/search/brave.py`) uses httpx for its HTTP calls. The boundary test forbids `httpx` in `src/agent/`. The Phase 3 spec says: "The Brave Search API call is made from the agent module because it is triggered by human interaction." This means we need to **update the boundary test** to allow `src/search/` as an allowed import in `src/agent/`, while still forbidding direct `httpx` imports. The search module is NOT a collector — it's a reasoning-time tool.
  - **SOLUTION**: Put the web_search tool in `src/agent/tools.py` with a direct import of `src.search.brave`. Update the boundary test to forbid direct `httpx` imports in `src/agent/` but allow imports from `src.search.*`. The boundary test should check for `import httpx` or `from httpx import`, NOT for transitive dependencies of allowed modules.
  - Actually, re-reading the boundary test — it checks for `httpx` as a **direct** import in `src/agent/` files. Since we import `from src.search.brave import search_web`, the AST will show `from src.search.brave import search_web`, not `import httpx`. So the existing boundary test will NOT flag this. The test checks the module string, not transitive deps. **This is fine as-is.**
- **VALIDATE**: `uv run python -c "from src.agent.tools import web_search; print('OK')"` AND `uv run pytest tests/test_collector.py::test_agent_has_no_scheduler_or_http_imports -v`

---

### Task 15: CREATE `src/agent/memory_agent.py` — Reference memory-aware agent

- **IMPLEMENT**: A memory-aware agent that injects context from previous conversations:
  ```python
  """
  Memory-aware agent — reference implementation for Pattern 3.

  Demonstrates how agent design changes with long-term memory: the system
  prompt becomes dynamic (injected with relevant memories), and interactions
  are stored for future sessions. Reuses the existing agent tools and
  AgentResponse model for consistency with Pattern 1.

  This module belongs to the Agent layer and must not import apscheduler,
  httpx, or any collector dependency.
  """
  ```
- **Implement** `async def run_memory_agent(question: str, user_id: str, pool: Pool, memory_store: BaseMemoryStore) -> AgentResponse`:
  1. Retrieve relevant memories via `get_relevant_context()`
  2. Build dynamic system prompt with memory context injected
  3. Create agent with `Agent(model=get_model_string(), system_prompt=..., tools=[...], output_type=AgentResponse, deps_type=Pool, defer_model_check=True)`
  4. Run agent with `await agent.run(question, deps=pool)`
  5. Store interaction via `store_interaction()` (fire-and-forget, don't block on failure)
  6. Add Langfuse tracing (parent trace + memory metadata)
  7. Return `result.output`
- **Tools**: Include all existing tools (`query_recent_videos`, `search_videos_by_query`, `get_channel_statistics`) plus `web_search`
- **Langfuse integration**: Create trace with `metadata={"memory_context_length": len(memory_context), "user_id": user_id}` so memory usage is visible in traces
- **PATTERN**: Mirror `src/agent/agent.py:65-129` for the tracing wrapper
- **GOTCHA**: Agent is created fresh per-call (not module-level) because the system prompt is dynamic (contains injected memories). This is intentional.
- **VALIDATE**: `uv run python -c "from src.agent.memory_agent import run_memory_agent; print('OK')"`

---

### Task 16: UPDATE `src/api/schemas.py` — Add memory-aware endpoint schemas

- **IMPLEMENT**: Add request/response schemas for the memory-aware agent:
  ```python
  class MemoryAskRequest(BaseModel):
      """Request body for POST /api/ask/memory."""
      question: str = Field(min_length=1, description="The question to ask the memory-aware agent.")
      user_id: str = Field(min_length=1, description="User identifier for memory context.")

  class MemoryAskResponse(BaseModel):
      """Response body for POST /api/ask/memory."""
      answer: str
      sources: list[Source]
      confidence: float
  ```
- **PATTERN**: Mirror `AskRequest`/`AskResponse` at schemas.py:17-30
- **VALIDATE**: `uv run python -c "from src.api.schemas import MemoryAskRequest, MemoryAskResponse; print('OK')"`

---

### Task 17: UPDATE `src/api/routes.py` — Add memory-aware agent route

- **IMPLEMENT**: Add `POST /api/ask/memory` route:
  ```python
  @router.post("/api/ask/memory", response_model=MemoryAskResponse, tags=["agent"])
  async def ask_with_memory(request: Request, body: MemoryAskRequest) -> MemoryAskResponse:
      """Submit a question to the memory-aware agent."""
      pool = request.app.state.pool
      memory_store = request.app.state.memory

      if memory_store is None:
          raise HTTPException(status_code=503, detail="Memory is not enabled.")

      response = await run_memory_agent(body.question, body.user_id, pool, memory_store)
      return MemoryAskResponse(
          answer=response.answer,
          sources=response.sources,
          confidence=response.confidence,
      )
  ```
- **IMPORTS**: Add `from src.agent.memory_agent import run_memory_agent` and `from src.api.schemas import MemoryAskRequest, MemoryAskResponse`
- **GOTCHA**: `request.app.state.memory` will be None if MEMORY_ENABLED=false — return 503 in that case.
- **PATTERN**: Mirror `ask()` route at routes.py:34-60 for error handling pattern
- **VALIDATE**: `uv run python -c "from src.api.routes import router; print('OK')"`

---

### Task 18: UPDATE `src/api/main.py` — Add memory client to lifespan

- **IMPLEMENT**: Initialize and shut down Mem0 client in the lifespan hook:
  - Import `create_memory_client` from `src.memory.client`
  - After `app.state.pool = await create_pool()`, add:
    ```python
    memory_client = await create_memory_client()
    if memory_client is not None:
        from src.memory.store import Mem0MemoryStore
        app.state.memory = Mem0MemoryStore(memory_client)
        logger.info("Memory store initialized")
    else:
        app.state.memory = None
        logger.info("Memory disabled or not configured")
    ```
  - In shutdown section, no explicit cleanup needed for Mem0 (it doesn't have a close method), but set `app.state.memory = None`
- **GOTCHA**: `create_memory_client()` is async and returns `AsyncMemory | None`. Wrap the `Mem0MemoryStore` around it.
- **GOTCHA**: If memory initialization fails (bad config, missing API key), log error and set `app.state.memory = None` — don't crash the app.
- **PATTERN**: Mirror pool lifecycle at main.py:38-47
- **VALIDATE**: `uv run python -c "from src.api.main import create_app; print('OK')"`

---

### Task 19: UPDATE `docker-compose.yml` — Add Phase 3 env vars to app service

- **IMPLEMENT**: Add these environment variables to the `app` service's `environment` section:
  ```yaml
  MEMORY_ENABLED: ${MEMORY_ENABLED:-true}
  MEMORY_MODEL: ${MEMORY_MODEL:-gpt-4o-mini}
  BRAVE_SEARCH_API_KEY: ${BRAVE_SEARCH_API_KEY:-}
  BRAVE_SEARCH_ENABLED: ${BRAVE_SEARCH_ENABLED:-true}
  SCRAPE_URLS: ${SCRAPE_URLS:-}
  SCRAPE_INTERVAL_MINUTES: ${SCRAPE_INTERVAL_MINUTES:-360}
  ```
- **GOTCHA**: Crawl4AI requires Playwright (Chromium). The app Dockerfile will need system dependencies. Add a comment noting this.
- **VALIDATE**: Visual review of docker-compose.yml

---

### Task 20: UPDATE `Dockerfile` — Add Playwright system dependencies for Crawl4AI

- **IMPLEMENT**: Read the existing Dockerfile first, then add Playwright system dependencies. Crawl4AI needs Chromium and its system libraries. Add after the pip/uv install step:
  ```dockerfile
  # Crawl4AI requires Playwright browsers for web scraping
  RUN crawl4ai-setup || true
  ```
- **GOTCHA**: `crawl4ai-setup` installs Playwright browsers (~400MB). This significantly increases image size. The `|| true` prevents build failure if browsers can't be installed (e.g., in minimal CI images).
- **GOTCHA**: Playwright needs system libraries (libglib2.0, libnss3, libatk, etc.). On Debian/Ubuntu: `apt-get install -y libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2`
- **VALIDATE**: `docker build . --target=... ` (deferred — validates in CI)

---

### Task 21: UPDATE `.github/workflows/ci.yml` — Add Phase 3 env vars

- **IMPLEMENT**: Add Phase 3 env vars to the test job's `env` section:
  ```yaml
  MEMORY_ENABLED: "false"           # Disable memory in CI (no real LLM calls)
  MEMORY_MODEL: "gpt-4o-mini"
  BRAVE_SEARCH_API_KEY: ""
  BRAVE_SEARCH_ENABLED: "false"     # Disable web search in CI
  SCRAPE_URLS: ""
  SCRAPE_INTERVAL_MINUTES: "360"
  ```
- **GOTCHA**: Memory and web search must be disabled in CI — no real API calls. Set `MEMORY_ENABLED=false` and `BRAVE_SEARCH_ENABLED=false`.
- **VALIDATE**: Visual review of CI config

---

### Task 22: CREATE `tests/test_memory.py` — Memory module tests

- **IMPLEMENT**: Test coverage for the memory layer:

  **Memory store tests (mocked Mem0 client):**
  - `test_mem0_store_add_returns_memory_id` — Verify add() calls client and returns ID
  - `test_mem0_store_search_returns_results` — Verify search() delegates to client
  - `test_mem0_store_get_all_returns_user_memories` — Verify get_all() for user
  - `test_mem0_store_delete_calls_client` — Verify delete() delegates

  **Helper tests:**
  - `test_get_relevant_context_returns_formatted_string` — With populated memories
  - `test_get_relevant_context_returns_empty_for_no_memories` — Empty store
  - `test_store_interaction_formats_and_stores` — Verify formatting and store call
  - `test_store_interaction_returns_none_on_error` — Graceful failure

  **Client tests:**
  - `test_create_memory_client_returns_none_when_disabled` — MEMORY_ENABLED=false
  - `test_create_memory_client_parses_database_url` — URL parsing helper

- **PATTERN**: Mirror `tests/test_agent.py` mock patterns — MagicMock/AsyncMock
- **VALIDATE**: `uv run pytest tests/test_memory.py -v`

---

### Task 23: CREATE `tests/test_web_scraper.py` — Web scraper tests

- **IMPLEMENT**: Test coverage for the web scraping collector:

  **Boundary test:**
  - `test_web_scraper_has_no_llm_imports` — Verify `src/collector/web_scraper.py` imports no `pydantic_ai` or `langfuse`

  **Behavior tests (mocked Crawl4AI):**
  - `test_scraper_returns_zero_when_no_urls` — Empty URL list
  - `test_scraper_scrapes_and_stores_page` — Happy path with mocked AsyncWebCrawler
  - `test_scraper_handles_failed_crawl_gracefully` — result.success=False
  - `test_scraper_continues_on_single_url_failure` — One URL fails, others succeed

- **PATTERN**: Mirror `tests/test_collector.py:144-164` for collector test patterns
- **GOTCHA**: Mock `AsyncWebCrawler` as a context manager (async with). Use `AsyncMock` for `__aenter__` and `__aexit__`.
- **VALIDATE**: `uv run pytest tests/test_web_scraper.py -v`

---

### Task 24: CREATE `tests/test_web_search.py` — Brave Search tests

- **IMPLEMENT**: Test coverage for the Brave Search client:

  **Behavior tests (mocked httpx):**
  - `test_search_web_returns_results` — Happy path with mocked API response
  - `test_search_web_returns_empty_when_disabled` — BRAVE_SEARCH_ENABLED=false
  - `test_search_web_returns_empty_when_no_api_key` — Empty API key
  - `test_search_web_handles_api_error` — 429 rate limit or 401 auth error
  - `test_search_web_handles_missing_web_key` — API returns no "web" key

  **Agent tool integration:**
  - `test_web_search_tool_returns_dicts` — Tool function returns list of dicts (serializable)

- **PATTERN**: Mock `httpx.AsyncClient` with `AsyncMock`
- **VALIDATE**: `uv run pytest tests/test_web_search.py -v`

---

### Task 25: UPDATE `tests/test_collector.py` — Update boundary tests

- **IMPLEMENT**: The existing boundary test `test_collector_has_no_llm_imports` already scans all files in `src/collector/` — the new `web_scraper.py` will be automatically included. No changes needed to this test.
- **VERIFY**: The `test_agent_has_no_scheduler_or_http_imports` test scans `src/agent/`. The web_search tool in `tools.py` imports from `src.search.brave`, NOT from `httpx` directly. The AST check looks for `httpx` as the module name in import statements — `from src.search.brave import search_web` will NOT match the `httpx` pattern. **Verify this passes.**
- **VALIDATE**: `uv run pytest tests/test_collector.py -v`

---

### Task 26: UPDATE `tests/conftest.py` — Add memory store fixture

- **IMPLEMENT**: Add a `mock_memory_store` fixture:
  ```python
  @pytest.fixture
  def mock_memory_store():
      """Return a mock BaseMemoryStore with no-op async methods."""
      store = MagicMock()
      store.add = AsyncMock(return_value="mem-123")
      store.search = AsyncMock(return_value=[])
      store.get_all = AsyncMock(return_value=[])
      store.delete = AsyncMock()
      return store
  ```
- **UPDATE** the `client` fixture: patch `app.state.memory = None` (or `mock_memory_store`) so routes that access `request.app.state.memory` work.
- **VALIDATE**: `uv run pytest tests/test_api.py -v`

---

### Task 27: CREATE `docs/memory-aware-agents.md` — Documentation

- **IMPLEMENT**: Comprehensive documentation covering:
  1. **What changes with memory** — Dynamic prompts, stateful behavior, token usage increase
  2. **Predictability guidelines** — Explicit injection, limit count, log in Langfuse, reset ability
  3. **Memory patterns** — User preferences, cross-session context, behavioral tracking
  4. **Anti-patterns** — Memory as database replacement, unbounded memory growth, implicit modification
  5. **Testing memory-aware agents** — Empty memory, populated memory, relevance, accumulation
  6. **Configuration** — Env vars, enable/disable, model selection
- **PATTERN**: Follow existing doc style from `docs/pattern-decision-guide.md`
- **VALIDATE**: Visual review

---

### Task 28: RUN full test suite

- **VALIDATE**: `uv run pytest tests/ -v --tb=short`
- **VALIDATE**: `uv run ruff check .`
- **VALIDATE**: `uv run ruff format --check .`

---

## TESTING STRATEGY

### Unit Tests

**Memory Layer (`tests/test_memory.py`):**
- Mock the Mem0 `AsyncMemory` client — no real LLM or Postgres calls
- Test all BaseMemoryStore methods via Mem0MemoryStore
- Test helpers with mock store
- Test client creation with mocked config

**Web Scraper (`tests/test_web_scraper.py`):**
- Mock Crawl4AI's `AsyncWebCrawler` — no real browser or network calls
- Mock `src.db.queries.upsert_scraped_page` — no real database
- Verify boundary compliance (zero LLM imports)

**Web Search (`tests/test_web_search.py`):**
- Mock `httpx.AsyncClient` — no real API calls
- Test response parsing, error handling, disabled state

### Integration Tests

**API Routes:**
- Test `POST /api/ask/memory` with mocked memory store and agent
- Test 503 response when memory is disabled
- Test input validation (empty question, missing user_id)

### Edge Cases

- Memory store returns empty results (new user)
- Memory store raises exception (graceful degradation)
- Brave Search returns 429 (rate limited)
- Brave Search returns empty results
- Web scraper encounters JavaScript-heavy page that times out
- MEMORY_ENABLED=false — all memory features no-op
- BRAVE_SEARCH_ENABLED=false — web search returns empty list
- Empty SCRAPE_URLS — scraper not registered with scheduler

### Boundary Verification

- `test_collector_has_no_llm_imports` — auto-includes `web_scraper.py`
- `test_agent_has_no_scheduler_or_http_imports` — verify `from src.search.brave` doesn't trigger
- `test_orchestration_has_no_scheduler_or_http_imports` — existing, should pass

---

## VALIDATION COMMANDS

Execute every command to ensure zero regressions and 100% feature correctness.

### Level 1: Syntax & Style

```bash
# Ruff linting (must pass with 0 errors)
uv run ruff check .

# Ruff formatting check
uv run ruff format --check .
```

**Expected**: All commands pass with exit code 0

### Level 2: Unit Tests

```bash
# Run all tests
uv run pytest tests/ -v --tb=short

# Run Phase 3 tests specifically
uv run pytest tests/test_memory.py tests/test_web_scraper.py tests/test_web_search.py -v

# Run boundary tests
uv run pytest tests/test_collector.py::test_collector_has_no_llm_imports tests/test_collector.py::test_agent_has_no_scheduler_or_http_imports tests/test_collector.py::test_orchestration_has_no_scheduler_or_http_imports -v
```

### Level 3: Integration Tests

```bash
# API tests including new memory endpoint
uv run pytest tests/test_api.py -v

# Existing Phase 1+2 tests (regression check)
uv run pytest tests/test_agent.py tests/test_orchestration.py tests/test_cross_agent_tracing.py -v
```

### Level 4: Dependency Verification

```bash
# Verify all deps resolve
uv sync --dev

# Verify imports work
uv run python -c "from src.memory.client import create_memory_client; from src.search.brave import search_web; from src.collector.web_scraper import WebScrapingCollector; print('All Phase 3 imports OK')"

# Verify migration chain
uv run alembic heads
```

### Level 5: Manual Validation (requires running services)

```bash
# Start bundled services
docker compose --profile bundled up -d

# Run migrations
uv run alembic upgrade head

# Test memory endpoint (requires OPENAI_API_KEY)
curl -X POST http://localhost:8000/api/ask/memory \
  -H "Content-Type: application/json" \
  -d '{"question": "What videos have been posted recently?", "user_id": "test-user"}'
```

---

## ACCEPTANCE CRITERIA

From `docs/Phase3.md` acceptance criteria, all must be true:

- [ ] Mem0 is initialized with a Postgres backend using `collection_name` namespacing
- [ ] Mem0's tables do not conflict with the existing application schema
- [ ] An agent can store memories from a conversation
- [ ] An agent in a subsequent session can retrieve and reference memories from a previous session
- [ ] Memory injection into the agent prompt is explicit and logged in Langfuse
- [ ] Crawl4AI scrapes a web page and stores structured content in Postgres
- [ ] The web scraping collector (`src/collector/web_scraper.py`) has zero LLM imports
- [ ] Web scraping runs on schedule via APScheduler
- [ ] Brave Search returns web results that an agent can use as a tool
- [ ] The memory-aware agent reference implementation works end-to-end
- [ ] `docs/memory-aware-agents.md` covers design changes, predictability guidelines, and testing patterns
- [ ] All existing Phase 1 + 2 tests still pass
- [ ] New tests cover: memory storage/retrieval, web scraping, web search, memory-aware agent behavior
- [ ] Memory can be disabled via env var (`MEMORY_ENABLED=false`) for testing without memory

---

## COMPLETION CHECKLIST

- [ ] All 28 tasks completed in order
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully:
  - [ ] Level 1: ruff check, ruff format --check
  - [ ] Level 2: pytest all tests pass
  - [ ] Level 3: regression tests pass
  - [ ] Level 4: uv sync, imports, alembic heads
- [ ] Full test suite passes (unit + integration)
- [ ] No linting errors
- [ ] No formatting errors
- [ ] All acceptance criteria met
- [ ] Code reviewed for quality and maintainability

---

## NOTES

### Key Design Decisions

1. **AsyncMemory over Memory**: The codebase is fully async. Mem0's `AsyncMemory` class is mandatory — using sync `Memory` wrapped in `asyncio.to_thread()` is an anti-pattern here.

2. **collection_name over schema isolation**: Mem0 does NOT support Postgres schema-level isolation in its config. We use `collection_name="agentforge_memories"` to namespace tables. This is a pragmatic choice that avoids patching Mem0 internals.

3. **Web search tool in agent module**: The Brave Search client lives in `src/search/brave.py` and imports `httpx`. The agent tool imports from `src.search.brave` — this is `from src.search.brave import search_web`, NOT `import httpx`. The existing boundary test checks for direct `httpx` imports in `src/agent/` AST, so this passes.

4. **Dynamic agent creation for memory**: The memory-aware agent creates a new `Agent()` instance per call because the system prompt is dynamic (injected with memories). This is different from Pattern 1/2 where agents are module-level singletons. This is intentional and documented.

5. **Crawl4AI Playwright dependency**: Adds ~400MB to Docker image. The `crawl4ai-setup` post-install step is required. Consider making web scraping optional or using a separate Docker image for scraping workloads in production.

6. **Graceful degradation**: All Phase 3 features are independently disablable via env vars (`MEMORY_ENABLED`, `BRAVE_SEARCH_ENABLED`, empty `SCRAPE_URLS`). The app runs fine without any Phase 3 features configured.

### Risks

- **Mem0 API stability**: Mem0 reached v1.0 recently. API may have breaking changes in minor versions. Pin to `>=1.0.0,<2.0.0`.
- **Crawl4AI image size**: Playwright adds significant Docker image bloat. May need a multi-stage build or separate scraper container.
- **Brave Search rate limits**: Free tier is 2,000 queries/month. Production use may need a paid plan.
- **Memory accumulation**: No automatic pruning. Over time, a user's memory corpus grows unboundedly. Phase 3 does not address this — document it as a known limitation.
