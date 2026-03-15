# Phase 1 — Core Platform (Single Agent Pattern) → v0.1

*AgentForge Starter Kit*

---

## Purpose of This Document

This document contains everything an AI or developer needs to build Phase 1 of AgentForge from scratch. It is self-contained — no other documents are required. Phase 1 is the minimum viable kit: clone the repo, run one command, build a single agent end-to-end.

---

## What Phase 1 Delivers

A complete, working development stack for building AI agents in Python. A developer clones the repo, runs `docker compose --profile bundled up`, and has:

- A Postgres database with pgvector for storage and vector similarity search
- A Pydantic AI agent with tool registration and structured output
- A FastAPI API layer for interacting with the agent
- APScheduler running in-process for scheduled data collection
- Langfuse tracing on every agent call (prompt, response, tokens, cost, latency)
- Docker Compose orchestration with dual deployment support (laptop vs. server)
- A reference YouTube monitor agent demonstrating the full collector/reasoning separation pattern

---

## Project Name

**AgentForge** — an opinionated, open-source, code-first development stack for building AI agents in Python. It is a pre-wired stack with opinionated patterns and sensible defaults, not a framework with enforced constraints. Developers can follow the patterns or deviate.

---

## Core Architectural Principles

These four principles govern every decision. They are non-negotiable.

### 1. Collector/Reasoning Separation

The most important architectural boundary. Enforced by module structure, not convention.

- **Collector module** — imports: `httpx`, `asyncpg`, `pydantic`. Runs on schedule. Fetches external data. Stores to Postgres. Zero token spend.
- **Agent module** — imports: `pydantic-ai`, `langfuse`. Runs on human interaction only. Reads from Postgres. Invokes LLM. Token spend proportional to human interactions.
- **The boundary test:** If `src/collector/` imports from `pydantic_ai` or `langfuse`, the boundary is violated. If `src/agent/` imports from `apscheduler` or makes direct HTTP calls to external APIs, the boundary is violated.

**Why this matters:** Token cost stays proportional to human interactions, not data volume. A collector that runs hourly and fetches 500 records costs zero tokens. Swapping models never touches the collector.

### 2. Interface-Driven Extensibility

The core defines contracts. Skills and collectors are separate modules that implement those contracts. Adding a capability never changes the core.

**Critical rule:** No interface is designed in the abstract. Build one real implementation first, then extract the interface from what it actually needed.

### 3. Model-Agnostic Design

No collector or deterministic component depends on a specific LLM provider. The reasoning layer is isolated behind Pydantic AI's provider abstraction. Switching models is a config change (`MODEL_PROVIDER` + `MODEL_NAME` env vars), not a code change.

### 4. Shared Infrastructure vs. Bundled Services

Two deployment modes from a single Docker Compose file:

- **Developer laptop:** `docker compose --profile bundled up` — all services start (Postgres, Langfuse, app)
- **Dedicated server:** Set `DATABASE_URL`, `LANGFUSE_HOST`, etc. in `.env` → `docker compose up` — only the app starts, connects to shared infra

**Boundary rule:** A service belongs in shared infrastructure if it outlives any single project.

---

## Technology Stack

Every dependency for Phase 1, with its role and version constraint.

| Layer | Tool | Role | Notes |
|-------|------|------|-------|
| Language | Python 3.12 | Runtime | Stable, fully supported by all dependencies |
| Package Manager | `uv` | Dependency management, venv, lockfile | Rust-based, fast, modern standard |
| Agent Framework | `pydantic-ai` | Tool registration, structured output, provider abstraction | Core of every agent |
| Observability | `langfuse` | Traces, cost tracking, latency | Wired into every agent call |
| API | `fastapi` + `uvicorn` | ASGI backend | Async-native, OpenAPI out of the box |
| Scheduling | `apscheduler` | In-process scheduled tasks | Runs via FastAPI lifespan hook |
| Database | Postgres 15 + pgvector | Storage + vector similarity search | Raw Postgres, not full Supabase stack |
| Migrations | `alembic` | Schema versioning | Every schema change is a migration file |
| DB Driver | `asyncpg` | Async Postgres driver | Fastest async driver, direct query control |
| Data Models | `pydantic` | Validation throughout | Already a pydantic-ai dependency |
| HTTP Client | `httpx` | Async HTTP for collector API calls | Used in collectors only |
| YouTube Data | `google-api-python-client` | YouTube Data API v3 | Reference collector dependency |
| YouTube Transcripts | `youtube-transcript-api` | Transcript fetching | No quota consumption |
| Environment | `python-dotenv` | `.env` file loading | |
| Testing | `pytest` + `pytest-asyncio` + `httpx` | Test framework | Agent, API, and collector tests |
| Linting | `ruff` | Replaces flake8 + black + isort | Single fast tool |
| Orchestration | Docker Compose | Service management | Profiles for dual deployment |

