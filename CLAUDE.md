# CLAUDE.md — AgentForge Development Guide

This file provides the conventions, rules, and architectural guidelines for AI-assisted development on the AgentForge project. It is the authoritative source for how code should be written, structured, and documented.

For phase-specific implementation details, see the individual Phase files (`Phase1.md`, `Phase2.md`, etc.) and the `PRD.md`. For architectural decisions and their rationale, see `ARCHITECTURE.md`.

---

## Project Overview

AgentForge is an opinionated, open-source, code-first Python stack for building AI agents. It ships pre-integrated tooling with enforced architectural patterns — not a framework with rigid constraints, but a curated foundation with sensible defaults.

**Tech stack summary:** Python 3.12, uv (package manager), FastAPI, Pydantic AI, LangGraph, Postgres 15 + pgvector, Alembic, APScheduler, Langfuse, Docker Compose, Ruff, Pytest.

---

## Documentation Requirements

### File and Class Descriptions

Every Python file must begin with a module-level docstring describing the file's purpose, its role in the system, and what layer it belongs to.

```python
"""
YouTube video metadata collector.

Fetches video metadata and transcripts from the YouTube Data API on a
scheduled interval and stores them in Postgres. This module belongs to
the Collector layer and must not import any LLM or observability
dependencies.
"""
```

Every class must have a class-level docstring describing its responsibility and how it fits into the broader architecture.

```python
class YouTubeCollector(BaseCollector):
    """Collects video metadata and transcripts from YouTube channels.

    Implements the BaseCollector interface for scheduled data collection.
    Uses the YouTube Data API v3 for metadata and youtube-transcript-api
    for transcripts. Stores results via the database query layer.
    """
```

### Method and Function Comments

Every method and function must have a short docstring (one to two sentences) describing what it does, not how it does it. Use Google-style docstrings when parameters or return values are non-obvious.

```python
async def collect(self) -> int:
    """Run a collection cycle for all configured YouTube channels."""

async def get_videos(pool: Pool, channel_id: str, limit: int = 20) -> list[VideoModel]:
    """Fetch the most recent videos for a channel.

    Args:
        pool: asyncpg connection pool.
        channel_id: YouTube channel identifier.
        limit: Maximum number of videos to return.

    Returns:
        List of video models ordered by published date descending.
    """
```

Inline comments should explain *why*, not *what*. If the code needs a comment to explain what it does, the code should be rewritten to be clearer.

```python
# Groq uses the OpenAI-compatible API with a base_url override
groq_model = OpenAIModel(model_name=MODEL_NAME, base_url="https://api.groq.com/openai/v1")
```

---

## Python Style and Conventions

### Foundational Standards

This project follows **PEP 8** as enforced by **Ruff**. Ruff replaces flake8, black, and isort. The canonical configuration lives in `pyproject.toml`.

- **Line length:** 88 characters (black default).
- **Python target:** 3.12.
- **String quotes:** Double quotes preferred.
- **Trailing commas:** Always use trailing commas in multi-line structures (tuples, lists, dicts, function signatures). This produces cleaner diffs.

### Naming Conventions

Follow PEP 8 naming strictly:

| Element | Convention | Example |
|---------|-----------|---------|
| Modules | `snake_case` | `youtube.py`, `base.py` |
| Classes | `PascalCase` | `YouTubeCollector`, `AgentResponse` |
| Functions / methods | `snake_case` | `get_videos`, `collect` |
| Constants | `UPPER_SNAKE_CASE` | `MODEL_PROVIDER`, `DATABASE_URL` |
| Private attributes | Leading underscore | `_pool`, `_scheduler` |
| Type variables | `PascalCase` | `T`, `CollectorT` |

Avoid abbreviations unless they are universally understood (`db`, `id`, `url`, `api`). Prefer descriptive names over short ones.

### Import Organization

Ruff handles import sorting automatically. Imports must follow this order (enforced by isort rules in Ruff):

1. Standard library (`os`, `asyncio`, `datetime`, `uuid`)
2. Third-party packages (`fastapi`, `pydantic`, `pydantic_ai`, `asyncpg`)
3. Local application imports (`src.db.client`, `src.agent.tools`)

Each group is separated by a blank line. Use absolute imports throughout — no relative imports.

```python
import os
from datetime import datetime
from uuid import UUID

from asyncpg import Pool
from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.config import MODEL_NAME
from src.db.queries import get_videos
```

---

## Type Hints

Type hints are mandatory on all function signatures (parameters and return types). This project uses Pydantic throughout, making type safety a first-class concern.

### Rules

- All function parameters must have type annotations.
- All function return types must be annotated (use `-> None` explicitly when applicable).
- Use modern Python 3.12 syntax: `str | None` instead of `Optional[str]`, `list[str]` instead of `List[str]`.
- Use `Any` sparingly and only when genuinely needed. Prefer specific types.
- Pydantic models are the preferred way to define structured data — use them for API schemas, database results, agent responses, and graph state.

