# Feature: Phase 4 — Local AI & Caching

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Phase 4 adds three infrastructure capabilities that enable fully local, privacy-first agent workflows where no data leaves the machine:

1. **Ollama** — Local LLM serving via Docker. Run open-source models as a drop-in replacement for OpenAI/Groq by changing two env vars.
2. **SearXNG** — Self-hosted meta-search engine. Agents search the web without external API calls or API keys.
3. **Redis/Valkey** — Caching layer for measured bottlenecks. Disabled by default; only activated when a specific performance issue is documented.

After Phase 4, the entire AgentForge stack (model inference, web search, memory, tools) runs on a local machine with zero external dependencies.

## User Story

As a Python developer building AI agents
I want to run the entire stack locally without external API dependencies
So that I can develop in privacy-first environments, avoid API costs, and share GPU resources across projects on a dedicated server

## Problem Statement

Phases 1–3 require cloud API keys (OpenAI/Groq for LLM, Brave for search). Developers who want local-only workflows, privacy compliance, or cost-free development cannot use the kit without external dependencies.

## Solution Statement

Add Ollama as a third LLM provider (drop-in via env vars), SearXNG as an alternative search backend (routed via `SEARCH_PROVIDER` config), and Redis as an opt-in caching layer. All three are Docker services behind profiles — fully optional and zero-config for developers who don't need them.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `src/config.py`, `src/search/`, `src/agent/tools.py`, `src/cache/` (new), `docker-compose.yml`, `.env.example`, `src/api/main.py`
**Dependencies**: Ollama Docker image, SearXNG Docker image, Redis Docker image, `redis` Python package

---

## CONTEXT REFERENCES

### Relevant Codebase Files — MUST READ BEFORE IMPLEMENTING

- `src/config.py` (full file) — Why: Must add `OLLAMA_HOST`, `SEARCH_PROVIDER`, `SEARXNG_HOST`, `REDIS_URL`, `CACHE_ENABLED` config vars. Must update `get_model_string()` for Ollama. Must update `SUPPORTED_PROVIDERS` frozenset. Must update `validate_provider_config()`.
- `src/search/brave.py` (full file) — Why: SearXNG client (`src/search/searxng.py`) must mirror this module's structure: same `SearchResult` model (or import it), same error handling pattern (return `[]` on failure, never raise), same logging.
- `src/agent/tools.py` (lines 96-119) — Why: The `web_search` tool currently hardcodes Brave. Must be refactored to route based on `SEARCH_PROVIDER` config — either Brave or SearXNG.
- `src/api/main.py` (full file) — Why: Lifespan hook must add Redis pool creation/teardown. Store cache pool in `app.state.cache`.
- `docker-compose.yml` (full file) — Why: Must add Ollama, SearXNG, and Redis services with correct profiles.
- `.env.example` (full file) — Why: Must add all Phase 4 env vars with comments.
- `src/search/__init__.py` — Why: Must update module docstring to cover SearXNG.
- `tests/test_web_search.py` (full file) — Why: Pattern to follow for SearXNG tests. Same mock structure (mock httpx client, mock responses).
- `tests/conftest.py` (full file) — Why: Must add `mock_cache` fixture. Must add Phase 4 env vars to CI config awareness.
- `.github/workflows/ci.yml` (full file) — Why: Must add Phase 4 env vars (`SEARCH_PROVIDER`, `CACHE_ENABLED`, etc.) to the test job environment.
- `src/memory/client.py` (full file) — Why: Shows the pattern for optional infrastructure — how to handle disabled state gracefully. Cache client should follow the same pattern.
- `Dockerfile` (full file) — Why: No changes needed (Ollama/SearXNG/Redis are separate Docker services), but verify no build step breaks.
- `src/agent/agent.py` (full file) — Why: Uses `get_model_string()` — must verify Ollama model strings work without code changes here.
- `src/agent/memory_agent.py` (full file) — Why: Also uses `get_model_string()` — same verification.
- `src/collector/scheduler.py` (full file) — Why: No changes needed, but verify no conflicts.

### New Files to Create

- `src/search/searxng.py` — SearXNG search client (mirrors `src/search/brave.py` structure)
- `src/cache/__init__.py` — Cache layer package init
- `src/cache/client.py` — Redis/Valkey async connection pool and cache helpers
- `config/searxng/settings.yml` — SearXNG server configuration (JSON API enabled)
- `scripts/pull_model.py` — Helper script to pull models into Ollama
- `tests/test_searxng.py` — SearXNG client tests (mirrors `tests/test_web_search.py`)
- `tests/test_cache.py` — Cache client tests
- `tests/test_ollama_provider.py` — Ollama provider config tests
- `docs/local-ai-guide.md` — Running fully local with Ollama + SearXNG
- `docs/gpu-sharing.md` — Ollama GPU sharing on dedicated servers

### Relevant Documentation — READ BEFORE IMPLEMENTING

- Pydantic AI models documentation — Ollama provider support
  - Pydantic AI supports `ollama:model-name` as a model string (e.g. `"ollama:llama3.1:8b"`) — auto-selects `OllamaProvider`
  - When using the model string approach, Pydantic AI reads `OLLAMA_BASE_URL` env var to find the Ollama server
  - Under the hood, Ollama uses `OpenAIChatModel` + `OllamaProvider` (Ollama exposes an OpenAI-compatible API)
  - Alternative explicit approach: `OpenAIChatModel(model_name="llama3.1:8b", provider=OllamaProvider(base_url="http://localhost:11434/v1"))`
  - No pip extra or separate package needed — built into `pydantic-ai`
  - Why: The model string approach (`get_model_string()` returning `"ollama:model-name"`) is simplest and requires only setting `OLLAMA_BASE_URL` env var
- SearXNG JSON API — https://docs.searxng.org/dev/search_api.html
  - Endpoint: `GET /search?q=query&format=json` (also supports POST)
  - Response: `{"results": [{"title": "...", "url": "...", "content": "..."}]}`
  - Note: SearXNG uses `content` for the snippet text (not `description` or `snippet`). Field name may vary by engine — always use `.get("content", "")` with fallback.
  - Why: Must know exact JSON field names for parsing
