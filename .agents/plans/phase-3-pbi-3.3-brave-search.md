# PBI 3.3 — Brave Search API (Web Search for Agents)

The following plan should be complete, but validate documentation and codebase patterns before implementing.

## Feature Description

Add real-time web search as an agent tool via the Brave Search API. Agents can search the web during reasoning when the user's question requires information beyond the collected video database. The search client lives in a new `src/search/` module; the agent tool is registered alongside existing tools.

## User Story

As a Python developer building AI agents
I want my agents to search the web in real-time during conversations
So that they can answer questions about current events or topics not covered by collected data

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Low-Medium
**Primary Systems Affected**: `src/search/` (new), `src/agent/tools.py`, `src/config.py`
**Dependencies**: `httpx` (existing)
**Branch**: `feat/pbi-3.3-brave-search` (from `main`)
**Prerequisite PBIs**: None (independent of 3.1 and 3.2)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING!

- `CLAUDE.md` — Coding conventions, boundary rules. READ FIRST.
- `docs/Phase3.md` (lines 306-367) — PBI 3.3 specification
- `src/config.py` (lines 1-91) — Config pattern for new env vars
- `src/agent/tools.py` (lines 1-94) — Pydantic AI tool pattern: `RunContext[Pool]` first arg, docstrings, delegation to query layer
- `src/agent/agent.py` (lines 39-62) — Agent definition with tools list
- `src/agent/research_agent.py` (lines 41-59) — Agent with tools list pattern
- `tests/test_agent.py` (lines 182-214) — Tool delegation test pattern
- `tests/test_collector.py` (lines 48-76) — Boundary test: `test_agent_has_no_scheduler_or_http_imports` — scans `src/agent/` for `httpx` imports via AST
- `.env.example` — Env var documentation pattern

### New Files to Create

- `src/search/__init__.py` — Package init
- `src/search/brave.py` — Brave Search API async client
- `tests/test_web_search.py` — Brave Search + tool tests

### Files to Modify

- `src/config.py` — Add `BRAVE_SEARCH_API_KEY`, `BRAVE_SEARCH_ENABLED`
- `.env.example` — Document search env vars
- `src/agent/tools.py` — Add `web_search` tool function
- `src/agent/agent.py` — Add `web_search` to Pattern 1 agent tools list (optional, or only for memory agent in PBI 3.4)
- `docker-compose.yml` — Add search env vars
- `.github/workflows/ci.yml` — Add search env vars (disabled)

### Relevant Documentation — READ BEFORE IMPLEMENTING!

- [Brave Search API — Get Started](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started)
  - Endpoint URL, required headers, query params
  - Why: Core API integration