### LLM Providers (Phase 1)

| Provider | Role | Configuration |
|----------|------|---------------|
| OpenAI | Primary | Native Pydantic AI provider. Most widely used. |
| Groq | Secondary | OpenAI-compatible API (`base_url` override). 300-500 tok/s for open-source models. |

**Provider switching pattern:**

```python
# src/config.py
import os

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")

# .env.example
MODEL_PROVIDER=openai        # openai | groq
MODEL_NAME=gpt-4o            # model name for the selected provider
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk-...
```

Switching providers requires changing two environment variables. Zero code changes.

---

## Project Structure

```
agentforge/
├── docker-compose.yml          # All services, profiles for bundled vs. shared
├── Dockerfile                  # python:3.12-slim based app container
├── .env.example                # All env vars with comments
├── pyproject.toml              # uv-managed, all dependencies
├── alembic.ini                 # Alembic configuration
├── README.md                   # Quickstart + architecture overview
│
├── src/
│   ├── __init__.py
│   ├── config.py               # Environment loading, provider config
│   │
│   ├── collector/              # Deterministic data collection — NO LLM imports
│   │   ├── __init__.py
│   │   ├── base.py             # Base collector pattern / interface
│   │   ├── models.py           # Pydantic models for collected data
│   │   ├── youtube.py          # Reference collector: YouTube video metadata
│   │   └── scheduler.py        # APScheduler setup and job registration
│   │
│   ├── agent/                  # LLM reasoning — only invoked on human interaction
│   │   ├── __init__.py
│   │   ├── agent.py            # Pydantic AI agent with tool registration
│   │   └── tools.py            # Agent tools (database queries, search, etc.)
│   │
│   ├── api/                    # FastAPI layer
│   │   ├── __init__.py
│   │   ├── main.py             # App factory, middleware, lifespan hook
│   │   ├── routes.py           # Route definitions (POST /api/ask, etc.)
│   │   └── schemas.py          # Request/response Pydantic models
│   │
│   ├── db/                     # Database layer
│   │   ├── __init__.py
│   │   ├── client.py           # asyncpg connection pool setup
│   │   ├── queries.py          # Typed async query functions
│   │   └── migrations/         # Alembic migration files
│   │       ├── env.py
│   │       └── versions/
│   │
│   └── observability/          # Langfuse integration
│       ├── __init__.py
│       └── tracing.py          # Client setup, trace decorators, context helpers
│
├── scripts/
│   ├── seed.py                 # Populate initial data (e.g., YouTube channels)
│   └── collect.py              # Manual collection trigger for testing
│
└── tests/
    ├── conftest.py             # Shared fixtures
    ├── test_collector.py       # Collector tests (no LLM mocking needed)
    ├── test_agent.py           # Agent tests (mock LLM provider)
    └── test_api.py             # API integration tests
```

---

## Container Architecture

```
docker-compose.yml
├── supabase-db         postgres:15 + pgvector     :5432   profile: bundled
├── langfuse-server     langfuse/langfuse           :3001   profile: bundled
├── langfuse-db         postgres:15                 :5433   profile: bundled
└── app                 python:3.12-slim            :8000   (always starts)
    ├── FastAPI (Uvicorn)
    ├── APScheduler (in-process via lifespan)
    └── Pydantic AI agent
```