- Redis async Python — `redis` package v7.x (`redis.asyncio`)
  - `redis.asyncio.from_url(url, decode_responses=True)` creates an async Redis client
  - `await client.get(key)`, `await client.set(key, value, ex=ttl)` for basic ops
  - `await client.aclose()` for cleanup (use `aclose()` not `close()` — `close()` is deprecated in v7+)
  - No separate `aioredis` package needed — `redis.asyncio` is built-in since v4.2+
  - Why: Need async Redis patterns that fit the existing asyncpg pool pattern

### Patterns to Follow

**Config Pattern** (from `src/config.py`):
```python
# Module-level constants loaded from env
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
SEARCH_PROVIDER: str = os.getenv("SEARCH_PROVIDER", "brave")
```

**Search Client Pattern** (from `src/search/brave.py`):
- Module-level docstring with layer identification
- `SearchResult` Pydantic model for typed results
- Custom exception class (e.g., `SearXNGSearchError`)
- Main function returns `list[SearchResult]`, never raises — returns `[]` on failure
- Uses `httpx.AsyncClient` for HTTP calls
- Logs results count on success, logs errors on failure

**Optional Service Pattern** (from `src/memory/client.py`):
- Check enabled flag before initialising
- Return `None` when disabled
- Log why it's disabled
- Caller stores in `app.state` and checks for `None` before use

**Lifespan Pattern** (from `src/api/main.py`):
- Create resource in startup, store in `app.state`
- Tear down in shutdown (reverse order)
- Wrap in try/except with graceful degradation

**Test Pattern** (from `tests/test_web_search.py`):
- Mock httpx client with `AsyncMock`
- Patch module-level config values
- Test success path, disabled path, missing key path, HTTP error path, network error path

**Error Handling Pattern**:
- Domain-specific exception classes defined in the module
- Functions catch and log errors, return safe defaults
- Never let infrastructure failures crash the agent

**Naming Conventions**:
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Config vars match env var names

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — Configuration & Docker Infrastructure

Update configuration, Docker Compose, and env vars to support Ollama, SearXNG, and Redis. No Python code changes beyond config.

**Tasks:**
- Add Ollama, SearXNG, Redis config vars to `src/config.py`
- Update `SUPPORTED_PROVIDERS` to include `"ollama"`
- Update `get_model_string()` for Ollama provider
- Update `validate_provider_config()` for Ollama
- Add Docker services to `docker-compose.yml`
- Create SearXNG config file (`config/searxng/settings.yml`)
- Update `.env.example` with all Phase 4 vars
- Create `scripts/pull_model.py`

### Phase 2: Core Implementation — SearXNG & Unified Search

Build the SearXNG client and refactor the web_search tool to route between Brave and SearXNG.

**Tasks:**
- Create `src/search/searxng.py`
- Update `src/search/__init__.py` docstring
- Refactor `src/agent/tools.py` `web_search` to route by `SEARCH_PROVIDER`

### Phase 3: Core Implementation — Redis/Valkey Cache Layer

Build the async cache client with opt-in pattern (disabled by default).

**Tasks:**
- Create `src/cache/__init__.py`
- Create `src/cache/client.py`
- Update `src/api/main.py` lifespan to manage cache pool
- Update `tests/conftest.py` with cache fixture and patching

### Phase 4: CI & Environment

Update CI pipeline and ensure all env vars are configured for tests.

**Tasks:**
- Update `.github/workflows/ci.yml` with Phase 4 env vars

### Phase 5: Testing

Write tests for all new components.

**Tasks:**
- Create `tests/test_ollama_provider.py`
- Create `tests/test_searxng.py`
- Create `tests/test_cache.py`

### Phase 6: Documentation

Write guides for local AI workflows and GPU sharing.

**Tasks:**
- Create `docs/local-ai-guide.md`
- Create `docs/gpu-sharing.md`

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: UPDATE `src/config.py` — Add Phase 4 configuration

- **IMPLEMENT**: Add the following constants after the Web Search section:
  ```python
  # ---------------------------------------------------------------------------
  # Ollama (Phase 4)
  # ---------------------------------------------------------------------------
  OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

  # ---------------------------------------------------------------------------
  # Search Provider (Phase 4)
  # ---------------------------------------------------------------------------
  SEARCH_PROVIDER: str = os.getenv("SEARCH_PROVIDER", "brave")

  # ---------------------------------------------------------------------------
  # SearXNG (Phase 4)
  # ---------------------------------------------------------------------------
  SEARXNG_HOST: str = os.getenv("SEARXNG_HOST", "http://localhost:8080")

  # ---------------------------------------------------------------------------
  # Caching (Phase 4)
  # ---------------------------------------------------------------------------
  CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "false").lower() == "true"
  REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
  ```
- **IMPLEMENT**: Update `SUPPORTED_PROVIDERS` to include `"ollama"`:
  ```python
  SUPPORTED_PROVIDERS: frozenset[str] = frozenset({"openai", "groq", "ollama"})
  ```
- **IMPLEMENT**: Update `get_model_string()` to handle Ollama. Pydantic AI accepts `"ollama:model-name"` as a model string, so the existing `f"{MODEL_PROVIDER}:{MODEL_NAME}"` pattern already works. However, Ollama needs `OLLAMA_BASE_URL` or explicit base_url. The simplest approach: set `OLLAMA_BASE_URL` env var in the environment from `OLLAMA_HOST`. Add this at module level after OLLAMA_HOST:
  ```python
  # Pydantic AI's OllamaModel reads OLLAMA_BASE_URL from the environment.
  # Mirror OLLAMA_HOST so developers only configure one variable.
  if MODEL_PROVIDER == "ollama" and not os.getenv("OLLAMA_BASE_URL"):
      os.environ["OLLAMA_BASE_URL"] = OLLAMA_HOST
  ```