- [Brave Search API — Rate Limiting](https://api-dashboard.search.brave.com/documentation/guides/rate-limiting)
  - Free tier: 2,000 queries/month, 1 query/sec burst
  - Why: Error handling for 429 responses

### Patterns to Follow

**Agent Tool Pattern** (from `src/agent/tools.py`):
```python
async def query_recent_videos(
    ctx: RunContext[Pool],
    channel_id: str,
    limit: int = 10,
) -> list[VideoSummary]:
    """Fetch the most recently published videos for a YouTube channel.

    Use this tool when the user asks about recent uploads...
    """
    ...
```

**Config Pattern** (from `src/config.py`):
```python
BRAVE_SEARCH_API_KEY: str = os.getenv("BRAVE_SEARCH_API_KEY", "")
```

---

## STEP-BY-STEP TASKS

### Task 1: UPDATE `src/config.py` — Add Brave Search env vars

- **IMPLEMENT**: Add after the Memory section (or after Collector if PBI 3.1 hasn't landed yet):
  ```python
  # ---------------------------------------------------------------------------
  # Web Search (Phase 3)
  # ---------------------------------------------------------------------------
  BRAVE_SEARCH_API_KEY: str = os.getenv("BRAVE_SEARCH_API_KEY", "")
  BRAVE_SEARCH_ENABLED: bool = os.getenv("BRAVE_SEARCH_ENABLED", "true").lower() == "true"
  ```
- **VALIDATE**: `uv run python -c "from src.config import BRAVE_SEARCH_API_KEY, BRAVE_SEARCH_ENABLED; print('OK')"`

---

### Task 2: UPDATE `.env.example` — Document search env vars

- **IMPLEMENT**: Append:
  ```env
  # -----------------------------------------------------------------------------
  # Web Search (Phase 3)
  # Brave Search API — https://brave.com/search/api/
  # Free tier: 2,000 queries/month. Set BRAVE_SEARCH_ENABLED=false to disable.
  # -----------------------------------------------------------------------------
  BRAVE_SEARCH_API_KEY=BSA-...
  BRAVE_SEARCH_ENABLED=true
  ```
- **VALIDATE**: Visual review

---

### Task 3: CREATE `src/search/__init__.py` — Package init

- **IMPLEMENT**:
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

### Task 4: CREATE `src/search/brave.py` — Brave Search API client

- **IMPLEMENT**:
  ```python
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
  ```
- **GOTCHA**: `data.get("web", {}).get("results", [])` — the `web` key may be absent.
- **GOTCHA**: Set `timeout=10.0` — don't hang indefinitely on Brave API.
- **GOTCHA**: Never raise to callers. Log and return empty list. Search failure should degrade gracefully.
- **VALIDATE**: `uv run python -c "from src.search.brave import search_web, SearchResult, WebSearchError; print('OK')"`

---

### Task 5: UPDATE `src/agent/tools.py` — Add web_search tool

- **IMPLEMENT**: Add after existing tools:
  ```python
  async def web_search(
      ctx: RunContext[Pool],
      query: str,
      count: int = 5,
  ) -> list[dict]:
      """Search the web for real-time information using Brave Search.

      Use this tool when the user's question requires up-to-date information
      not available in the collected video database — current events, recent
      news, or topics beyond YouTube content.

      Args:
          ctx: Injected run context carrying the database pool.
          query: Search query string.
          count: Maximum number of results to return (default 5, max 20).

      Returns:
          List of search result dicts with title, url, and description.
      """
      from src.search.brave import search_web as brave_search

      logger.debug("Tool: web_search", extra={"query": query})
      results = await brave_search(query, count=min(count, 20))
      return [r.model_dump() for r in results]
  ```
- **CRITICAL**: Import `search_web` inside the function body. The boundary test at `tests/test_collector.py:48-76` uses `ast.walk()` to scan ALL import nodes in `src/agent/` files. A top-level `from src.search.brave import search_web` would NOT directly import `httpx`, but the lazy import is cleaner and avoids any future boundary confusion. However — re-reading the test, it checks for `httpx` and `apscheduler` as module names, not transitive deps. `from src.search.brave import search_web` at the top level would show `src.search.brave` as the module, which does NOT match `httpx`. **Either approach works**, but the lazy import is more defensive.
- **GOTCHA**: Returns `list[dict]` (serializable), not `list[SearchResult]`. Pydantic AI tools must return JSON-serializable types for the LLM.
- **VALIDATE**: `uv run python -c "from src.agent.tools import web_search; print('OK')"` AND `uv run pytest tests/test_collector.py::test_agent_has_no_scheduler_or_http_imports -v`

---

### Task 6: UPDATE `docker-compose.yml` — Add search env vars

- **IMPLEMENT**: Add to `app` service `environment`:
  ```yaml
  BRAVE_SEARCH_API_KEY: ${BRAVE_SEARCH_API_KEY:-}
  BRAVE_SEARCH_ENABLED: ${BRAVE_SEARCH_ENABLED:-true}
  ```
- **VALIDATE**: Visual review

---

### Task 7: UPDATE `.github/workflows/ci.yml` — Add search env vars (disabled)

- **IMPLEMENT**: Add to test job `env`:
  ```yaml
  BRAVE_SEARCH_API_KEY: ""
  BRAVE_SEARCH_ENABLED: "false"
  ```
- **VALIDATE**: Visual review

---

### Task 8: CREATE `tests/test_web_search.py` — Brave Search tests

- **IMPLEMENT**:
  ```python
  """
  Web search module tests.

  Covers the Brave Search API client and the web_search agent tool.
  All HTTP calls are mocked — no real API calls are made.
  """

  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest
  ```

  **Brave Search client tests (mock httpx):**
  - `test_search_web_returns_results`:
    ```python
    async def test_search_web_returns_results():
        """search_web returns SearchResult list from Brave API response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Result 1", "url": "https://example.com/1", "description": "Desc 1"},
                    {"title": "Result 2", "url": "https://example.com/2", "description": "Desc 2"},
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
    ```
  - `test_search_web_returns_empty_when_disabled` — `BRAVE_SEARCH_ENABLED=False`
  - `test_search_web_returns_empty_when_no_api_key` — Empty API key
  - `test_search_web_returns_empty_on_http_error` — 429 / 401
  - `test_search_web_returns_empty_on_request_error` — Network failure
  - `test_search_web_handles_missing_web_key` — API response without `web` key

  **Agent tool test:**
  - `test_web_search_tool_returns_serializable_dicts`:
    ```python
    async def test_web_search_tool_returns_serializable_dicts(mock_pool):
        """web_search tool returns list of dicts (JSON-serializable for LLM)."""
        from unittest.mock import MagicMock
        from pydantic_ai import RunContext
        from src.search.brave import SearchResult

        mock_results = [
            SearchResult(title="T1", url="https://example.com", description="D1")
        ]

        ctx = MagicMock(spec=RunContext)
        ctx.deps = mock_pool

        with patch("src.agent.tools.brave_search", AsyncMock(return_value=mock_results)):
            from src.agent.tools import web_search
            results = await web_search(ctx, query="test")

        assert isinstance(results, list)
        assert isinstance(results[0], dict)
        assert results[0]["title"] == "T1"
    ```

- **VALIDATE**: `uv run pytest tests/test_web_search.py -v`

---

### Task 9: RUN full validation

- **VALIDATE**:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  uv run pytest tests/ -v --tb=short
  uv run pytest tests/test_collector.py::test_agent_has_no_scheduler_or_http_imports -v
  ```

---

## TESTING STRATEGY

### Unit Tests
- Mock `httpx.AsyncClient` — no real HTTP calls
- Test response parsing, error handling, disabled state, missing keys

### Edge Cases
- `BRAVE_SEARCH_ENABLED=false` → empty list, no HTTP call
- Empty API key → empty list with warning
- 429 rate limit → empty list with error log
- 401 auth error → empty list with error log
- Network timeout → empty list with error log
- Response missing `web` key → empty list
- Response `web.results` is empty → empty list

---

## ACCEPTANCE CRITERIA

- [ ] `BRAVE_SEARCH_API_KEY` and `BRAVE_SEARCH_ENABLED` config vars exist
- [ ] `search_web()` returns typed `SearchResult` models from Brave API
- [ ] `search_web()` returns empty list on any error (never raises)
- [ ] `web_search` agent tool registered and returns serializable dicts
- [ ] Boundary test `test_agent_has_no_scheduler_or_http_imports` still passes
- [ ] Web search disabled in CI via `BRAVE_SEARCH_ENABLED=false`
- [ ] All existing tests still pass
- [ ] New tests cover: success, disabled, no key, HTTP errors, missing keys

---

## NOTES

- **No new pip dependency**: Brave Search uses `httpx` which is already in `pyproject.toml`.
- **Lazy import in tool**: The `from src.search.brave import search_web` is inside the function body as a defensive pattern. The boundary test checks for `httpx` as a direct import module name — `src.search.brave` doesn't match — but the lazy import is cleaner.
- **Never raises**: `search_web()` catches all exceptions and returns empty list. Agent tools should degrade gracefully — a failed web search shouldn't crash the entire agent run.
