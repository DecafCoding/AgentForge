# PBI 3.1 — Mem0 Integration (Long-Term Memory)

The following plan should be complete, but validate documentation and codebase patterns before implementing.

Pay special attention to naming of existing utils, types, and models. Import from the right files.

## Feature Description

Add long-term agent memory backed by Mem0 with Postgres/pgvector vector storage. Agents can store memories from conversations and retrieve them in future sessions. Memory is isolated from existing application tables via `collection_name` namespacing. The memory layer is independently disablable via `MEMORY_ENABLED=false`.

This PBI builds the foundational memory infrastructure. The memory-aware agent and API route are delivered in PBI 3.4.

## User Story

As a Python developer building AI agents
I want a pre-integrated long-term memory layer backed by my existing Postgres instance
So that my agents can remember information across sessions without me assembling the integration from scratch

## Problem Statement

Phase 1-2 agents are stateless — every conversation starts from zero context. Developers who want cross-session memory must manually integrate a memory solution, configure vector storage, and handle the lifecycle. This is exactly the kind of plumbing AgentForge should eliminate.

## Solution Statement

Integrate Mem0's `AsyncMemory` with the existing Postgres/pgvector instance. Provide a `BaseMemoryStore` ABC, a concrete `Mem0MemoryStore`, and helper functions for retrieving/storing memories. Initialize the memory client in FastAPI's lifespan hook alongside the existing DB pool and scheduler.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `src/memory/` (new), `src/config.py`, `src/api/main.py`, `pyproject.toml`
**Dependencies**: `mem0ai>=1.0.0`
**Branch**: `feat/pbi-3.1-mem0-integration` (from `main`)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — YOU MUST READ THESE BEFORE IMPLEMENTING!

- `CLAUDE.md` — All coding conventions, architectural boundaries, naming rules. READ FIRST.
- `docs/Phase3.md` (lines 113-226) — PBI 3.1 specification, config dict structure, store interface
- `src/config.py` (lines 1-91) — Config pattern: module-level constants from env vars, typed defaults
- `src/api/main.py` (lines 1-76) — Lifespan hook pattern: startup creates pool + scheduler, shutdown reverses
- `src/db/client.py` (lines 1-37) — Pool creation/close pattern to mirror for memory client lifecycle
- `src/observability/tracing.py` (lines 1-62) — Singleton client pattern with lazy init and graceful None
- `src/collector/base.py` (lines 1-33) — ABC pattern with module docstring conventions
- `tests/conftest.py` (lines 1-57) — Fixture patterns: MagicMock pool, AsyncMock methods, client fixture
- `tests/test_agent.py` (lines 1-30) — Test helper and mock patterns
- `.env.example` — Env var documentation pattern with section headers and comments

### New Files to Create

- `src/memory/__init__.py` — Package init with public API exports
- `src/memory/client.py` — Mem0 AsyncMemory client factory
- `src/memory/store.py` — BaseMemoryStore ABC + Mem0MemoryStore implementation
- `src/memory/helpers.py` — Memory retrieval and injection helpers
- `tests/test_memory.py` — Full test coverage for memory layer

### Files to Modify

- `pyproject.toml` — Add `mem0ai` dependency
- `src/config.py` — Add `MEMORY_ENABLED`, `MEMORY_MODEL` env vars
- `.env.example` — Document memory env vars
- `src/api/main.py` — Init/shutdown memory client in lifespan
- `docker-compose.yml` — Add memory env vars to app service
- `.github/workflows/ci.yml` — Add memory env vars (disabled)
- `tests/conftest.py` — Add `mock_memory_store` fixture, patch `app.state.memory`

### Relevant Documentation — READ BEFORE IMPLEMENTING!