- **IMPLEMENT**: Update `validate_provider_config()` — add Ollama to the key check. Ollama does not need an API key, so skip the key warning for Ollama:
  ```python
  _required_keys: dict[str, str] = {
      "openai": OPENAI_API_KEY,
      "groq": GROQ_API_KEY,
  }
  if MODEL_PROVIDER in _required_keys:
      key = _required_keys[MODEL_PROVIDER]
      if not key:
          logger.warning(...)
  # Ollama does not require an API key — no warning needed.
  ```
- **PATTERN**: Follow existing config.py structure — `os.getenv` with defaults, typed annotations
- **GOTCHA**: The `OLLAMA_BASE_URL` env var must be set before any Pydantic AI OllamaModel is created. Since config.py is imported at module load time, this happens early enough.
- **GOTCHA**: Default `OLLAMA_HOST` should be `http://localhost:11434` (not `http://ollama:11434`) since the config defaults should work outside Docker too. The Docker Compose `environment` block will override with `http://ollama:11434`.
- **VALIDATE**: `uv run ruff check src/config.py && uv run ruff format --check src/config.py`

---

### Task 2: UPDATE `docker-compose.yml` — Add Ollama, SearXNG, Redis services

- **IMPLEMENT**: Add these services between the langfuse-server service and the app service:
  ```yaml
  # ---------------------------------------------------------------------------
  # Phase 4 — Local AI infrastructure
  # ---------------------------------------------------------------------------

  ollama:
    image: ollama/ollama
    profiles: ["bundled", "local-ai"]
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  searxng:
    image: searxng/searxng
    profiles: ["bundled", "local-ai"]
    ports:
      - "8080:8080"
    volumes:
      - ./config/searxng:/etc/searxng
    environment:
      - SEARXNG_BASE_URL=http://localhost:8080/

  redis:
    image: redis:7-alpine
    profiles: ["bundled", "cache"]
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
  ```
- **IMPLEMENT**: Add Phase 4 env vars to the `app` service `environment` block:
  ```yaml
  OLLAMA_HOST: ${OLLAMA_HOST:-http://ollama:11434}
  SEARCH_PROVIDER: ${SEARCH_PROVIDER:-brave}
  SEARXNG_HOST: ${SEARXNG_HOST:-http://searxng:8080}
  REDIS_URL: ${REDIS_URL:-redis://redis:6379/0}
  CACHE_ENABLED: ${CACHE_ENABLED:-false}
  ```
- **IMPLEMENT**: Add volumes to the `volumes` section:
  ```yaml
  volumes:
    supabase-data:
    langfuse-data:
    ollama-data:
    redis-data:
  ```
- **GOTCHA**: The GPU `deploy.resources.reservations.devices` section requires Docker Compose v2 and NVIDIA Container Toolkit. Ollama falls back to CPU automatically if no GPU is available, but Docker Compose may fail to start the container if the NVIDIA driver isn't installed. The docs should note this.
- **GOTCHA**: SearXNG needs a volume mount for config — the `config/searxng/` directory must exist before `docker compose up`.
- **VALIDATE**: `docker compose config --quiet` (validates YAML syntax)

---

### Task 3: CREATE `config/searxng/settings.yml` — SearXNG configuration

- **IMPLEMENT**: Create the file:
  ```yaml
  use_default_settings: true
  server:
    secret_key: "agentforge-dev-secret-change-in-production"
    bind_address: "0.0.0.0"
  search:
    formats:
      - html
      - json
  ```
- **GOTCHA**: The `json` format must be enabled or the API will return HTML instead of JSON. This is the most common SearXNG setup mistake.
- **GOTCHA**: Do NOT configure specific search engines in the settings file — SearXNG's defaults include Google, DuckDuckGo, Wikipedia, and others. Keep it simple.
- **VALIDATE**: File exists and is valid YAML

---

### Task 4: UPDATE `.env.example` — Add Phase 4 environment variables

- **IMPLEMENT**: Add after the Web Search section:
  ```env
  # -----------------------------------------------------------------------------
  # Ollama — Local LLM Serving (Phase 4)
  # Ollama runs open-source models locally. Start with --profile local-ai.
  # To use Ollama: set MODEL_PROVIDER=ollama and MODEL_NAME to a pulled model.
  # Example: MODEL_PROVIDER=ollama, MODEL_NAME=llama3.1:8b
  # See docs/local-ai-guide.md for setup instructions.
  # -----------------------------------------------------------------------------
  OLLAMA_HOST=http://localhost:11434
  # MODEL_PROVIDER=ollama
  # MODEL_NAME=llama3.1:8b

  # -----------------------------------------------------------------------------
  # Search Provider (Phase 4)
  # Choose between Brave Search (cloud API) or SearXNG (self-hosted).
  # brave: Requires BRAVE_SEARCH_API_KEY (see above).
  # searxng: Requires SearXNG running (--profile local-ai). No API key needed.
  # -----------------------------------------------------------------------------
  SEARCH_PROVIDER=brave

  # -----------------------------------------------------------------------------
  # SearXNG — Self-Hosted Search (Phase 4)
  # Defaults point to the bundled Docker Compose SearXNG service.
  # Override with your shared SearXNG instance when not using --profile local-ai.
  # -----------------------------------------------------------------------------
  SEARXNG_HOST=http://localhost:8080

  # -----------------------------------------------------------------------------
  # Caching (Phase 4)
  # Redis/Valkey caching — disabled by default.
  # Only enable after identifying a specific measured bottleneck.
  # Start Redis with: docker compose --profile cache up
  # -----------------------------------------------------------------------------
  CACHE_ENABLED=false
  REDIS_URL=redis://localhost:6379/0
  ```
- **IMPLEMENT**: Update the LLM Provider section comment to include ollama:
  ```env
  # Supported values for MODEL_PROVIDER: openai | groq | ollama
  ```