### Docker Compose Pattern

```yaml
services:
  # --- Bundled infrastructure (laptop mode) ---
  supabase-db:
    image: postgres:15
    profiles: ["bundled"]
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: agentforge
    volumes:
      - supabase-data:/var/lib/postgresql/data
    # pgvector extension must be enabled in migration or init script

  langfuse-db:
    image: postgres:15
    profiles: ["bundled"]
    ports:
      - "5433:5432"
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse
      POSTGRES_DB: langfuse

  langfuse-server:
    image: langfuse/langfuse
    profiles: ["bundled"]
    ports:
      - "3001:3000"
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      NEXTAUTH_URL: http://localhost:3001
      NEXTAUTH_SECRET: mysecret
      SALT: mysalt
    depends_on:
      - langfuse-db

  # --- App container (always starts) ---
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: ${DATABASE_URL:-postgresql://postgres:postgres@supabase-db:5432/agentforge}
      LANGFUSE_HOST: ${LANGFUSE_HOST:-http://langfuse-server:3000}
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY:-pk-lf-...}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY:-sk-lf-...}
      MODEL_PROVIDER: ${MODEL_PROVIDER:-openai}
      MODEL_NAME: ${MODEL_NAME:-gpt-4o}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      GROQ_API_KEY: ${GROQ_API_KEY:-}
    depends_on:
      supabase-db:
        condition: service_started
        required: false

volumes:
  supabase-data:
```

---

## Product Backlog Items (PBIs)

### PBI 1.1 — Project Scaffolding

**Description:** `pyproject.toml` (uv-managed), ruff config, `.env.example`, project directory structure, `README.md` skeleton.

**Done when:** Project structure matches the architecture spec above. `uv sync` resolves all dependencies. Ruff is configured and passes on the empty project.

**Implementation details:**

- `pyproject.toml` must use `uv` as the build backend with all Phase 1 dependencies listed
- Ruff config in `pyproject.toml` with `[tool.ruff]` section: line length 88, Python 3.12 target, isort + flake8 equivalent rules
- `.env.example` with every env var, commented with purpose and example values
- All `__init__.py` files in place for every package
- `README.md` with skeleton sections: Quickstart, Architecture, Configuration, Development, Testing

### PBI 1.2 — Docker Compose Setup

**Description:** App container (python:3.12-slim), Postgres 15 + pgvector (bundled profile), Langfuse server + Langfuse DB (bundled profile), env var overrides for shared infra.

**Done when:** `docker compose --profile bundled up` starts all services. `docker compose up` starts only the app (and connects to external infra if env vars are set).

**Implementation details:**

- `Dockerfile`: Multi-stage build. Stage 1: install deps with `uv`. Stage 2: slim runtime image with only the app code and installed packages.
- Postgres container must enable pgvector extension (via init script or first migration)
- Langfuse server and its dedicated Postgres are both under the `bundled` profile
- App container has `depends_on` with `required: false` for bundled services (so it starts without them when connecting to external infra)
- Health checks on database containers before app starts

### PBI 1.3 — Database Layer

**Description:** asyncpg connection pool, Alembic migration setup, initial schema (pgvector extension enabled), typed async query functions.

**Done when:** `alembic upgrade head` creates all tables. Queries return typed Pydantic models.

**Implementation details:**

**`src/db/client.py`** — Connection pool setup:
- Create asyncpg connection pool from `DATABASE_URL` env var
- Pool lifecycle managed by FastAPI lifespan hook (create on startup, close on shutdown)
- Export `get_pool()` function for other modules

**`src/db/queries.py`** — Typed query functions:
- All queries are async functions that accept the pool and return Pydantic models
- Example: `async def get_videos(pool, channel_id: str) -> list[VideoModel]`
- No raw SQL in agent or collector code — all queries go through this module

**Alembic setup:**
- `alembic.ini` configured to read `DATABASE_URL` from environment
- `src/db/migrations/env.py` wired for async (asyncpg)
- Initial migration: enable `pgvector` extension, create base tables for the YouTube reference collector