```python
async def search_videos(query: str, limit: int = 10) -> list[VideoSummary]:
    ...

def get_model_string() -> str:
    ...

async def create_pool() -> Pool:
    ...
```

### Pydantic Model Conventions

- All fields must have type annotations.
- Use `Field()` for default values, descriptions, and validation constraints.
- Use `model_config` for model-level settings (not the legacy `Config` inner class).
- Models used as API schemas should have descriptive field names — avoid single-letter abbreviations.

```python
class VideoMetadata(BaseModel):
    """Metadata for a collected YouTube video."""

    video_id: str
    channel_id: str
    title: str
    description: str | None = None
    published_at: datetime | None = None
    view_count: int | None = None
    embedding: list[float] | None = Field(default=None, exclude=True)
```

---

## Async Patterns

The entire stack is async-native (FastAPI, asyncpg, Pydantic AI, LangGraph). Follow these conventions:

### Rules

- All I/O-bound functions must be `async`. This includes database queries, HTTP calls, agent invocations, and file operations.
- Never use synchronous blocking calls (`time.sleep`, synchronous `requests`, `psycopg2`) in async code. Use `asyncio.sleep`, `httpx`, and `asyncpg` respectively.
- Use `asyncio.gather()` for concurrent independent operations (e.g., fetching data from multiple sources simultaneously).
- Use `asyncio.TaskGroup` (Python 3.11+) for structured concurrency when tasks are interdependent.
- Never catch `BaseException` or bare `except:` in async code — it can swallow cancellation signals.

### Connection Pool Management

Database connection pools are created once during application startup (via FastAPI lifespan) and passed as dependencies. Never create pools inside request handlers or agent tools.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()
    yield
    await close_pool(app.state.pool)
```

---

## Error Handling

### Rules

- Use specific exception types. Never raise bare `Exception` or catch broad exceptions without re-raising.
- Define custom exception classes for domain-specific errors. Place them in the module where they originate.
- API endpoints should catch domain exceptions and return structured error responses — never let raw tracebacks reach the client.
- Collectors should log errors and continue. A single failed video fetch should not abort the entire collection cycle.
- Agent tools should raise descriptive errors that the LLM can interpret. The agent needs to understand what went wrong to decide its next action.

```python
class CollectionError(Exception):
    """Raised when a collector encounters a non-recoverable error."""

class VideoNotFoundError(CollectionError):
    """Raised when a specific video cannot be found via the API."""
```

### Logging

Use Python's built-in `logging` module with structured context. Every module should get its own logger.

```python
import logging

logger = logging.getLogger(__name__)

async def collect(self) -> int:
    """Run a collection cycle for all configured channels."""
    logger.info("Starting collection cycle", extra={"channels": len(self.channels)})
    ...
    logger.error("Failed to fetch video", extra={"video_id": vid, "error": str(e)})
```

Do not use `print()` for any operational output. Use logging at the appropriate level: `DEBUG` for development detail, `INFO` for operational events, `WARNING` for recoverable issues, `ERROR` for failures.

---

## Architectural Boundaries

These boundaries are non-negotiable. They are enforced by module structure, not convention. Violating them is a build-breaking offense.

### Collector / Reasoning Separation

| Rule | Collector Module (`src/collector/`) | Agent Module (`src/agent/`) |
|------|-------------------------------------|----------------------------|
| **Allowed imports** | `httpx`, `asyncpg`, `pydantic`, external API clients | `pydantic_ai`, `langfuse`, `src.db` |
| **Forbidden imports** | `pydantic_ai`, `langfuse` | `apscheduler`, `httpx` (no direct HTTP calls) |
| **Trigger** | Scheduled (APScheduler) | Human interaction only |
| **Token spend** | Zero | Proportional to human interactions |

**The test:** If `src/collector/` imports from `pydantic_ai` or `langfuse`, the boundary is violated. If `src/agent/` imports from `apscheduler` or makes direct HTTP calls to external APIs, the boundary is violated.

### Layer Dependencies

Dependencies flow downward only. No module may import from a module above it in the layer hierarchy.

```
Application Layer  (src/api/)
       ↓
Agent Layer        (src/agent/, src/orchestration/)
       ↓
Collector Layer    (src/collector/)      Observability (src/observability/)
       ↓                                        ↓
Data Layer         (src/db/)
       ↓