- **PATTERN**: Follow existing `.env.example` style — section headers with dashes, comments explaining each var
- **VALIDATE**: File is well-formed (no syntax errors in env format)

---

### Task 5: CREATE `scripts/pull_model.py` — Ollama model pull helper

- **IMPLEMENT**: Create the script:
  ```python
  """
  Pull a model into Ollama.

  Run after the Ollama container is up. Defaults to llama3.1:8b if no
  model name is provided. This script belongs to the scripts layer and
  is not imported by application code.

  Usage:
      uv run python scripts/pull_model.py
      uv run python scripts/pull_model.py qwen2.5:32b
  """

  import os
  import sys

  import httpx

  OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
  MODEL = sys.argv[1] if len(sys.argv) > 1 else "llama3.1:8b"


  def main() -> None:
      """Pull a model from the Ollama registry."""
      print(f"Pulling {MODEL} from {OLLAMA_HOST}...")
      try:
          with httpx.Client(timeout=600.0) as client:
              response = client.post(
                  f"{OLLAMA_HOST}/api/pull",
                  json={"name": MODEL},
              )
              response.raise_for_status()
          print(f"Successfully pulled {MODEL}")
      except httpx.HTTPError as exc:
          print(f"Failed to pull {MODEL}: {exc}", file=sys.stderr)
          sys.exit(1)


  if __name__ == "__main__":
      main()
  ```
- **GOTCHA**: Use synchronous httpx (not async) — this is a CLI script, not part of the async app. Use a long timeout (600s) because model pulls can take minutes.
- **GOTCHA**: The Ollama `/api/pull` endpoint streams progress. For simplicity, just check the final status code. A more sophisticated version could stream and display progress, but that's not needed for the MVP.
- **PATTERN**: Mirror `scripts/collect.py` and `scripts/seed.py` structure
- **VALIDATE**: `uv run ruff check scripts/pull_model.py`

---

### Task 6: CREATE `src/search/searxng.py` — SearXNG search client

- **IMPLEMENT**: Create the file mirroring `src/search/brave.py` structure:
  ```python
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
                  description=item.get("content", ""),  # SearXNG uses "content" not "description"
              )
          )

      logger.info(
          "SearXNG search complete",
          extra={"query": query, "results": len(results)},
      )
      return results
  ```
- **GOTCHA**: SearXNG returns `content` as the snippet field, NOT `description`. The Brave API uses `description`. Map `content` → `description` in the SearchResult model.
- **GOTCHA**: SearXNG's `number_of_results` param is a hint, not a guarantee. Slice `raw_results[:count]` to enforce the limit.
- **PATTERN**: Mirror `src/search/brave.py` exactly — same function signature `search_web(query, count)`, same return type `list[SearchResult]`, same error handling (return `[]`).
- **IMPORTS**: `httpx`, `pydantic.BaseModel`, `src.config.SEARXNG_HOST`
- **VALIDATE**: `uv run ruff check src/search/searxng.py`

---

### Task 7: UPDATE `src/search/__init__.py` — Update module docstring

- **IMPLEMENT**: Update the docstring to mention SearXNG:
  ```python
  """
  Web search integration layer.

  Provides async web search capabilities via external search APIs.
  Supports Brave Search (cloud API) and SearXNG (self-hosted).
  The active provider is selected via the SEARCH_PROVIDER config var.
  This module is imported by agent tools — it must not import collector
  or scheduler dependencies.
  """
  ```
- **VALIDATE**: `uv run ruff check src/search/__init__.py`

---

### Task 8: UPDATE `src/agent/tools.py` — Unify web_search tool with provider routing

- **IMPLEMENT**: Refactor the `web_search` function to route based on `SEARCH_PROVIDER`:
  ```python
  async def web_search(
      ctx: RunContext[Pool],
      query: str,
      count: int = 5,
  ) -> list[dict]:
      """Search the web for real-time information.

      Routes to Brave Search or SearXNG based on the SEARCH_PROVIDER
      configuration. Use this tool when the user's question requires
      up-to-date information not available in the collected video database.

      Args:
          ctx: Injected run context carrying the database pool.
          query: Search query string.
          count: Maximum number of results to return (default 5, max 20).

      Returns:
          List of search result dicts with title, url, and description.
      """
      from src.config import SEARCH_PROVIDER

      logger.debug("Tool: web_search", extra={"query": query, "provider": SEARCH_PROVIDER})
      count = min(count, 20)

      if SEARCH_PROVIDER == "searxng":
          from src.search.searxng import search_web as searxng_search

          results = await searxng_search(query, count=count)
      else:
          from src.search.brave import search_web as brave_search

          results = await brave_search(query, count=count)

      return [r.model_dump() for r in results]
  ```
- **GOTCHA**: Use lazy imports inside the function (not at module level) to avoid import errors when the non-active search provider's dependencies are missing. This also keeps the import within the function scope matching the existing pattern.
- **GOTCHA**: Import `SEARCH_PROVIDER` inside the function (not at module top) so it can be patched in tests. Alternatively, import at the top and patch `src.agent.tools.SEARCH_PROVIDER`.
- **PATTERN**: Follow existing tool pattern — `RunContext[Pool]` first arg, docstring with usage guidance, logging
- **VALIDATE**: `uv run ruff check src/agent/tools.py`

---

### Task 9: CREATE `src/cache/__init__.py` — Cache package init

- **IMPLEMENT**:
  ```python
  """
  Caching layer.

  Provides async caching via Redis/Valkey for measured performance
  bottlenecks. Disabled by default (CACHE_ENABLED=false). The cache
  is transparent — the system works identically without it, just slower.
  This module must not import agent, collector, or LLM dependencies.
  """
  ```
- **VALIDATE**: `uv run ruff check src/cache/__init__.py`

---

### Task 10: CREATE `src/cache/client.py` — Redis async cache client