**Initial schema (reference implementation):**

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE youtube_channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id VARCHAR NOT NULL UNIQUE,
    channel_name VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE youtube_videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id VARCHAR NOT NULL UNIQUE,
    channel_id VARCHAR NOT NULL REFERENCES youtube_channels(channel_id),
    title VARCHAR NOT NULL,
    description TEXT,
    published_at TIMESTAMPTZ,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER,
    duration VARCHAR,
    transcript TEXT,
    embedding vector(1536),
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_videos_channel ON youtube_videos(channel_id);
CREATE INDEX idx_videos_published ON youtube_videos(published_at DESC);
```

### PBI 1.4 — Collector Module

**Description:** APScheduler setup via FastAPI lifespan hook, base collector pattern, minimal reference collector (fetches YouTube video metadata and stores on schedule).

**Done when:** Collector runs on schedule, stores data in Postgres, has zero LLM imports.

**Implementation details:**

**`src/collector/base.py`** — Base collector pattern:
```python
from abc import ABC, abstractmethod
from asyncpg import Pool

class BaseCollector(ABC):
    """Base class for all collectors. NO LLM imports allowed in this module."""

    def __init__(self, pool: Pool):
        self.pool = pool

    @abstractmethod
    async def collect(self) -> int:
        """Run a collection cycle. Returns number of items collected."""
        ...
```

**`src/collector/youtube.py`** — Reference implementation:
- Uses `google-api-python-client` to fetch video metadata from configured channels
- Uses `youtube-transcript-api` to fetch transcripts
- Stores results in Postgres via `src/db/queries.py`
- Returns count of new/updated videos
- Imports: `httpx`, `asyncpg`, `pydantic`, `googleapiclient`, `youtube_transcript_api` — NO `pydantic_ai`, NO `langfuse`

**`src/collector/scheduler.py`** — APScheduler integration:
- Creates an `AsyncIOScheduler` instance
- Registers collector jobs with configurable intervals (from env vars)
- Exposes `start_scheduler()` and `shutdown_scheduler()` for the FastAPI lifespan hook

**`src/collector/models.py`** — Pydantic models for collected data:
```python
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class VideoMetadata(BaseModel):
    video_id: str
    channel_id: str
    title: str
    description: str | None
    published_at: datetime | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    duration: str | None
    transcript: str | None
```

### PBI 1.5 — Agent Module

**Description:** Pydantic AI agent with tool registration, structured output, database query tools.

**Done when:** Agent answers questions using stored data. Tools are registered and callable.

**Implementation details:**

**`src/agent/agent.py`** — Main agent setup:
```python
from pydantic_ai import Agent
from src.agent.tools import query_videos, search_videos, get_channel_stats
from src.config import MODEL_NAME

agent = Agent(
    model=MODEL_NAME,
    system_prompt="""You are a YouTube content research assistant.
    You have access to a database of YouTube video metadata and transcripts.
    Use your tools to find relevant information before answering.
    Always cite your sources with video titles and links.""",
    tools=[query_videos, search_videos, get_channel_stats],
    result_type=AgentResponse,
)
```

**`src/agent/tools.py`** — Agent tools (database query functions):
- `query_videos(channel_id: str, limit: int) -> list[VideoSummary]` — Fetch recent videos for a channel
- `search_videos(query: str) -> list[VideoSummary]` — Search videos by title/description
- `get_channel_stats(channel_id: str) -> ChannelStats` — Aggregate stats for a channel
- Tools read from Postgres via `src/db/queries.py`
- NO direct HTTP calls, NO scheduler imports

**Structured output:**
```python
from pydantic import BaseModel

class Source(BaseModel):
    title: str
    video_id: str
    url: str

class AgentResponse(BaseModel):
    answer: str
    sources: list[Source]
    confidence: float
