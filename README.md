# AgentForge

An opinionated, open-source, code-first Python stack for building AI agents. Clone the repo, run one command, start writing agent logic.

AgentForge is not a framework — it's a pre-wired stack with opinionated patterns and sensible defaults. The boring plumbing is already done. The architectural decisions are already made. Deviate freely.

**What's pre-integrated:**

| Layer | Tools |
|-------|-------|
| Agent | Pydantic AI · LangGraph |
| Data | Postgres 15 + pgvector · Alembic · asyncpg |
| Memory | Mem0 |
| Search | Brave Search · SearXNG (self-hosted) |
| Scraping | Crawl4AI |
| Local AI | Ollama |
| Caching | Redis / Valkey |
| Observability | Langfuse v2 |
| Scheduling | APScheduler |
| API | FastAPI |
| Frontend | React 18 · Vite · shadcn/ui · TanStack Query |
| Reverse Proxy | Caddy (automatic HTTPS) |
| Tooling | uv · Ruff · Pytest · Docker Compose |

---

## Quickstart

You will need:

- [Docker](https://docs.docker.com/get-docker/) with Compose v2
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- An **OpenAI API key** (or Groq / Ollama — see [Configuration](#configuration))
- A **YouTube Data API v3 key** — [create one in Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com) (free quota is sufficient)

### 1 — Clone and install

```bash
git clone https://github.com/DecafCoding/agentforge.git
cd agentforge
uv sync
```

### 2 — Configure

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```env
OPENAI_API_KEY=sk-...
YOUTUBE_API_KEY=AIza...
```

Everything else defaults to the bundled Docker services and can be left as-is for local development.

### 3 — Start all services

```bash
docker compose --profile bundled up -d
```

This starts:

| Container | Role | Port |
|-----------|------|------|
| `app` | FastAPI + APScheduler | 8000 |
| `frontend` | React SPA (nginx) | 3000 |
| `supabase-db` | Postgres 15 + pgvector | 5432 |
| `langfuse-server` | Langfuse v2 | 3001 |
| `langfuse-db` | Langfuse's Postgres | 5433 |

Wait ~15 seconds for Langfuse to finish its database migration before proceeding.

### 4 — Run database migrations

```bash
uv run alembic upgrade head
```

### 5 — Get your Langfuse API keys

1. Open [http://localhost:3001](http://localhost:3001)
2. Create a local account and project
3. Go to **Settings → API Keys** and create a key pair
4. Add the keys to `.env` and restart the app:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

```bash
docker compose --profile bundled restart app
```

### 6 — Seed channels and collect data

```bash
uv run python scripts/seed.py UCddiULmld79aDgK4aCiVDsw  # e.g. Fireship
uv run python scripts/collect.py
```

### 7 — Open the frontend

Navigate to [http://localhost:3000](http://localhost:3000) to chat with your agent through the browser UI.

Or call the API directly:

```bash
curl -s -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What topics has this channel covered recently?"}' \
  | python -m json.tool
```

Open [http://localhost:3001](http://localhost:3001) to see the full Langfuse trace — prompt, response, tokens, cost, and latency.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Application Layer                                   │
│  FastAPI · APScheduler · React Frontend             │
├─────────────────────────────────────────────────────┤
│  Agent Layer                                         │
│  Pydantic AI (single agent) · LangGraph (multi)     │
├──────────────────┬──────────────────────────────────┤
│  Collector Layer │  Observability                    │
│  No LLM imports  │  Langfuse                        │
├──────────────────┴──────────────────────────────────┤
│  Services Layer                                      │
│  Mem0 (memory) · Brave/SearXNG (search)             │
│  Crawl4AI (scraping) · Ollama (local AI)            │
│  Redis (caching)                                     │
├─────────────────────────────────────────────────────┤
│  Data Layer                                          │
│  Postgres 15 + pgvector · Alembic · asyncpg         │
├─────────────────────────────────────────────────────┤
│  Infrastructure                                      │
│  Docker Compose · Caddy · uv                        │
└─────────────────────────────────────────────────────┘
```

### Collector / Reasoning Separation

The most important architectural boundary:

| | Collector (`src/collector/`) | Agent (`src/agent/`) |
|---|---|---|
| **Trigger** | APScheduler (schedule) | HTTP request (human) |
| **Reads from** | External APIs | Postgres |
| **Writes to** | Postgres | — |
| **LLM imports** | ❌ Never | ✅ Always |
| **Token cost** | Zero | Proportional to requests |

They share the database and nothing else. Token cost stays proportional to human interactions, not data volume.

### Layer Dependencies

Dependencies flow downward only:

```
src/api/            → src/agent/, src/orchestration/, src/db/, src/config.py
src/agent/          → src/db/, src/observability/, src/memory/, src/config.py
src/orchestration/  → src/agent/, src/db/, src/config.py
src/collector/      → src/db/, src/config.py
src/db/             → src/config.py
src/config.py       → (no local imports)
```

### Project Structure

```
agentforge/
├── src/
│   ├── config.py               # All env vars — the only place os.getenv is called
│   ├── agent/                  # Pattern 1: single Pydantic AI agent
│   │   ├── agent.py            # run_agent() — standard agent
│   │   ├── memory_agent.py     # run_memory_agent() — memory-aware variant
│   │   ├── models.py           # AgentResponse, Source
│   │   └── tools.py            # Typed DB query wrappers for the agent
│   ├── orchestration/          # Pattern 2: LangGraph multi-agent workflow
│   │   ├── graph.py            # run_workflow() — research → analysis → synthesis
│   │   ├── nodes.py            # Individual agent nodes
│   │   └── state.py            # Pydantic workflow state
│   ├── collector/              # Deterministic data collection — NO LLM imports
│   │   ├── base.py             # BaseCollector ABC
│   │   ├── models.py           # Pydantic models for collected data
│   │   ├── youtube.py          # YouTube video metadata collector
│   │   ├── web_scraper.py      # Crawl4AI web scraping collector
│   │   └── scheduler.py        # APScheduler setup
│   ├── memory/                 # Mem0 long-term memory
│   │   ├── client.py           # Mem0 client factory
│   │   ├── store.py            # Mem0MemoryStore wrapper
│   │   └── helpers.py          # Memory formatting utilities
│   ├── search/                 # Web search providers
│   │   ├── brave.py            # Brave Search API client
│   │   └── searxng.py          # SearXNG self-hosted client
│   ├── cache/                  # Redis caching layer
│   │   └── client.py           # Cache pool and get/set helpers
│   ├── evaluation/             # Ragas evaluation pipelines
│   │   ├── pipeline.py         # End-to-end evaluation runner
│   │   ├── dataset.py          # Dataset export from Langfuse
│   │   ├── metrics.py          # Metric definitions
│   │   └── reporter.py         # Results formatting
│   ├── mcp/                    # FastMCP server exposure
│   │   └── server.py           # MCP tool definitions
│   ├── observability/
│   │   └── tracing.py          # Langfuse client
│   ├── db/                     # Database layer — all SQL lives here
│   │   ├── client.py           # asyncpg pool management
│   │   ├── queries.py          # Typed async query functions
│   │   └── migrations/         # Alembic migration files
│   └── api/                    # FastAPI application layer
│       ├── main.py             # App factory + lifespan hook
│       ├── routes.py           # /health, /api/ask, /api/research, /api/ask/memory
│       └── schemas.py          # Request/response Pydantic models
├── frontend/                   # React + Vite + shadcn/ui chat interface
│   ├── src/
│   │   ├── components/         # chat/, layout/, ui/ (shadcn)
│   │   ├── hooks/              # useAgent, useWorkflow (React Query)
│   │   ├── lib/                # api.ts (fetch client), utils.ts
│   │   └── types/              # api.ts (TypeScript types matching backend)
│   └── Dockerfile              # Multi-stage: node build → nginx serve
├── scripts/
│   ├── seed.py                 # Populate initial channel data
│   ├── collect.py              # Manual collection trigger
│   ├── evaluate.py             # Run evaluation pipeline
│   ├── export_dataset.py       # Export Langfuse traces as dataset
│   ├── mcp_server.py           # Start MCP server
│   └── pull_model.py           # Pull Ollama models
├── config/
│   ├── caddy/Caddyfile         # Reverse proxy + automatic HTTPS
│   └── searxng/settings.yml    # SearXNG configuration
├── docs/                       # Extended documentation
├── docker-compose.yml          # Development services
└── docker-compose.prod.yml     # Production overrides
```

---

## Agent Patterns

### Pattern 1 — Single Agent (`POST /api/ask`)

A Pydantic AI agent with typed tools and structured output. Tools query the database; the agent synthesises an answer with cited sources.

```bash
curl -s -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the most discussed topics?"}'
```

### Pattern 1b — Memory-Aware Agent (`POST /api/ask/memory`)

The single agent extended with Mem0 long-term memory. Requires `MEMORY_ENABLED=true`.

```bash
curl -s -X POST http://localhost:8000/api/ask/memory \
  -H "Content-Type: application/json" \
  -d '{"question": "What did we discuss last time?", "user_id": "user-123"}'
```

See [docs/memory-aware-agents.md](docs/memory-aware-agents.md) for details.

### Pattern 2 — Multi-Agent Workflow (`POST /api/research`)

A LangGraph pipeline that routes queries through three specialised Pydantic AI agents: Research → Analysis → Synthesis. Each agent has a focused role and the full workflow is traced as a single Langfuse trace with per-node spans.

```bash
curl -s -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Summarise recent trends in AI tooling"}'
```

See [docs/pattern-decision-guide.md](docs/pattern-decision-guide.md) to choose between Pattern 1 and Pattern 2.

---

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env`. Every variable has a default that works with `--profile bundled`.

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_PROVIDER` | `openai` | LLM provider: `openai` · `groq` · `ollama` |
| `MODEL_NAME` | `gpt-4o` | Model name for the selected provider |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `GROQ_API_KEY` | — | Groq API key |
| `DATABASE_URL` | bundled Postgres | asyncpg connection string |
| `LANGFUSE_HOST` | `http://localhost:3001` | Langfuse server URL |
| `LANGFUSE_PUBLIC_KEY` | — | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | — | Langfuse secret key |

### Collector

| Variable | Default | Description |
|----------|---------|-------------|
| `YOUTUBE_API_KEY` | — | YouTube Data API v3 key |
| `COLLECTION_INTERVAL_MINUTES` | `60` | Collector run interval |
| `SCRAPE_URLS` | — | Comma-separated URLs for web scraping |
| `SCRAPE_INTERVAL_MINUTES` | `360` | Web scraper run interval |

### Memory, Search & Caching

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMORY_ENABLED` | `true` | Enable Mem0 long-term memory |
| `MEMORY_MODEL` | `gpt-4o-mini` | Model for memory extraction |
| `SEARCH_PROVIDER` | `brave` | `brave` or `searxng` |
| `BRAVE_SEARCH_API_KEY` | — | Brave Search API key |
| `BRAVE_SEARCH_ENABLED` | `true` | Enable Brave Search tools |
| `SEARXNG_HOST` | `http://localhost:8080` | SearXNG base URL |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama base URL |
| `CACHE_ENABLED` | `false` | Enable Redis caching |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |

### Frontend & Deployment

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins (comma-separated) |
| `DOMAIN` | `localhost` | Domain for Caddy HTTPS |
| `VITE_API_BASE` | `/api` | Frontend API base path |

### Switching LLM Providers

Zero code changes — env vars only:

```env
# Groq (fast, free tier)
MODEL_PROVIDER=groq
MODEL_NAME=llama-3.1-70b-versatile
GROQ_API_KEY=gsk-...

# Ollama (fully local, no API key)
MODEL_PROVIDER=ollama
MODEL_NAME=llama3.1:8b
```

See [docs/local-ai-guide.md](docs/local-ai-guide.md) for the full local AI setup.

---

## Docker Profiles

| Command | What starts |
|---------|-------------|
| `docker compose up` | `app` + `frontend` |
| `docker compose --profile bundled up` | + Postgres, Langfuse, Ollama, SearXNG, Redis |
| `docker compose --profile local-ai up` | + Ollama, SearXNG |
| `docker compose --profile cache up` | + Redis |

---

## Development

### Running Tests

```bash
uv run pytest                          # all tests
uv run pytest -v --tb=short           # verbose
uv run pytest tests/test_collector.py  # single file
```

Tests are fully mocked — no database or LLM API needed. CI provisions a real `pgvector/pgvector:pg15` instance to validate migrations.

### Linting

```bash
uv run ruff check .        # lint
uv run ruff format .       # format
uv run ruff check --fix .  # lint + auto-fix
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev   # starts at http://localhost:5173, proxies /api to port 8000
```

### Adding a Collector

```python
# src/collector/my_source.py
from src.collector.base import BaseCollector

class MySourceCollector(BaseCollector):
    """Collects data from My Source."""

    async def collect(self) -> int:
        """Fetch and store data. Returns item count."""
        # fetch → store via queries → return count
```

Register in `src/collector/scheduler.py`. Add a migration for new tables. **Rule:** no `pydantic_ai` or `langfuse` imports in `src/collector/`.

### Adding an Agent Tool

```python
# src/db/queries.py — add the query
async def get_my_data(pool: Pool, param: str) -> list[MyRecord]:
    rows = await pool.fetch("SELECT ... WHERE x = $1", param)
    return [MyRecord(**dict(row)) for row in rows]

# src/agent/tools.py — add the tool
async def my_tool(ctx: RunContext[Pool], param: str) -> list[MyRecord]:
    """What this tool does and when to call it. Written for the LLM."""
    return await queries.get_my_data(ctx.deps, param)
```

Register in `src/agent/agent.py`. **Rule:** no `apscheduler` imports in `src/agent/`.

### Architectural Boundary Tests

Two tests parse source files with Python's `ast` module and fail if forbidden imports appear:

- `test_collector_has_no_llm_imports` — blocks `pydantic_ai` / `langfuse` in `src/collector/`
- `test_agent_has_no_scheduler_or_http_imports` — blocks `apscheduler` / `httpx` in `src/agent/`

---

## Production Deployment

For a full walkthrough from server setup to running HTTPS application, see [docs/deployment-guide.md](docs/deployment-guide.md).

**Quick reference:**

```bash
# Copy and configure production env
cp .env.production.example .env
# Edit DOMAIN, API keys, CORS_ORIGINS

# Start with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile bundled --profile prod up -d

# Run migrations
docker compose exec app alembic upgrade head
```

Caddy provisions Let's Encrypt certificates automatically when `DOMAIN` is set to a real domain.

---

## Evaluation

Run quality checks on your agent using Ragas:

```bash
# Export traces from Langfuse as a dataset
uv run python scripts/export_dataset.py

# Run evaluation pipeline
uv run python scripts/evaluate.py
```

See [docs/evaluation-guide.md](docs/evaluation-guide.md) for setup and metric interpretation.

---

## MCP Server

Expose your agent as a Model Context Protocol server for Claude Desktop or other MCP clients:

```bash
uv run python scripts/mcp_server.py
```

See [docs/mcp-integration.md](docs/mcp-integration.md) for client configuration.

---

## Further Reading

| Document | What It Covers |
|----------|---------------|
| [docs/pattern-decision-guide.md](docs/pattern-decision-guide.md) | When to use Pattern 1 vs Pattern 2 |
| [docs/local-ai-guide.md](docs/local-ai-guide.md) | Running fully local with Ollama + SearXNG |
| [docs/memory-aware-agents.md](docs/memory-aware-agents.md) | Mem0 long-term memory setup |
| [docs/deployment-guide.md](docs/deployment-guide.md) | Production server deployment |
| [docs/frontend-customization.md](docs/frontend-customization.md) | Modifying the React template |
| [docs/evaluation-guide.md](docs/evaluation-guide.md) | Ragas evaluation pipelines |
| [docs/mcp-integration.md](docs/mcp-integration.md) | MCP server and client setup |
| [docs/testing-patterns.md](docs/testing-patterns.md) | Agent and workflow testing patterns |