Configuration      (src/config.py)
```

- `src/api/` may import from `src/agent/`, `src/db/`, `src/config.py`.
- `src/agent/` may import from `src/db/`, `src/observability/`, `src/config.py`.
- `src/collector/` may import from `src/db/`, `src/config.py`.
- `src/db/` may import from `src/config.py`.
- No module imports from `src/api/`.

### Database Access

All database queries go through `src/db/queries.py`. No raw SQL in agent, collector, or API code. The query layer returns typed Pydantic models — never raw rows or dicts.

---

## Testing Conventions

### Rules

- Use **Pytest** with **pytest-asyncio** for all tests.
- Test files mirror the source structure: `tests/test_collector.py`, `tests/test_agent.py`, `tests/test_api.py`.
- Use fixtures in `tests/conftest.py` for shared setup (database pools, test clients, mock providers).
- Mock external dependencies (YouTube API, LLM providers) — never make real network calls in tests.
- Agent tests should use Pydantic AI's test/mock model support.
- API tests should use `httpx.AsyncClient` with the FastAPI test client.

### Boundary Verification Tests

Include tests that verify architectural boundaries by inspecting imports:

```python
def test_collector_has_no_llm_imports():
    """Verify the collector module does not import LLM dependencies."""
    import ast
    # Parse collector source files and assert no pydantic_ai or langfuse imports
```

### Test Naming

Test names should describe the behavior being verified, not the implementation:

```python
# Good
async def test_collector_stores_video_metadata_in_postgres():
async def test_agent_returns_source_cited_response():
async def test_provider_switch_requires_no_code_changes():

# Bad
async def test_youtube_collector():
async def test_agent_run():
```

---

## Dependency and Configuration Management

### Environment Variables

All configuration flows through environment variables loaded via `python-dotenv`. The canonical list lives in `.env.example` with comments explaining each variable.

- Never hardcode secrets, API keys, or connection strings.
- Every env var must have a sensible default in code (pointing to bundled Docker services) so that `docker compose --profile bundled up` works without any `.env` file.
- Use `src/config.py` as the single source of truth for loading and exposing configuration. Other modules import from `config.py` — they never read `os.getenv` directly.

### Package Management

- Use **uv** for all dependency management. Never use pip directly.
- All dependencies are declared in `pyproject.toml`.
- Lock files (`uv.lock`) are committed to the repository.
- Pin major versions for critical dependencies (Pydantic AI, LangGraph, FastAPI). Allow patch updates.

---

## Git and Workflow Conventions

### Commit Messages

Use conventional commit format:

```
feat: add YouTube transcript fetching to collector
fix: handle missing video descriptions in metadata parsing
refactor: extract base collector interface from YouTube collector
docs: add shared infrastructure setup guide to README
test: add boundary verification tests for collector imports
```

### Branch Strategy

- `main` is the stable branch. All merges go through pull requests.
- Feature branches: `feat/collector-base-interface`, `feat/langfuse-integration`.
- Fix branches: `fix/async-pool-cleanup`.
- Keep branches short-lived. Merge frequently.

---

## Common Patterns

### Dependency Injection via FastAPI

Pass shared resources (database pool, configuration) through FastAPI's `app.state` or dependency injection — not through global variables.

```python
@router.post("/api/ask")
async def ask(request: Request, body: AskRequest):
    pool = request.app.state.pool
    result = await agent.run(body.question, deps=pool)
```

### Repository Pattern for Database Access

`src/db/queries.py` acts as the repository layer. Every database operation is an async function that accepts a pool and returns typed models. This keeps SQL isolated and makes the data layer independently testable.

```python
async def get_videos(pool: Pool, channel_id: str, limit: int = 20) -> list[VideoModel]:
    """Fetch recent videos for a channel, ordered by publish date."""
    rows = await pool.fetch(
        "SELECT * FROM youtube_videos WHERE channel_id = $1 ORDER BY published_at DESC LIMIT $2",
        channel_id,
        limit,
    )
    return [VideoModel(**row) for row in rows]
```

### Model-Agnostic Provider Pattern

The agent layer never references a specific LLM provider. It uses a model string from configuration. Swapping providers is a `.env` change.

```python
from src.config import get_model_string

agent = Agent(
    model=get_model_string(),
    system_prompt="...",
    tools=[...],
    result_type=AgentResponse,
)
```

### Structured Agent Output

All agent responses use Pydantic models as `result_type`. Never return unstructured strings from agents.

```python
class AgentResponse(BaseModel):
    """Structured response from the YouTube research agent."""

    answer: str
    sources: list[Source]
    confidence: float
```

---

## What Not to Do

- **Do not** add dependencies without adding them to `pyproject.toml` and running `uv sync`.
- **Do not** write synchronous database or HTTP code anywhere in the application.
- **Do not** import across architectural boundaries (see the boundary rules above).
- **Do not** put raw SQL in agent, collector, or API modules.
- **Do not** create global mutable state. Use FastAPI lifespan and dependency injection.
- **Do not** suppress or silence exceptions without logging them.
- **Do not** design interfaces in the abstract. Build one real implementation first, then extract the interface.
- **Do not** add tools to the kit that have not been validated through a real downstream project.
- **Do not** use `print()` for operational output. Use the `logging` module.
- **Do not** skip type hints on any function signature.