```

### PBI 1.6 — Observability Integration

**Description:** Langfuse client setup, trace decorators, context helpers wired into every agent call.

**Done when:** Full reasoning chain visible in Langfuse — prompt, response, tokens, cost, latency.

**Implementation details:**

**`src/observability/tracing.py`:**
- Initialize Langfuse client from env vars (`LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`)
- Pydantic AI has native Langfuse integration — configure the agent to use Langfuse as the instrumentation backend
- Every agent `run()` call should produce a Langfuse trace with:
  - The full prompt sent to the model
  - The model's response
  - Token count (prompt + completion)
  - Estimated cost
  - Latency (total and per-tool-call)
  - Model and provider used
- Export helper functions for creating traces in non-agent contexts if needed

### PBI 1.7 — API Layer

**Description:** FastAPI app factory, middleware, routes for agent interaction (`POST /api/ask`), request/response schemas.

**Done when:** API accepts questions and returns agent-generated, source-cited answers.

**Implementation details:**

**`src/api/main.py`** — App factory with lifespan:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.db.client import create_pool, close_pool
from src.collector.scheduler import start_scheduler, shutdown_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.pool = await create_pool()
    await start_scheduler(app.state.pool)
    yield
    # Shutdown
    await shutdown_scheduler()
    await close_pool(app.state.pool)

def create_app() -> FastAPI:
    app = FastAPI(title="AgentForge", lifespan=lifespan)
    app.include_router(routes.router)
    return app
```

**`src/api/routes.py`:**
```python
from fastapi import APIRouter, Request
from src.api.schemas import AskRequest, AskResponse
from src.agent.agent import agent

router = APIRouter(prefix="/api")

@router.post("/ask", response_model=AskResponse)
async def ask(request: Request, body: AskRequest):
    result = await agent.run(body.question, deps=request.app.state.pool)
    return AskResponse(
        answer=result.data.answer,
        sources=result.data.sources,
    )
```

**`src/api/schemas.py`:**
```python
from pydantic import BaseModel
from src.agent.tools import Source

class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
```

### PBI 1.8 — Model Provider Configuration

**Description:** OpenAI (primary) + Groq (secondary), env-based provider switching, `.env.example` with all provider options.

**Done when:** Switching providers requires changing two env vars, zero code changes.

**Implementation details:**

**`src/config.py`:**
```python
import os
from dotenv import load_dotenv

load_dotenv()

# LLM Provider Configuration
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@supabase-db:5432/agentforge")

# Langfuse
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://langfuse-server:3000")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")

# Collector
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
COLLECTION_INTERVAL_MINUTES = int(os.getenv("COLLECTION_INTERVAL_MINUTES", "60"))

def get_model_string() -> str:
    """Return the model string Pydantic AI expects based on provider config."""
    if MODEL_PROVIDER == "groq":
        return f"groq:{MODEL_NAME}"
    return f"openai:{MODEL_NAME}"
```

**Groq integration:** Groq exposes an OpenAI-compatible API. In Pydantic AI, it is the OpenAI provider with a `base_url` override. Pydantic AI may have native Groq support — check the latest docs. If not, configure as:
```python
from pydantic_ai.models.openai import OpenAIModel

groq_model = OpenAIModel(
    model_name="llama-3.1-70b-versatile",
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)
```

### PBI 1.9 — Testing & CI/CD

**Description:** Pytest skeleton with patterns for collector, agent, and API tests. GitHub Actions workflow for lint (ruff), test, build.

**Done when:** Tests pass in CI. Lint is enforced. New PRs run the full pipeline.

**Implementation details:**

**`tests/conftest.py`:**
- Shared fixtures: test database pool (use a test database or mock), mock LLM provider for agent tests
- Fixture for FastAPI test client using `httpx.AsyncClient`

**`tests/test_collector.py`:**
- Test that the collector fetches and stores data correctly
- Test that the collector has zero LLM imports (import verification test)
- Mock external APIs (YouTube API) to avoid network calls in tests

**`tests/test_agent.py`:**
- Test agent with mocked LLM provider (Pydantic AI supports test/mock models)
- Test that tools return expected data shapes
- Test structured output validation

**`tests/test_api.py`:**
- Test `POST /api/ask` with mocked agent
- Test request validation (missing fields, bad types)
- Test response schema compliance