- **IMPLEMENT**:
  ```python
  """
  Redis/Valkey cache client.

  Provides async cache operations (get, set, delete) with automatic TTL.
  The cache pool is created during FastAPI startup and stored in app.state.
  Returns None for all operations when caching is disabled — callers do
  not need to check CACHE_ENABLED themselves.

  This module belongs to the Cache layer. It imports from src.config only.
  """

  import json
  import logging

  import redis.asyncio as redis

  from src.config import CACHE_ENABLED, REDIS_URL

  logger = logging.getLogger(__name__)

  # Default TTL: 1 hour. Every cached value must have a TTL.
  DEFAULT_TTL_SECONDS: int = 3600


  async def create_cache_pool() -> redis.Redis | None:
      """Create an async Redis connection pool.

      Returns None when caching is disabled via CACHE_ENABLED=false.
      The caller should store the result in app.state.cache.
      """
      if not CACHE_ENABLED:
          logger.info("Caching disabled via CACHE_ENABLED=false")
          return None

      try:
          pool = redis.from_url(REDIS_URL, decode_responses=True)
          # Verify connectivity
          await pool.ping()
          logger.info("Redis cache pool created", extra={"url": REDIS_URL})
          return pool
      except Exception as exc:
          logger.error(
              "Failed to connect to Redis — continuing without cache",
              extra={"error": str(exc), "url": REDIS_URL},
          )
          return None


  async def close_cache_pool(pool: redis.Redis | None) -> None:
      """Close the Redis connection pool gracefully."""
      if pool is not None:
          await pool.aclose()
          logger.info("Redis cache pool closed")


  async def cache_get(pool: redis.Redis | None, key: str) -> str | None:
      """Get a value from cache.

      Returns None on cache miss, cache disabled, or any Redis error.
      Cache failures are silently logged — never raised to callers.

      Args:
          pool: Redis connection pool, or None if caching is disabled.
          key: Cache key.

      Returns:
          Cached string value, or None.
      """
      if pool is None:
          return None
      try:
          return await pool.get(key)
      except Exception as exc:
          logger.error("Cache get failed", extra={"key": key, "error": str(exc)})
          return None


  async def cache_set(
      pool: redis.Redis | None,
      key: str,
      value: str,
      ttl_seconds: int = DEFAULT_TTL_SECONDS,
  ) -> None:
      """Set a value in cache with TTL.

      No-ops when caching is disabled. Cache failures are logged but
      never raised — a failed cache write should never affect the response.

      Args:
          pool: Redis connection pool, or None if caching is disabled.
          key: Cache key.
          value: String value to cache.
          ttl_seconds: Time-to-live in seconds (default 3600).
      """
      if pool is None:
          return
      try:
          await pool.set(key, value, ex=ttl_seconds)
      except Exception as exc:
          logger.error("Cache set failed", extra={"key": key, "error": str(exc)})


  async def cache_delete(pool: redis.Redis | None, key: str) -> None:
      """Delete a value from cache.

      No-ops when caching is disabled.

      Args:
          pool: Redis connection pool, or None if caching is disabled.
          key: Cache key to delete.
      """
      if pool is None:
          return
      try:
          await pool.delete(key)
      except Exception as exc:
          logger.error("Cache delete failed", extra={"key": key, "error": str(exc)})


  async def cache_get_json(pool: redis.Redis | None, key: str) -> dict | list | None:
      """Get a JSON-deserialised value from cache.

      Args:
          pool: Redis connection pool, or None if caching is disabled.
          key: Cache key.

      Returns:
          Deserialised JSON value, or None on miss/error.
      """
      raw = await cache_get(pool, key)
      if raw is None:
          return None
      try:
          return json.loads(raw)
      except (json.JSONDecodeError, TypeError):
          return None


  async def cache_set_json(
      pool: redis.Redis | None,
      key: str,
      value: dict | list,
      ttl_seconds: int = DEFAULT_TTL_SECONDS,
  ) -> None:
      """Serialise a value to JSON and store in cache with TTL.

      Args:
          pool: Redis connection pool, or None if caching is disabled.
          key: Cache key.
          value: JSON-serialisable value.
          ttl_seconds: Time-to-live in seconds (default 3600).
      """
      try:
          serialised = json.dumps(value)
      except (TypeError, ValueError) as exc:
          logger.error("Cache JSON serialisation failed", extra={"key": key, "error": str(exc)})
          return
      await cache_set(pool, key, serialised, ttl_seconds)
  ```
- **PATTERN**: Mirror `src/memory/client.py` — disabled state returns None, graceful degradation, logging
- **GOTCHA**: All functions accept `pool` as first arg (not using a global) — follows the dependency injection pattern. The pool is stored in `app.state.cache` and passed explicitly.
- **GOTCHA**: Every cached value MUST have a TTL (no indefinite caching). The `DEFAULT_TTL_SECONDS` constant enforces this.
- **IMPORTS**: `redis.asyncio`, `json`, `logging`, `src.config`
- **VALIDATE**: `uv run ruff check src/cache/client.py`

---

### Task 11: UPDATE `src/api/main.py` — Add cache pool to lifespan

- **IMPLEMENT**: Add cache import at top:
  ```python
  from src.cache.client import close_cache_pool, create_cache_pool
  ```
- **IMPLEMENT**: Add cache pool creation in lifespan after memory init, and teardown before memory teardown:
  ```python
  # In lifespan, after memory init:
  try:
      app.state.cache = await create_cache_pool()
  except Exception as exc:
      logger.error(
          "Cache initialisation failed — continuing without cache",
          extra={"error": str(exc)},
      )
      app.state.cache = None

  # ... yield ...

  # In shutdown, before memory teardown:
  await close_cache_pool(getattr(app.state, "cache", None))
  ```
- **IMPLEMENT**: Update the lifespan docstring to include cache in the startup/shutdown order.
- **PATTERN**: Follow the existing memory init pattern — try/except with graceful degradation
- **GOTCHA**: Shutdown order matters — close cache before memory, memory before scheduler, scheduler before pool.
- **VALIDATE**: `uv run ruff check src/api/main.py`

---

### Task 12: ADD `redis` dependency to `pyproject.toml`

