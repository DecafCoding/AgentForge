# AgentForge

An opinionated, open-source, code-first Python stack for building AI agents. Clone the repo, run one command, start writing agent logic.

AgentForge is not a framework — it's a pre-wired stack with opinionated patterns and sensible defaults. The boring plumbing is already done. The architectural decisions are already made. Deviate freely.

**What's pre-integrated:** Postgres + pgvector · Pydantic AI · APScheduler · Langfuse · FastAPI · Alembic · Docker Compose · Ruff · Pytest

---

## Quickstart

You will need:

- [Docker](https://docs.docker.com/get-docker/) (with Compose v2)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- An **OpenAI API key** (or Groq — see [Configuration](#configuration))
- A **YouTube Data API v3 key** — [create one in Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com) (free quota is sufficient)

### 1 — Clone and install

```bash
git clone https://github.com/your-org/agentforge.git
cd agentforge
uv sync
```

### 2 — Configure

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```bash
OPENAI_API_KEY=sk-...          # or use GROQ_API_KEY with MODEL_PROVIDER=groq
YOUTUBE_API_KEY=AIza...
```

Everything else defaults to the bundled Docker services and can be left as-is for local development.

### 3 — Start all services

```bash
docker compose --profile bundled up -d
```

This starts four containers:

| Container | Role | Port |
|-----------|------|------|
| `app` | FastAPI + APScheduler | 8000 |
| `supabase-db` | Postgres 15 + pgvector | 5432 |
| `langfuse-server` | Langfuse v2 | 3001 |
| `langfuse-db` | Langfuse's Postgres | 5433 |

Wait ~15 seconds for Langfuse to finish its own database migration before proceeding.

### 4 — Run database migrations

```bash
uv run alembic upgrade head
```

Expected output: `Running upgrade  -> 0001, Initial schema: pgvector extension, youtube_channels, youtube_videos.`

### 5 — Get your Langfuse API keys

1. Open [http://localhost:3001](http://localhost:3001)
2. Create an account (local only, no external signup)
3. Create a project
4. Go to **Settings → API Keys** and create a key pair
5. Add the keys to your `.env`:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

6. Restart the app container to pick up the new keys:

```bash
docker compose --profile bundled restart app
```

### 6 — Seed channels and collect data

```bash
# Seed one or more YouTube channel IDs
uv run python scripts/seed.py UCddiULmld79aDgK4aCiVDsw  # e.g. Fireship

# Trigger an immediate collection cycle
uv run python scripts/collect.py
```

`collect.py` will print how many videos were stored. The first run may take 30–60 seconds depending on how many channels you seeded and their video counts.

### 7 — Ask the agent

```bash
curl -s -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What topics has this channel covered recently?"}' \
  | python -m json.tool
```

Expected response shape:

```json
{
  "answer": "The channel has recently covered ...",
  "sources": [
    {
      "title": "Video Title",
      "video_id": "abc123",
      "url": "https://www.youtube.com/watch?v=abc123"
    }
  ]
}
```

Open [http://localhost:3001](http://localhost:3001) to see the full trace — prompt, response, token count, cost, and latency.

---

## Architecture

```
┌─────────────────────────────────────────┐
│  Application Layer                       │
│  FastAPI  ·  APScheduler                │
├─────────────────────────────────────────┤
│  Agent Layer                             │
│  Pydantic AI                            │
├──────────────────┬──────────────────────┤
│  Collector Layer │  Observability Layer  │
│  No LLM imports  │  Langfuse            │
├──────────────────┴──────────────────────┤
│  Data Layer                              │
│  Postgres + pgvector  ·  Alembic        │
├─────────────────────────────────────────┤
│  Infrastructure Layer                    │
│  Docker Compose  ·  uv                  │
└─────────────────────────────────────────┘
```

### Collector / Reasoning Separation

The most important architectural boundary in the codebase:

| | Collector (`src/collector/`) | Agent (`src/agent/`) |
|---|---|---|
| **Trigger** | APScheduler (schedule) | HTTP request (human) |
| **Reads from** | External APIs | Postgres |
| **Writes to** | Postgres | — |
| **LLM imports** | ❌ Never | ✅ Always |
| **Token cost** | Zero | Proportional to requests |

They share the database and nothing else. Token cost stays proportional to human interactions, not to data volume.

### Project Structure

```
agentforge/
├── src/
│   ├── config.py               # All env vars — only place os.getenv is called
│   ├── collector/              # Deterministic data collection — NO LLM imports
│   │   ├── base.py             # BaseCollector ABC
│   │   ├── models.py           # Pydantic models for incoming data
│   │   ├── youtube.py          # Reference collector: YouTube video metadata
│   │   └── scheduler.py        # APScheduler setup
│   ├── agent/                  # LLM reasoning — only runs on human interaction
│   │   ├── models.py           # AgentResponse, Source (shared with API)
│   │   ├── tools.py            # Agent tools (typed DB query wrappers)
│   │   └── agent.py            # Pydantic AI agent + run_agent() traced runner
│   ├── api/                    # FastAPI layer
│   │   ├── main.py             # App factory + lifespan hook
│   │   ├── routes.py           # POST /api/ask, GET /health
│   │   └── schemas.py          # Request/response models
│   ├── db/                     # Database layer — all SQL lives here
│   │   ├── client.py           # asyncpg pool management
│   │   ├── queries.py          # Typed async query functions + DB models
│   │   └── migrations/         # Alembic migration files
│   └── observability/
│       └── tracing.py          # Langfuse client
├── scripts/
│   ├── seed.py                 # Populate initial channel data
│   └── collect.py              # Manual collection trigger
└── tests/
    ├── conftest.py             # Shared fixtures (mock pool, test client)
    ├── test_collector.py       # Boundary verification + collector unit tests
    ├── test_agent.py           # Agent tests (mocked LLM)
    └── test_api.py             # API integration tests
```

### Layer Dependencies

Dependencies flow downward only. No module imports from a layer above it.

```
src/api/         → src/agent/, src/db/, src/config.py
src/agent/       → src/db/, src/observability/, src/config.py
src/collector/   → src/db/, src/config.py
src/db/          → src/config.py
src/config.py    → (no local imports)
```

---

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` to get started. Every variable has a default that works with `--profile bundled`.

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PROVIDER` | `openai` | LLM provider: `openai` or `groq` |
| `MODEL_NAME` | `gpt-4o` | Model name for the selected provider |
| `OPENAI_API_KEY` | — | OpenAI API key (`sk-...`) |
| `GROQ_API_KEY` | — | Groq API key (`gsk-...`) |
| `DATABASE_URL` | bundled Postgres | asyncpg-compatible Postgres connection string |
| `LANGFUSE_HOST` | `http://localhost:3001` | Langfuse server base URL |
| `LANGFUSE_PUBLIC_KEY` | — | Langfuse project public key (`pk-lf-...`) |
| `LANGFUSE_SECRET_KEY` | — | Langfuse project secret key (`sk-lf-...`) |
| `YOUTUBE_API_KEY` | — | Google Cloud API key with YouTube Data API v3 enabled |
| `COLLECTION_INTERVAL_MINUTES` | `60` | How often the collector runs |

### Switching LLM providers

Switching between OpenAI and Groq requires **two env var changes and a container restart** — zero code changes:

```bash
# In .env
MODEL_PROVIDER=groq
MODEL_NAME=llama-3.1-70b-versatile
GROQ_API_KEY=gsk-...
```

```bash
docker compose --profile bundled restart app
```

Groq runs at 300–500 tokens/second and is free-tier friendly for development.

---

## Development

### Adding a new collector

Collectors are deterministic data-fetching components. They run on a schedule and have zero LLM imports.

**1. Create the collector:**

```python
# src/collector/my_source.py
from src.collector.base import BaseCollector
from src.db import queries

class MySourceCollector(BaseCollector):
    """Collects data from My Source."""

    async def collect(self) -> int:
        """Fetch and store data. Returns count of items upserted."""
        # fetch from external API (use asyncio.to_thread() for sync clients)
        # call queries.upsert_*() to store results
        return count
```

**2. Register the scheduler job** in `src/collector/scheduler.py`:

```python
from src.collector.my_source import MySourceCollector

collector = MySourceCollector(pool=pool)
await _scheduler.add_schedule(
    collector.collect,
    IntervalTrigger(minutes=COLLECTION_INTERVAL_MINUTES),
    id="my_source_collector",
)
```

**3. Add any new tables** as an Alembic migration:

```bash
uv run alembic revision -m "add my_source table"
# edit the generated file in src/db/migrations/versions/
uv run alembic upgrade head
```

**Rule:** No `pydantic_ai` or `langfuse` imports anywhere in `src/collector/`. The test suite enforces this automatically.

### Adding a new agent tool

Agent tools are typed async functions that give the LLM access to your data.

**1. Add the query** to `src/db/queries.py`:

```python
async def get_my_data(pool: Pool, param: str) -> list[MyRecord]:
    """Fetch my data for the given parameter."""
    rows = await pool.fetch("SELECT ... WHERE x = $1", param)
    return [MyRecord(**dict(row)) for row in rows]
```

**2. Add the tool** to `src/agent/tools.py`:

```python
async def my_tool(ctx: RunContext[Pool], param: str) -> list[MyRecord]:
    """Describe what this tool does and WHEN to use it.

    The docstring is sent to the LLM — write it for the model, not for humans.
    """
    return await queries.get_my_data(ctx.deps, param)
```

**3. Register the tool** in `src/agent/agent.py`:

```python
agent = Agent(
    ...
    tools=[..., my_tool],
)
```

**Rule:** No `apscheduler` imports in `src/agent/`. No direct HTTP calls — all data comes from the database.

### Running the linter

```bash
uv run ruff check .       # lint
uv run ruff format .      # format
uv run ruff check --fix . # lint + auto-fix
```

---

## Shared Infrastructure

If you already have Postgres and Langfuse running on a shared server (e.g. a homelab or VPS), you can skip the bundled services and point AgentForge at your existing instances.

**1. Create a database for this project** on your shared Postgres:

```sql
CREATE DATABASE agentforge;
```

**2. Set the connection env vars** in `.env`:

```bash
DATABASE_URL=postgresql://user:pass@your-server:5432/agentforge
LANGFUSE_HOST=http://your-server:3001
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

**3. Start only the app container:**

```bash
docker compose up -d          # no --profile bundled
```

**4. Run migrations** against your shared database:

```bash
uv run alembic upgrade head
```

The app container connects to your external Postgres and Langfuse. The bundled database containers are never started.

> **Topology note:** On a shared server, run one Postgres instance with a separate database per project. Postgres is a shared service; the app container is project-owned.

---

## Testing

```bash
# Run all tests
uv run pytest

# Verbose output with short tracebacks
uv run pytest -v --tb=short

# A specific file
uv run pytest tests/test_collector.py

# A specific test
uv run pytest tests/test_api.py::test_health_returns_200
```

Tests are fully mocked — no database or LLM API is needed to run them. The CI workflow provisions a real `pgvector/pgvector:pg15` Postgres to validate migrations.

### Architectural boundary tests

The test suite includes two tests that parse the collector and agent source files with the Python `ast` module and assert no forbidden imports exist:

- `test_collector_has_no_llm_imports` — fails if `pydantic_ai` or `langfuse` appear in `src/collector/`
- `test_agent_has_no_scheduler_or_http_imports` — fails if `apscheduler` or `httpx` appear in `src/agent/`

These run on every CI push and act as an automated architecture review.

---

## APScheduler Scaling Note

APScheduler 4.x runs in-process alongside FastAPI using the same asyncio event loop. This is the right default — it eliminates the operational overhead of a separate worker process for the vast majority of use cases.

**When to consider moving to a dedicated worker:**

- You need multiple app replicas (in-process scheduling would run jobs on every replica)
- A collection cycle is CPU-intensive and blocks the event loop
- You need persistent job state that survives container restarts
- You are running more than ~10 concurrent collection jobs

When you hit one of these thresholds, move the collector to a dedicated worker container using the same APScheduler code, or replace with a task queue (ARQ is a good async-native choice).