- [Mem0 Open-Source Configuration](https://docs.mem0.ai/open-source/configuration)
  - Exact config dict structure for pgvector + OpenAI embedder
  - Why: Required for `src/memory/client.py` setup
- [Mem0 Async Memory](https://docs.mem0.ai/open-source/features/async-memory)
  - AsyncMemory class API — `add()`, `search()`, `get_all()`, `delete()` are all awaitable
  - Why: CRITICAL — project is fully async, must use `AsyncMemory` not `Memory`
- [Mem0 pgvector docs](https://docs.mem0.ai/components/vectordbs/dbs/pgvector)
  - pgvector backend config: `collection_name`, `embedding_model_dims`
  - Why: Database configuration and table namespacing strategy

### Patterns to Follow

**Module Docstring Pattern:**
```python
"""
Mem0 client initialisation.

Creates an AsyncMemory instance configured with Postgres/pgvector as the
vector store. This module belongs to the Memory layer and imports from
src.config only.
"""
```

**Config Pattern** (from `src/config.py`):
```python
MEMORY_ENABLED: bool = os.getenv("MEMORY_ENABLED", "true").lower() == "true"
```

**Lifespan Pattern** (from `src/api/main.py`):
```python
app.state.pool = await create_pool()  # startup
await close_pool(app.state.pool)      # shutdown
```

**Singleton Client Pattern** (from `src/observability/tracing.py`):
```python
def get_client() -> Langfuse | None:
    if not KEYS_CONFIGURED:
        logger.warning("...not configured — disabled...")
        return None
    ...
```

**ABC Pattern** (from `src/collector/base.py`):
```python
class BaseCollector(ABC):
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    @abstractmethod
    async def collect(self) -> int: ...
```

**Test Mock Pattern** (from `tests/conftest.py`):
```python
pool = MagicMock()
pool.fetch = AsyncMock(return_value=[])
```

---

## STEP-BY-STEP TASKS

### Task 1: UPDATE `pyproject.toml` — Add mem0ai dependency

- **IMPLEMENT**: Add `"mem0ai>=1.0.0,<2.0.0"` to `[project] dependencies` after the `langgraph` entry:
  ```
  # Long-term memory
  "mem0ai>=1.0.0,<2.0.0",
  ```
- **PATTERN**: Follow existing dependency format at `pyproject.toml:6-30`
- **GOTCHA**: `mem0ai` pulls many transitive deps. Pin `<2.0.0` for API stability.
- **VALIDATE**: `uv sync --dev` (must resolve without errors)

---

### Task 2: UPDATE `src/config.py` — Add memory environment variables

- **IMPLEMENT**: Add after the existing Collector section (after line 48):
  ```python
  # ---------------------------------------------------------------------------
  # Memory (Phase 3)
  # ---------------------------------------------------------------------------
  MEMORY_ENABLED: bool = os.getenv("MEMORY_ENABLED", "true").lower() == "true"
  MEMORY_MODEL: str = os.getenv("MEMORY_MODEL", "gpt-4o-mini")
  ```
- **PATTERN**: Mirror existing config sections — comment block header, typed constants, sensible defaults
- **GOTCHA**: `MEMORY_ENABLED` is a bool parsed from string. Default `"true"`.
- **VALIDATE**: `uv run python -c "from src.config import MEMORY_ENABLED, MEMORY_MODEL; print(f'enabled={MEMORY_ENABLED}, model={MEMORY_MODEL}')"`

---

### Task 3: UPDATE `.env.example` — Document memory env vars

- **IMPLEMENT**: Append after the YouTube Collector section:
  ```env
  # -----------------------------------------------------------------------------
  # Memory (Phase 3)
  # Mem0 uses the same Postgres instance for vector storage (pgvector).
  # MEMORY_MODEL: Model used by Mem0 for memory extraction (low-cost model recommended).
  # MEMORY_ENABLED: Set to false to disable memory for testing or cost control.
  # -----------------------------------------------------------------------------
  MEMORY_ENABLED=true
  MEMORY_MODEL=gpt-4o-mini
  ```
- **PATTERN**: Mirror existing `.env.example` section headers and comment style
- **VALIDATE**: Visual review

---

### Task 4: CREATE `src/memory/__init__.py` — Package init

- **IMPLEMENT**:
  ```python
  """
  Long-term memory layer.

  Provides cross-session memory storage and retrieval backed by Mem0 with a
  Postgres/pgvector vector store. The memory layer sits alongside the Agent
  and Observability layers in the architecture — it may be imported by the
  Agent and API layers but must not import from them.

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

### Task 5: CREATE `src/memory/client.py` — Mem0 AsyncMemory client factory

- **IMPLEMENT**:
  ```python
  """
  Mem0 client initialisation.

  Creates an AsyncMemory instance configured with Postgres/pgvector as the
  vector store. Uses the same Postgres instance as the main application but
  with a separate collection_name to avoid table conflicts. Mem0 auto-creates
  its tables on first use — no Alembic migration is needed for Mem0's storage.

  This module belongs to the Memory layer. It imports from src.config only.
  """

  import logging
  from urllib.parse import urlparse

  from src.config import (
      DATABASE_URL,
      MEMORY_ENABLED,
      MEMORY_MODEL,
      MODEL_PROVIDER,
      OPENAI_API_KEY,
  )

  logger = logging.getLogger(__name__)
  ```
- **Implement** `_parse_database_url(url: str) -> dict[str, str | int]`:
  - Parse `DATABASE_URL` (e.g. `postgresql://user:pass@host:5432/dbname`) into individual fields
  - Mem0 does NOT accept a connection string — it needs `host`, `port`, `user`, `password`, `dbname` separately
  - Use `urllib.parse.urlparse`
  ```python
  def _parse_database_url(url: str) -> dict[str, str | int]:
      """Extract connection parameters from a postgresql:// URL.

      Mem0's pgvector config requires individual fields, not a connection string.
      """
      parsed = urlparse(url)
      return {
          "host": parsed.hostname or "localhost",
          "port": parsed.port or 5432,
          "user": parsed.username or "postgres",
          "password": parsed.password or "postgres",
          "dbname": parsed.path.lstrip("/") or "agentforge",
      }
  ```
- **Implement** `async def create_memory_client()` with return type annotation using a string forward reference or `Any` to avoid importing `AsyncMemory` at module level when disabled:
  ```python
  async def create_memory_client() -> object | None:
      """Create and return a Mem0 AsyncMemory client, or None if disabled.

      Returns None when MEMORY_ENABLED is False or when required configuration
      (API key for the LLM provider) is missing. The caller should store the
      result in app.state and wrap it in a Mem0MemoryStore.
      """
      if not MEMORY_ENABLED:
          logger.info("Memory disabled via MEMORY_ENABLED=false")
          return None

      if MODEL_PROVIDER == "openai" and not OPENAI_API_KEY:
          logger.warning("Memory requires OPENAI_API_KEY for embeddings — disabled")
          return None

      from mem0 import AsyncMemory

      db_params = _parse_database_url(DATABASE_URL)

      config = {
          "vector_store": {
              "provider": "pgvector",
              "config": {
                  "host": db_params["host"],
                  "port": db_params["port"],
                  "user": db_params["user"],
                  "password": db_params["password"],
                  "dbname": db_params["dbname"],
                  "collection_name": "agentforge_memories",
                  "embedding_model_dims": 1536,
              },
          },
          "llm": {
              "provider": MODEL_PROVIDER,
              "config": {
                  "model": MEMORY_MODEL,
                  "api_key": OPENAI_API_KEY,
              },
          },
          "embedder": {
              "provider": "openai",
              "config": {
                  "model": "text-embedding-3-small",
                  "api_key": OPENAI_API_KEY,
              },
          },
      }

      logger.info(
          "Initialising Mem0 memory client",
          extra={
              "provider": MODEL_PROVIDER,
              "model": MEMORY_MODEL,
              "db_host": db_params["host"],
              "collection": "agentforge_memories",
          },
      )

      return AsyncMemory.from_config(config)
  ```
- **GOTCHA**: Import `AsyncMemory` inside the function body so the module loads cleanly even if `mem0ai` has import-time side effects. Also avoids import cost when memory is disabled.
- **GOTCHA**: `embedding_model_dims=1536` MUST match the embedder model output. OpenAI `text-embedding-3-small` = 1536. A mismatch causes silent insert failures.
- **GOTCHA**: Mem0 auto-creates its own tables on first use — no Alembic migration needed for Mem0's storage.
- **GOTCHA**: The `embedder` section is required and separate from the `llm` section. The LLM is used for memory extraction; the embedder is used for vector storage.
- **VALIDATE**: `uv run python -c "from src.memory.client import create_memory_client, _parse_database_url; print(_parse_database_url('postgresql://u:p@h:5432/db'))"`

---

### Task 6: CREATE `src/memory/store.py` — BaseMemoryStore ABC + Mem0MemoryStore

- **IMPLEMENT**:
  ```python
  """
  Memory store interface and Mem0 implementation.

  BaseMemoryStore defines the async contract for memory backends.
  Mem0MemoryStore wraps the Mem0 AsyncMemory client. All public methods
  are async. This module belongs to the Memory layer.
  """

  import logging
  from abc import ABC, abstractmethod

  logger = logging.getLogger(__name__)
  ```
- **BaseMemoryStore ABC**:
  ```python
  class BaseMemoryStore(ABC):
      """Abstract base for memory storage backends.

      Implementations wrap a specific memory provider (Mem0, etc.) and
      expose a uniform async interface for storing and retrieving memories.
      """

      @abstractmethod
      async def add(self, content: str, user_id: str, metadata: dict | None = None) -> str:
          """Store a memory and return its ID."""
          ...

      @abstractmethod
      async def search(self, query: str, user_id: str, limit: int = 5) -> list[dict]:
          """Search memories relevant to a query for a specific user."""
          ...

      @abstractmethod
      async def get_all(self, user_id: str) -> list[dict]:
          """Return all memories for a user."""
          ...

      @abstractmethod
      async def delete(self, memory_id: str) -> None:
          """Delete a specific memory by ID."""
          ...
  ```
- **Mem0MemoryStore**:
  ```python
  class Mem0MemoryStore(BaseMemoryStore):
      """Mem0-backed memory store using AsyncMemory.

      Wraps Mem0's async API and handles response parsing. Mem0's add()
      returns a dict with a results list; search() returns a list of dicts
      with 'memory' and 'score' keys.
      """

      def __init__(self, client: object) -> None:
          self._client = client

      async def add(self, content: str, user_id: str, metadata: dict | None = None) -> str:
          """Store a memory via Mem0 and return its ID."""
          result = await self._client.add(content, user_id=user_id, metadata=metadata or {})
          logger.debug("Memory stored", extra={"user_id": user_id, "result": result})
          # Mem0 returns {"results": [{"id": "...", "memory": "...", ...}]}
          results = result.get("results", [])
          if results:
              return results[0].get("id", "")
          return ""

      async def search(self, query: str, user_id: str, limit: int = 5) -> list[dict]:
          """Search for relevant memories via Mem0."""
          results = await self._client.search(query, user_id=user_id, limit=limit)
          logger.debug(
              "Memory search complete",
              extra={"user_id": user_id, "results": len(results)},
          )
          return results

      async def get_all(self, user_id: str) -> list[dict]:
          """Return all memories for a user via Mem0."""
          results = await self._client.get_all(user_id=user_id)
          return results

      async def delete(self, memory_id: str) -> None:
          """Delete a memory by ID via Mem0."""
          await self._client.delete(memory_id)
          logger.debug("Memory deleted", extra={"memory_id": memory_id})
  ```
- **GOTCHA**: Mem0's `add()` return structure may vary. Log the raw result at DEBUG on first use. The `results[0]["id"]` path is based on current docs — verify.
- **GOTCHA**: Mem0's `search()` returns dicts with `"memory"` (text), `"score"` (float), and possibly `"id"` keys. Preserve the full dict for callers.
- **VALIDATE**: `uv run python -c "from src.memory.store import BaseMemoryStore, Mem0MemoryStore; print('OK')"`

---

### Task 7: CREATE `src/memory/helpers.py` — Memory retrieval and injection helpers

- **IMPLEMENT**:
  ```python
  """
  Memory retrieval and injection helpers.

  Utility functions for injecting relevant memories into agent prompts and
  storing interaction history. Used by memory-aware agents to bridge the
  memory store and the Pydantic AI system prompt.

  This module belongs to the Memory layer.
  """

  import logging

  from src.memory.store import BaseMemoryStore

  logger = logging.getLogger(__name__)
  ```
- **`get_relevant_context()`**:
  ```python
  async def get_relevant_context(
      store: BaseMemoryStore,
      query: str,
      user_id: str,
      limit: int = 5,
  ) -> str:
      """Retrieve relevant memories and format as context for an agent prompt.

      Args:
          store: Memory store to search.
          query: The user's current query to match against.
          user_id: User identifier for scoping memory search.
          limit: Maximum number of memories to retrieve.

      Returns:
          Formatted context string, or empty string if no relevant memories.
      """
      try:
          memories = await store.search(query, user_id=user_id, limit=limit)
      except Exception as exc:
          logger.error("Memory search failed", extra={"error": str(exc)})
          return ""

      if not memories:
          return ""

      context_parts = ["Relevant context from previous conversations:"]
      for mem in memories:
          text = mem.get("memory", "")
          if text:
              context_parts.append(f"- {text}")

      logger.info(
          "Memory context retrieved",
          extra={"user_id": user_id, "memories_found": len(memories)},
      )
      return "\n".join(context_parts)
  ```
- **`store_interaction()`**:
  ```python
  async def store_interaction(
      store: BaseMemoryStore,
      question: str,
      answer: str,
      user_id: str,
  ) -> str | None:
      """Store a question/answer interaction as a memory.

      Memory storage failure is logged but does not raise — a failed memory
      write should never crash the agent response.

      Args:
          store: Memory store to write to.
          question: The user's question.
          answer: The agent's answer.
          user_id: User identifier for scoping the memory.

      Returns:
          The memory ID, or None if storage failed.
      """
      content = f"User asked: {question}\nAssistant answered: {answer}"
      try:
          memory_id = await store.add(
              content, user_id=user_id, metadata={"type": "interaction"}
          )
          logger.info(
              "Interaction stored as memory",
              extra={"user_id": user_id, "memory_id": memory_id},
          )
          return memory_id
      except Exception as exc:
          logger.error(
              "Failed to store interaction memory",
              extra={"user_id": user_id, "error": str(exc)},
          )
          return None
  ```
- **GOTCHA**: `get_relevant_context()` catches exceptions — memory search failure returns empty string, doesn't crash the agent.
- **GOTCHA**: `store_interaction()` catches exceptions — memory write failure returns None, doesn't crash.
- **VALIDATE**: `uv run python -c "from src.memory.helpers import get_relevant_context, store_interaction; print('OK')"`

---

### Task 8: UPDATE `src/api/main.py` — Init memory client in lifespan

- **IMPLEMENT**: Add memory client initialization after pool creation in the lifespan hook.
- **Add import** at top of file:
  ```python
  from src.memory.client import create_memory_client
  ```
- **In `lifespan()` startup** (after `await start_scheduler(app.state.pool)`):
  ```python
  try:
      memory_client = await create_memory_client()
      if memory_client is not None:
          from src.memory.store import Mem0MemoryStore
          app.state.memory = Mem0MemoryStore(memory_client)
          logger.info("Memory store initialised")
      else:
          app.state.memory = None
  except Exception as exc:
      logger.error("Memory initialisation failed — continuing without memory",
                   extra={"error": str(exc)})
      app.state.memory = None
  ```
- **In `lifespan()` shutdown** (before `await shutdown_scheduler()`):
  ```python
  app.state.memory = None
  ```
- **GOTCHA**: Memory init failure must NOT crash the app. Wrap in try/except, log error, set `app.state.memory = None`.
- **GOTCHA**: Import `Mem0MemoryStore` inside the conditional to avoid import cost when memory is disabled.
- **PATTERN**: Mirror pool lifecycle at `main.py:38-47`
- **VALIDATE**: `uv run python -c "from src.api.main import create_app; print('OK')"`

---

### Task 9: UPDATE `docker-compose.yml` — Add memory env vars

- **IMPLEMENT**: Add to the `app` service `environment` section (after `COLLECTION_INTERVAL_MINUTES`):
  ```yaml
  MEMORY_ENABLED: ${MEMORY_ENABLED:-true}
  MEMORY_MODEL: ${MEMORY_MODEL:-gpt-4o-mini}
  ```
- **VALIDATE**: Visual review

---

### Task 10: UPDATE `.github/workflows/ci.yml` — Add memory env vars (disabled)

- **IMPLEMENT**: Add to the test job `env` section (after `YOUTUBE_API_KEY`):
  ```yaml
  MEMORY_ENABLED: "false"
  MEMORY_MODEL: "gpt-4o-mini"
  ```
- **GOTCHA**: Memory MUST be disabled in CI — no real LLM calls.
- **VALIDATE**: Visual review

---

### Task 11: UPDATE `tests/conftest.py` — Add memory fixtures and patch app.state.memory

- **IMPLEMENT**: Add `mock_memory_store` fixture:
  ```python
  @pytest.fixture
  def mock_memory_store():
      """Return a mock BaseMemoryStore with no-op async methods."""
      store = MagicMock()
      store.add = AsyncMock(return_value="mem-test-123")
      store.search = AsyncMock(return_value=[])
      store.get_all = AsyncMock(return_value=[])
      store.delete = AsyncMock()
      return store
  ```
- **UPDATE** the `client` fixture: Add `app.state.memory = None` alongside `app.state.pool = mock_pool`:
  ```python
  app.state.pool = mock_pool
  app.state.memory = None  # Memory disabled in API tests by default
  ```
  And in teardown:
  ```python
  del app.state.pool
  if hasattr(app.state, "memory"):
      del app.state.memory
  ```
- **ALSO**: Add `create_memory_client` to the patches in the `client` fixture to prevent actual Mem0 init:
  ```python
  patch("src.api.main.create_memory_client", AsyncMock(return_value=None)),
  ```
- **VALIDATE**: `uv run pytest tests/test_api.py -v` (existing tests must still pass)

---

### Task 12: CREATE `tests/test_memory.py` — Memory layer tests

- **IMPLEMENT**: Comprehensive test coverage:

  ```python
  """
  Memory layer tests.

  Covers the BaseMemoryStore interface, Mem0MemoryStore implementation,
  helper functions, and client factory. All Mem0 calls are mocked — no
  real LLM or Postgres connections are made.
  """

  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest
  ```

  **URL parser tests:**
  - `test_parse_database_url_extracts_components` — Standard URL parsing
  - `test_parse_database_url_handles_defaults` — Missing components get defaults

  **Client factory tests:**
  - `test_create_memory_client_returns_none_when_disabled` — `MEMORY_ENABLED=false`
  - `test_create_memory_client_returns_none_when_no_api_key` — Empty OPENAI_API_KEY

  **Mem0MemoryStore tests (mock AsyncMemory client):**
  - `test_mem0_store_add_calls_client_and_returns_id` — Verify delegation and ID extraction
  - `test_mem0_store_add_returns_empty_string_on_empty_results` — Edge case
  - `test_mem0_store_search_delegates_to_client` — Verify search delegation
  - `test_mem0_store_get_all_delegates_to_client` — Verify get_all delegation
  - `test_mem0_store_delete_delegates_to_client` — Verify delete delegation

  **Helper tests:**
  - `test_get_relevant_context_formats_memories` — Returns formatted string with memories
  - `test_get_relevant_context_returns_empty_for_no_results` — Empty search results
  - `test_get_relevant_context_returns_empty_on_search_error` — Exception handling
  - `test_store_interaction_formats_and_stores` — Verify content format and add() call
  - `test_store_interaction_returns_none_on_error` — Exception handling

  **Example test structure for store:**
  ```python
  async def test_mem0_store_add_calls_client_and_returns_id():
      """Mem0MemoryStore.add() delegates to the Mem0 client and returns the memory ID."""
      mock_client = MagicMock()
      mock_client.add = AsyncMock(
          return_value={"results": [{"id": "mem-abc", "memory": "stored"}]}
      )
      store = Mem0MemoryStore(mock_client)

      result = await store.add("test content", user_id="user-1")

      mock_client.add.assert_called_once_with(
          "test content", user_id="user-1", metadata={}
      )
      assert result == "mem-abc"
  ```

  **Example test for helpers:**
  ```python
  async def test_get_relevant_context_formats_memories(mock_memory_store):
      """get_relevant_context returns formatted context string."""
      mock_memory_store.search = AsyncMock(
          return_value=[
              {"memory": "User likes Python tutorials"},
              {"memory": "User asked about async patterns"},
          ]
      )

      result = await get_relevant_context(mock_memory_store, "python", "user-1")

      assert "Relevant context from previous conversations:" in result
      assert "User likes Python tutorials" in result
      assert "User asked about async patterns" in result
  ```

- **VALIDATE**: `uv run pytest tests/test_memory.py -v`

---

### Task 13: RUN full validation

- **VALIDATE all tests pass**:
  ```bash
  uv run pytest tests/ -v --tb=short
  ```
- **VALIDATE lint**:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  ```
- **VALIDATE imports**:
  ```bash
  uv run python -c "from src.memory.client import create_memory_client; from src.memory.store import BaseMemoryStore, Mem0MemoryStore; from src.memory.helpers import get_relevant_context, store_interaction; print('All memory imports OK')"
  ```

---

## TESTING STRATEGY

### Unit Tests

- Mock `AsyncMemory` client entirely — no real Mem0, LLM, or Postgres calls
- Test all `BaseMemoryStore` methods via `Mem0MemoryStore` with mocked client
- Test helpers with mocked `BaseMemoryStore`
- Test client factory with patched config values

### Edge Cases

- `MEMORY_ENABLED=false` — client returns None, app continues
- Empty `OPENAI_API_KEY` — client returns None with warning
- Mem0 `add()` returns empty results list — returns empty string ID
- Memory search raises exception — `get_relevant_context()` returns empty string
- Memory add raises exception — `store_interaction()` returns None
- Lifespan memory init raises — app continues without memory

---

## VALIDATION COMMANDS

```bash
# Level 1: Syntax & Style
uv run ruff check .
uv run ruff format --check .

# Level 2: All tests
uv run pytest tests/ -v --tb=short

# Level 3: Memory-specific tests
uv run pytest tests/test_memory.py -v

# Level 4: Regression (existing tests unbroken)
uv run pytest tests/test_api.py tests/test_agent.py tests/test_orchestration.py tests/test_cross_agent_tracing.py tests/test_collector.py -v

# Level 5: Dependency resolution
uv sync --dev
```

---

## ACCEPTANCE CRITERIA

- [ ] `mem0ai` is in `pyproject.toml` and resolves via `uv sync`
- [ ] `MEMORY_ENABLED` and `MEMORY_MODEL` config vars exist with sensible defaults
- [ ] `create_memory_client()` returns `AsyncMemory` when enabled, `None` when disabled
- [ ] `Mem0MemoryStore` implements `BaseMemoryStore` with async add/search/get_all/delete
- [ ] `get_relevant_context()` returns formatted memory string or empty string on failure
- [ ] `store_interaction()` stores content or returns None on failure (no crash)
- [ ] Memory client initialised in FastAPI lifespan, stored in `app.state.memory`
- [ ] Memory init failure does not crash the application
- [ ] Mem0 tables namespaced via `collection_name="agentforge_memories"`
- [ ] All existing Phase 1 + 2 tests still pass
- [ ] New memory tests cover client, store, helpers, and edge cases
- [ ] Memory disabled in CI via `MEMORY_ENABLED=false`

---

## NOTES

- **AsyncMemory over Memory**: The codebase is fully async. Mem0's `AsyncMemory` is mandatory. Using sync `Memory` wrapped in `asyncio.to_thread()` is an anti-pattern.
- **collection_name over schema isolation**: Mem0 does NOT support Postgres schema-level isolation in its config dict. `collection_name="agentforge_memories"` is the namespacing mechanism.
- **No migration for Mem0 tables**: Mem0 auto-creates its vector tables on first use. We only need Alembic migrations for our own tables (scraped_pages in PBI 3.2).
- **Graceful degradation**: Memory disabled → `app.state.memory = None`. All downstream code must check for None.