- **IMPLEMENT**: Add to the dependencies list:
  ```toml
  # Caching (Phase 4 — only used when CACHE_ENABLED=true)
  "redis>=5.0.0",
  ```
- **IMPLEMENT**: Run `uv sync --dev` to update the lockfile.
- **GOTCHA**: The `redis` package includes `redis.asyncio` built-in since v4.2+. No separate `aioredis` package needed.
- **VALIDATE**: `uv sync --dev` succeeds

---

### Task 13: UPDATE `.github/workflows/ci.yml` — Add Phase 4 env vars

- **IMPLEMENT**: Add to the `env` section of the test job:
  ```yaml
  OLLAMA_HOST: ""
  SEARCH_PROVIDER: "brave"
  SEARXNG_HOST: ""
  CACHE_ENABLED: "false"
  REDIS_URL: ""
  ```
- **GOTCHA**: Keep `CACHE_ENABLED=false` and `SEARXNG_HOST=""` in CI — no Redis or SearXNG service is available in the test runner.
- **VALIDATE**: YAML syntax is valid

---

### Task 14: UPDATE `tests/conftest.py` — Add cache fixture

- **IMPLEMENT**: Add a `mock_cache` fixture:
  ```python
  @pytest.fixture
  def mock_cache():
      """Return a mock Redis connection for cache tests."""
      cache = AsyncMock()
      cache.get = AsyncMock(return_value=None)
      cache.set = AsyncMock()
      cache.delete = AsyncMock()
      cache.ping = AsyncMock()
      cache.close = AsyncMock()
      return cache
  ```
- **IMPLEMENT**: Update the `client` fixture to also patch cache:
  ```python
  # Add to the patch block:
  patch("src.api.main.create_cache_pool", AsyncMock(return_value=None)),
  ```
  And add: `app.state.cache = None` alongside `app.state.memory = None`.
  And in cleanup: add `if hasattr(app.state, "cache"): del app.state.cache`.
- **PATTERN**: Follow existing `mock_pool` and `mock_memory_store` fixture patterns
- **VALIDATE**: `uv run ruff check tests/conftest.py`

---

### Task 15: CREATE `tests/test_ollama_provider.py` — Ollama provider config tests

- **IMPLEMENT**: Test that config correctly handles the Ollama provider:
  ```python
  """
  Ollama provider configuration tests.

  Verifies that Ollama is a valid provider in config, that get_model_string()
  produces correct model strings, and that validate_provider_config() does
  not warn for Ollama (which needs no API key).
  """

  from unittest.mock import patch

  import pytest


  def test_ollama_is_supported_provider():
      """Ollama is in the SUPPORTED_PROVIDERS set."""
      from src.config import SUPPORTED_PROVIDERS

      assert "ollama" in SUPPORTED_PROVIDERS


  def test_get_model_string_returns_ollama_prefix():
      """get_model_string() returns 'ollama:model' for Ollama provider."""
      with (
          patch("src.config.MODEL_PROVIDER", "ollama"),
          patch("src.config.MODEL_NAME", "llama3.1:8b"),
      ):
          from src.config import get_model_string

          result = get_model_string()

      assert result == "ollama:llama3.1:8b"


  def test_validate_provider_config_no_warning_for_ollama(caplog):
      """validate_provider_config() does not warn about missing keys for Ollama."""
      with (
          patch("src.config.MODEL_PROVIDER", "ollama"),
          patch("src.config.SUPPORTED_PROVIDERS", frozenset({"openai", "groq", "ollama"})),
      ):
          import logging

          with caplog.at_level(logging.WARNING):
              from src.config import validate_provider_config

              validate_provider_config()

      # Should not contain API key warnings for Ollama
      key_warnings = [r for r in caplog.records if "API key" in r.message or "No API key" in r.message]
      assert len(key_warnings) == 0


  def test_supported_providers_includes_all_three():
      """SUPPORTED_PROVIDERS includes openai, groq, and ollama."""
      from src.config import SUPPORTED_PROVIDERS

      assert SUPPORTED_PROVIDERS == frozenset({"openai", "groq", "ollama"})
  ```
- **PATTERN**: Follow `tests/test_agent.py` style — descriptive test names, patch config values, minimal assertions
- **VALIDATE**: `uv run pytest tests/test_ollama_provider.py -v`

---

### Task 16: CREATE `tests/test_searxng.py` — SearXNG client tests

- **IMPLEMENT**: Mirror `tests/test_web_search.py` test structure with SearXNG-specific responses:
  ```python
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
      assert results[0].description == "Description from SearXNG"  # Mapped from "content"
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
      mock_client.get = AsyncMock(
          side_effect=httpx.RequestError("connection refused")
      )

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
  ```
- **PATTERN**: Mirror `tests/test_web_search.py` exactly — same mock structure, same error paths
- **VALIDATE**: `uv run pytest tests/test_searxng.py -v`

---

### Task 17: CREATE `tests/test_cache.py` — Cache client tests