**`.github/workflows/ci.yml`:**
```yaml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run ruff format --check .

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: agentforge_test
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run pytest tests/ -v
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/agentforge_test
```

### PBI 1.10 — Scripts & Seed Data

**Description:** `seed.py` for initial data population, `collect.py` for manual collection trigger.

**Done when:** Developer can populate data and trigger collection without the scheduler.

**Implementation details:**

**`scripts/seed.py`:**
- Accepts a list of YouTube channel IDs/URLs as arguments or from a config file
- Inserts channel records into the database
- Prints confirmation of what was seeded
- Runnable via: `uv run python scripts/seed.py`

**`scripts/collect.py`:**
- Instantiates the YouTube collector
- Runs a single collection cycle
- Prints results (number of videos collected, any errors)
- Runnable via: `uv run python scripts/collect.py`

### PBI 1.11 — Documentation

**Description:** README quickstart (clone to working agent in <15 min), architecture overview, `.env.example` with comments, shared infrastructure setup guide.

**Done when:** A new developer can follow the README and have a working agent without asking questions.

**Implementation details:**

**README.md sections:**

1. **What is AgentForge** — One paragraph explaining the kit
2. **Quickstart** — Step-by-step from clone to working agent:
   - Clone the repo
   - Copy `.env.example` to `.env`, fill in API keys
   - `docker compose --profile bundled up`
   - `uv run python scripts/seed.py` (add channels)
   - `uv run python scripts/collect.py` (collect data)
   - `curl -X POST http://localhost:8000/api/ask -d '{"question": "..."}'`
3. **Architecture** — The layered architecture diagram, collector/reasoning separation explanation
4. **Configuration** — All env vars explained
5. **Development** — How to add a new collector, how to add a new agent tool
6. **Shared Infrastructure** — How to point the kit at existing Postgres/Langfuse on a server
7. **Testing** — How to run tests locally
8. **APScheduler Scaling Note** — When to move to a separate worker

---

## Acceptance Criteria (Phase 1 Complete)

All of these must be true:

1. `docker compose --profile bundled up` starts all services (app, Postgres + pgvector, Langfuse server, Langfuse DB)
2. `docker compose up` starts only the app container (connects to external infra via env vars)
3. `alembic upgrade head` creates all tables with pgvector extension enabled
4. `uv run python scripts/seed.py` populates initial YouTube channel data
5. `uv run python scripts/collect.py` triggers a collection cycle that stores video metadata in Postgres
6. The collector runs automatically on the configured schedule via APScheduler
7. `POST /api/ask` with a question returns a structured, source-cited answer from the agent
8. The full agent reasoning chain is visible in Langfuse (prompt, response, tokens, cost, latency)
9. Changing `MODEL_PROVIDER` and `MODEL_NAME` env vars switches between OpenAI and Groq with zero code changes
10. `ruff check .` and `ruff format --check .` pass
11. `pytest tests/` passes
12. GitHub Actions CI runs lint, test, and build on every push/PR
13. A new developer can clone the repo, follow the README, and have a working agent in under 15 minutes
14. The `src/collector/` module has zero imports from `pydantic_ai` or `langfuse`
15. The `src/agent/` module has zero imports from `apscheduler` and makes no direct HTTP calls

---

## What Is NOT in Phase 1

These are explicitly excluded and deferred to later phases:

- **LangGraph / multi-agent orchestration** → Phase 2
- **Frontend / UI** → Phase 6
- **Authentication / authorization** → Not in MVP (single-user, private deployment)
- **Full Supabase stack** (GoTrue, Kong, Storage, Realtime) → Not planned
- **Local model serving** (Ollama, vLLM) → Phase 4
- **Long-term memory** (Mem0) → Phase 3
- **Web scraping** (Crawl4AI) → Phase 3
- **Evaluation pipelines** (Ragas) → Phase 5
- **MCP server exposure** (FastMCP) → Phase 5
- **Caching** (Redis/Valkey) → Phase 4
- **Reverse proxy / HTTPS** (Caddy) → Phase 6

---

*This document is the complete specification for Phase 1 of AgentForge. It contains everything needed to build the core platform without referencing external documents.*