- **IMPLEMENT**:
  ```python
  """
  Cache client tests.

  Covers Redis cache operations: pool creation, get/set/delete, JSON
  helpers, and graceful degradation when caching is disabled.
  """

  from unittest.mock import AsyncMock, patch

  import pytest


  @pytest.mark.asyncio
  async def test_create_cache_pool_returns_none_when_disabled():
      """create_cache_pool returns None when CACHE_ENABLED=false."""
      with patch("src.cache.client.CACHE_ENABLED", False):
          from src.cache.client import create_cache_pool

          result = await create_cache_pool()

      assert result is None


  @pytest.mark.asyncio
  async def test_cache_get_returns_none_when_pool_is_none():
      """cache_get returns None when pool is None (caching disabled)."""
      from src.cache.client import cache_get

      result = await cache_get(None, "some-key")
      assert result is None


  @pytest.mark.asyncio
  async def test_cache_set_noop_when_pool_is_none():
      """cache_set silently no-ops when pool is None."""
      from src.cache.client import cache_set

      # Should not raise
      await cache_set(None, "key", "value")


  @pytest.mark.asyncio
  async def test_cache_delete_noop_when_pool_is_none():
      """cache_delete silently no-ops when pool is None."""
      from src.cache.client import cache_delete

      await cache_delete(None, "key")


  @pytest.mark.asyncio
  async def test_cache_get_delegates_to_redis(mock_cache):
      """cache_get calls Redis get with the correct key."""
      mock_cache.get = AsyncMock(return_value="cached-value")

      from src.cache.client import cache_get

      result = await cache_get(mock_cache, "test-key")

      assert result == "cached-value"
      mock_cache.get.assert_called_once_with("test-key")


  @pytest.mark.asyncio
  async def test_cache_set_delegates_to_redis_with_ttl(mock_cache):
      """cache_set calls Redis set with key, value, and TTL."""
      from src.cache.client import cache_set

      await cache_set(mock_cache, "key", "value", ttl_seconds=300)

      mock_cache.set.assert_called_once_with("key", "value", ex=300)


  @pytest.mark.asyncio
  async def test_cache_get_returns_none_on_redis_error(mock_cache):
      """cache_get returns None and logs error on Redis failure."""
      mock_cache.get = AsyncMock(side_effect=ConnectionError("redis down"))

      from src.cache.client import cache_get

      result = await cache_get(mock_cache, "key")

      assert result is None


  @pytest.mark.asyncio
  async def test_cache_set_does_not_raise_on_redis_error(mock_cache):
      """cache_set silently logs errors without raising."""
      mock_cache.set = AsyncMock(side_effect=ConnectionError("redis down"))

      from src.cache.client import cache_set

      # Should not raise
      await cache_set(mock_cache, "key", "value")


  @pytest.mark.asyncio
  async def test_cache_get_json_deserialises_value(mock_cache):
      """cache_get_json returns deserialised JSON from cache."""
      mock_cache.get = AsyncMock(return_value='{"name": "test", "count": 42}')

      from src.cache.client import cache_get_json

      result = await cache_get_json(mock_cache, "json-key")

      assert result == {"name": "test", "count": 42}


  @pytest.mark.asyncio
  async def test_cache_get_json_returns_none_on_invalid_json(mock_cache):
      """cache_get_json returns None when cached value is not valid JSON."""
      mock_cache.get = AsyncMock(return_value="not-json")

      from src.cache.client import cache_get_json

      result = await cache_get_json(mock_cache, "bad-json")

      assert result is None


  @pytest.mark.asyncio
  async def test_cache_set_json_serialises_value(mock_cache):
      """cache_set_json serialises dict to JSON string before storing."""
      from src.cache.client import cache_set_json

      await cache_set_json(mock_cache, "json-key", {"data": [1, 2, 3]}, ttl_seconds=600)

      mock_cache.set.assert_called_once()
      call_args = mock_cache.set.call_args
      assert '"data"' in call_args[0][1]  # JSON string contains the key
  ```
- **PATTERN**: Follow existing test patterns — mock Redis, test both success and failure paths, test disabled state
- **VALIDATE**: `uv run pytest tests/test_cache.py -v`

---

### Task 18: CREATE `docs/local-ai-guide.md` — Local AI setup guide

- **IMPLEMENT**: Create documentation covering:
  1. Prerequisites (Docker, NVIDIA Container Toolkit for GPU)
  2. Starting local AI services (`docker compose --profile local-ai up`)
  3. Pulling a model (`uv run python scripts/pull_model.py llama3.1:8b`)
  4. Configuring the app to use Ollama (`MODEL_PROVIDER=ollama`, `MODEL_NAME=llama3.1:8b`)
  5. Configuring SearXNG as search provider (`SEARCH_PROVIDER=searxng`)
  6. Running the full stack locally with zero external API keys
  7. Recommended models for different use cases (small/fast vs large/capable)
  8. CPU-only fallback (Ollama works without GPU, just slower)
  9. Troubleshooting common issues (model not pulled, GPU not detected, SearXNG returning HTML instead of JSON)

- **PATTERN**: Follow existing docs style (see `docs/memory-aware-agents.md`, `docs/pattern-decision-guide.md`)
- **VALIDATE**: File exists and is well-structured markdown

---

### Task 19: CREATE `docs/gpu-sharing.md` — GPU sharing guide

- **IMPLEMENT**: Create documentation covering:
  1. The problem: multiple AgentForge projects fighting over GPU memory
  2. The solution: one shared Ollama instance per server
  3. Setup: run Ollama once on the host (not in Docker), or as a single Docker container
  4. Configuration: each project sets `OLLAMA_HOST` to point at the shared instance
  5. Remove the Ollama service from each project's Docker Compose (use shared infra pattern)
  6. GPU memory management: Ollama handles model loading/unloading automatically
  7. Monitoring GPU usage (`nvidia-smi`)

- **PATTERN**: Follow shared infrastructure pattern established in Phase 1 for Postgres/Langfuse
- **VALIDATE**: File exists and is well-structured markdown

---

## TESTING STRATEGY

### Unit Tests

All new modules have corresponding test files with mocked external dependencies:

- **`tests/test_ollama_provider.py`** — Config validation for Ollama provider (4 tests)
- **`tests/test_searxng.py`** — SearXNG client with mocked httpx (6 tests)
- **`tests/test_cache.py`** — Cache client with mocked Redis (11 tests)

### Integration Tests

No integration tests with real services (Ollama, SearXNG, Redis) in CI. These services are not available in GitHub Actions. Integration testing is manual using `docker compose --profile bundled up`.

### Edge Cases

- Ollama provider with no API key set (should work — Ollama doesn't need one)
- SearXNG returning HTML instead of JSON (when `format=json` is not configured)
- SearXNG returning empty results array
- SearXNG returning results with missing `content` field
- Redis connection refused (CACHE_ENABLED=true but Redis not running)
- Redis timeout during operations
- Cache get/set with None pool (disabled state)
- Cache with invalid JSON values
- `SEARCH_PROVIDER` set to an unknown value (should default to Brave)
- Ollama model string with colon in name (e.g., `llama3.1:8b` → `ollama:llama3.1:8b`)

### Existing Test Regression

All existing tests must continue to pass with no modifications (except `conftest.py` updates for cache patching).

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```bash
uv run ruff check .
uv run ruff format --check .
```

**Expected**: Both pass with exit code 0

### Level 2: Unit Tests

```bash
uv run pytest tests/test_ollama_provider.py -v
uv run pytest tests/test_searxng.py -v
uv run pytest tests/test_cache.py -v
```

**Expected**: All tests pass

### Level 3: Full Test Suite (Regression)

```bash
uv run pytest tests/ -v --tb=short
```

**Expected**: All existing + new tests pass. Zero regressions.

### Level 4: Docker Validation

```bash
docker compose config --quiet
```

**Expected**: Docker Compose YAML is valid

### Level 5: Manual Validation (Local Only)

```bash
# Start local AI services
docker compose --profile local-ai up -d

# Pull a model
uv run python scripts/pull_model.py llama3.1:8b

# Test with Ollama provider
MODEL_PROVIDER=ollama MODEL_NAME=llama3.1:8b uv run uvicorn src.api.main:app

# Test SearXNG search
SEARCH_PROVIDER=searxng curl -X POST http://localhost:8000/api/ask -d '{"question": "test"}'
```

---

## ACCEPTANCE CRITERIA

- [ ] `"ollama"` is in `SUPPORTED_PROVIDERS`
- [ ] `get_model_string()` returns `"ollama:model-name"` when `MODEL_PROVIDER=ollama`
- [ ] `validate_provider_config()` does not warn about missing API key for Ollama
- [ ] Ollama Docker service defined with `bundled` and `local-ai` profiles
- [ ] GPU passthrough configured in Docker Compose (with CPU fallback)
- [ ] `scripts/pull_model.py` can pull a model into Ollama
- [ ] SearXNG Docker service defined with `bundled` and `local-ai` profiles
- [ ] SearXNG config enables JSON API format
- [ ] `src/search/searxng.py` returns `list[SearchResult]` matching Brave client interface
- [ ] `web_search` tool routes to SearXNG when `SEARCH_PROVIDER=searxng`
- [ ] `web_search` tool routes to Brave when `SEARCH_PROVIDER=brave` (default)
- [ ] Redis Docker service defined with `bundled` and `cache` profiles
- [ ] `src/cache/client.py` provides async get/set/delete with TTL
- [ ] Cache is disabled by default (`CACHE_ENABLED=false`)
- [ ] Cache operations no-op gracefully when disabled
- [ ] Cache errors are logged but never raised
- [ ] All Phase 4 env vars added to `.env.example` with comments
- [ ] All Phase 4 env vars added to CI workflow
- [ ] All three services (Ollama, SearXNG, Redis) are optional
- [ ] All existing Phase 1–3 tests still pass
- [ ] New tests cover: Ollama config, SearXNG search, cache operations
- [ ] `docs/local-ai-guide.md` covers running fully local
- [ ] `docs/gpu-sharing.md` covers shared Ollama on multi-project server
- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format --check .` passes

---

## COMPLETION CHECKLIST

- [ ] All 19 tasks completed in order
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully:
  - [ ] Level 1: ruff check, ruff format
  - [ ] Level 2: individual test files pass
  - [ ] Level 3: full test suite passes (zero regressions)
  - [ ] Level 4: docker compose config validates
- [ ] Full test suite passes (unit)
- [ ] No linting errors
- [ ] No formatting errors
- [ ] All acceptance criteria met
- [ ] Code reviewed for quality and maintainability

---

## NOTES

### Design Decisions

1. **Model string vs factory pattern for Ollama**: Using the model string approach (`"ollama:model-name"`) rather than a factory that creates `OpenAIChatModel(provider=OllamaProvider(...))` instances. This is simpler and keeps the existing `get_model_string()` pattern unchanged. Pydantic AI resolves the `OllamaProvider` from the `"ollama:"` prefix automatically. The `OLLAMA_BASE_URL` env var tells Pydantic AI where to connect (bridged from our `OLLAMA_HOST` config).

2. **Separate SearchResult models**: Both `src/search/brave.py` and `src/search/searxng.py` define their own `SearchResult` class. This avoids coupling the two modules. They have the same fields, so the `web_search` tool can call `.model_dump()` on either.

3. **Cache functions take pool as parameter**: Rather than using a module-level global `_pool`, cache functions accept the pool as a parameter. This follows the dependency injection pattern used throughout the codebase and makes testing trivial.

4. **Redis disabled by default**: Following the PRD's explicit instruction that caching should not be added speculatively. The infrastructure is ready but `CACHE_ENABLED=false` by default.

5. **SEARCH_PROVIDER config in tools.py, not at module level**: The `SEARCH_PROVIDER` import is inside the `web_search` function to allow easy patching in tests and to avoid import-time side effects.

### Risks

- **Ollama structured output**: Some Ollama models may not reliably produce structured JSON output matching Pydantic AI's `result_type`. This is a model capability issue, not a code issue. The docs should recommend models known to work well with structured output (e.g., `llama3.1:8b`, `qwen2.5:32b`).
- **SearXNG rate limiting**: SearXNG aggregates results from upstream engines which may rate-limit. The client handles this gracefully (returns `[]` on error).
- **GPU Docker setup**: The NVIDIA Container Toolkit must be installed on the host for GPU passthrough. This is a host configuration issue, not a code issue.

### Confidence Score: 9/10

High confidence because:
- Phase 4 is well-specified in `docs/Phase4.md`
- All three additions follow existing patterns (config, search client, optional service)
- No complex business logic — mostly infrastructure wiring
- Existing test patterns are clear and easy to replicate
- The only uncertainty is Pydantic AI's exact Ollama integration details (model string format, env var names)
