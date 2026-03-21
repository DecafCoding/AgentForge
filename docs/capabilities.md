# AgentForge — Capabilities Overview

*Version 0.6.0 | March 2026*

---

## What It Is

AgentForge is an opinionated, open-source, code-first Python stack for building AI agents. It ships pre-integrated tooling with enforced architectural patterns — not a framework with rigid constraints, but a curated foundation with sensible defaults. Clone the repo, run one command, start writing agent logic. The boring plumbing is already done.

**Tech stack:** Python 3.12, uv, FastAPI, Pydantic AI, LangGraph, Postgres 15 + pgvector, Alembic, APScheduler, Langfuse, Docker Compose, Ruff, Pytest.

---

## Architecture

AgentForge enforces strict layer boundaries through module structure. Dependencies flow downward only — no module imports from a layer above it.

```
Application Layer    (src/api/)
       ↓
Agent Layer          (src/agent/, src/orchestration/)
       ↓
Collector Layer      (src/collector/)       Observability (src/observability/)
       ↓                                          ↓
Data Layer           (src/db/)
       ↓
Configuration        (src/config.py)
```

The most important boundary: **collectors never touch LLMs**, and **agents never make direct HTTP calls**. Collectors fetch and store data on a schedule at zero token cost. Agents reason over that data only when a human asks. This separation is enforced by boundary verification tests that parse source files and fail CI if violated.

---

## Agent Patterns

### Pattern 1 — Single Agent (Pydantic AI)

A single Pydantic AI agent with registered tools for database queries and web search. Returns structured output (`AgentResponse` with answer, sources, and confidence score). Best for straightforward questions and lookup tasks.

- **Endpoint:** `POST /api/ask`
- **Tools available:** query recent videos, search videos by keyword, get channel statistics, web search
- **Output:** Structured JSON with cited sources and confidence score
- **Observability:** Single Langfuse trace per call

### Pattern 1b — Memory-Aware Agent

Extends Pattern 1 with Mem0 long-term memory. The agent retrieves relevant memories from previous sessions via semantic search, injects them into a dynamic system prompt, runs the query, and stores the interaction for future recall.

- **Endpoint:** `POST /api/ask/memory`
- **Memory backend:** Postgres with pgvector (same database as application data)
- **Embedding model:** OpenAI text-embedding-3-small
- **User scoping:** Separate memory per user ID

### Pattern 2 — Multi-Agent Workflow (LangGraph + Pydantic AI)

Three Pydantic AI agents composed into a LangGraph workflow with conditional routing:

1. **Research Agent** — Queries the database and gathers raw findings
2. **Analysis Agent** — Evaluates research quality, identifies gaps, assigns a quality score
3. **Synthesis Agent** — Combines findings into a final answer with citations

The analysis agent's `quality_score` drives routing: scores below 0.3 send the workflow back to research (up to 3 retries). This creates a self-correcting loop — the system keeps researching until it has enough data to produce a quality answer.

- **Endpoint:** `POST /api/research`
- **Output:** Same `AgentResponse` shape as Pattern 1 for API consistency
- **Observability:** Single parent Langfuse trace with per-node child spans

### Model-Agnostic Design

Agents never reference a specific LLM provider. The model string is resolved at runtime from environment variables. Swapping providers is a `.env` change — zero code modifications required.

| Provider | Configuration |
|----------|--------------|
| OpenAI | `MODEL_PROVIDER=openai`, `MODEL_NAME=gpt-4o` |
| Groq | `MODEL_PROVIDER=groq`, `MODEL_NAME=llama-3.1-70b-versatile` |
| Ollama (local) | `MODEL_PROVIDER=ollama`, `MODEL_NAME=llama3.1:8b` |

---

## Data Collection

Collectors are scheduled, deterministic data-fetching components that run via APScheduler. They write to Postgres and spend zero LLM tokens.

### YouTube Collector

Monitors YouTube channels on a configurable schedule (default: every 60 minutes). Fetches video metadata and transcripts from the YouTube Data API v3 and youtube-transcript-api.

**Collection strategy:**
- One channel checked per scheduler run
- Priority queue: never-checked channels first, then oldest `last_checked_at`
- Channels checked within the last 3 days are skipped
- 5 most recent videos fetched per channel per cycle
- Transcripts skipped for videos over 1 hour
- Transcripts only fetched for new videos or existing videos missing transcripts
- Individual video failures are logged and skipped — they don't abort the cycle

**Data captured:** video ID, channel ID, title, description, published date, view/like/comment counts, ISO 8601 duration, full transcript text.

### Web Scraper

Scrapes configured web pages on a schedule (default: every 6 hours) using Crawl4AI for async HTML-to-markdown extraction. Stores results in a `scraped_pages` table.

- **Configuration:** `SCRAPE_URLS` (comma-separated list), `SCRAPE_INTERVAL_MINUTES`
- Individual URL failures don't abort the cycle

### Scheduling

APScheduler 4.x runs in-process via FastAPI's lifespan hook. Collectors are registered with interval triggers at startup and shut down gracefully on app termination. Manual collection is also available via `scripts/collect.py`.

---

## Web Search

Two search providers, one interface. The agent's `web_search` tool routes to whichever is configured.

| Provider | Type | Configuration | Limits |
|----------|------|--------------|--------|
| Brave Search | Cloud API | `BRAVE_SEARCH_API_KEY` | 2,000 queries/month free |
| SearXNG | Self-hosted | `SEARXNG_HOST` | No API keys, no limits |

Both return the same `SearchResult` model. Switch providers by changing `SEARCH_PROVIDER` in `.env`.

---

## Database

Postgres 15 with pgvector extension. All queries go through `src/db/queries.py` — no raw SQL anywhere else in the codebase. Every query function is async, accepts a connection pool, and returns typed Pydantic models.

**Schema:**
- `youtube_channels` — Tracked channels with `last_checked_at` for scheduling priority
- `youtube_videos` — Video metadata, transcripts, and a `vector(1536)` embedding column (reserved for future vector similarity)
- `scraped_pages` — Web scraper results with JSONB metadata
- `evaluation_runs` — Ragas evaluation history with JSONB results

**Migrations:** Alembic with version-controlled migration files. Run `uv run alembic upgrade head` to apply.

---

## Observability

Langfuse v2 integration traces every LLM interaction. Deployed as a bundled Docker service (UI on port 3001).

**What's traced:**
- Every agent call (Pattern 1): prompt, response, token usage, latency
- Every workflow execution (Pattern 2): parent trace with per-node child spans
- Memory-aware calls: memory context metadata included
- Tool calls: each tool invocation recorded as a child span

**Graceful degradation:** If Langfuse credentials are missing, tracing is silently disabled — the application runs normally without observability.

---

## Evaluation

Ragas integration for measuring agent response quality. The pipeline converts Langfuse traces into evaluation datasets and runs quality metrics.

**Metrics:**
- **Faithfulness** — Is the answer supported by the retrieved context?
- **Response Relevancy** — Does the answer address the question?
- **Context Precision** — Is the retrieved context relevant to the question?
- **Context Recall** (supervised) — Does the context cover the ground truth? (requires reference answers)

**Workflow:** Export traces from Langfuse → build Ragas dataset → run evaluation → store results in `evaluation_runs` table for historical tracking.

**Scripts:** `scripts/export_dataset.py` (export), `scripts/evaluate.py` (run evaluation).

---

## MCP Server

AgentForge exposes its agents as Model Context Protocol tools via FastMCP 2.0, making them available to Claude Desktop and other MCP-compatible clients.

**Exposed tools:**
- `ask_agent(question)` — Pattern 1 single agent
- `search_videos(query, limit)` — Direct database search (no LLM)
- `get_channel_summary(channel_id)` — Channel statistics
- `run_research_workflow(query)` — Pattern 2 multi-agent workflow

**Transports:** Stdio (Claude Desktop) or HTTP (remote clients, configurable port).

---

## Caching

Optional Redis/Valkey caching layer (Phase 4, disabled by default). All cache operations silently fail if Redis is unavailable — cache downtime never breaks agent responses.

- **Operations:** get, set, delete, with JSON serialization helpers
- **TTL:** Default 1 hour, configurable per key
- **Enable:** `CACHE_ENABLED=true` + `docker compose --profile cache up`

---

## Frontend

React 18 single-page application with Vite, shadcn/ui components, and TanStack Query for API integration. Provides a chat interface for interacting with agents. Deployed alongside the API via Docker Compose.

---

## API

FastAPI with async lifespan management. Resources (database pool, scheduler, memory store, cache) are initialized at startup and cleaned up at shutdown.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (database status, version) |
| `/api/ask` | POST | Pattern 1 — single agent query |
| `/api/research` | POST | Pattern 2 — multi-agent research workflow |
| `/api/ask/memory` | POST | Pattern 1b — memory-aware agent query |

All endpoints return structured JSON. Errors return structured error responses — raw tracebacks never reach the client.

---

## Deployment

### Development

```bash
uv sync                                    # Install dependencies
docker compose --profile bundled up -d     # Start all services (Postgres, Langfuse, etc.)
uv run alembic upgrade head                # Run migrations
uv run python scripts/seed.py @Channel     # Seed YouTube channels
uv run uvicorn src.api.main:app --reload   # Start API
```

### Docker Compose Profiles

| Profile | Services |
|---------|----------|
| `bundled` | Postgres, Langfuse (DB + server) — everything for local development |
| `local-ai` | Ollama, SearXNG — local LLM and search |
| `cache` | Redis/Valkey |
| *(default)* | Application only (expects external Postgres, Langfuse) |

### Production

- `docker-compose.prod.yml` for production overrides
- Caddy reverse proxy with automatic HTTPS via Let's Encrypt
- All secrets from environment variables

---

## Configuration

All configuration flows through `src/config.py` — no module reads `os.getenv` directly. Every variable has a sensible default pointing to bundled Docker services, so `docker compose --profile bundled up` works without any `.env` file.

**Key variables:**

| Category | Variables |
|----------|----------|
| LLM | `MODEL_PROVIDER`, `MODEL_NAME`, `OPENAI_API_KEY`, `GROQ_API_KEY` |
| Database | `DATABASE_URL` |
| YouTube | `YOUTUBE_API_KEY`, `COLLECTION_INTERVAL_MINUTES` |
| Web Scraping | `SCRAPE_URLS`, `SCRAPE_INTERVAL_MINUTES` |
| Search | `SEARCH_PROVIDER`, `BRAVE_SEARCH_API_KEY`, `SEARXNG_HOST` |
| Memory | `MEMORY_ENABLED`, `MEMORY_MODEL` |
| Observability | `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` |
| Cache | `CACHE_ENABLED`, `REDIS_URL` |
| Evaluation | `EVAL_MODEL`, `EVAL_DATASET_LIMIT` |
| MCP | `MCP_TRANSPORT`, `MCP_PORT` |
| Local AI | `OLLAMA_HOST` |
| Frontend | `CORS_ORIGINS`, `DOMAIN`, `VITE_API_BASE` |

---

## Testing

Pytest with pytest-asyncio. All external dependencies are mocked — no real network calls in tests.

**Coverage:**
- Collector unit tests (mocked YouTube API, mocked Crawl4AI)
- Agent instantiation and tool tests
- FastAPI route tests (httpx async client)
- LangGraph workflow routing tests
- Memory-aware agent tests
- Web search provider tests (Brave, SearXNG)
- Cache operation tests (mocked Redis)
- Evaluation pipeline tests (mocked Ragas)
- MCP tool definition tests
- Cross-agent tracing tests
- Architectural boundary verification (AST parsing — collectors can't import LLM deps, agents can't import scheduler/httpx)

**Run:** `uv run pytest`

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/seed.py` | Populate YouTube channels (accepts IDs or @handles) |
| `scripts/collect.py` | Run one manual collection cycle |
| `scripts/evaluate.py` | Run Ragas evaluation pipeline |
| `scripts/export_dataset.py` | Export Langfuse traces as evaluation dataset |
| `scripts/mcp_server.py` | Start MCP server (stdio or HTTP) |
| `scripts/pull_model.py` | Pull an Ollama model |

---

## Extensibility

### Adding a Collector

1. Create `src/collector/my_collector.py`, subclass `BaseCollector`
2. Implement `async collect() -> int`
3. Use `src.db.queries` for all database writes
4. Register in `src/collector/scheduler.py` with an interval trigger
5. Add Alembic migration if a new table is needed
6. Rule: zero `pydantic_ai` or `langfuse` imports

### Adding an Agent Tool

1. Write an async function in `src/agent/tools.py` with `RunContext[Pool]` as the first parameter
2. Add the backing query in `src/db/queries.py` if database access is needed
3. Write a descriptive docstring — it becomes the tool description the LLM sees
4. Register in the agent's `tools=[...]` list
5. Rule: zero `apscheduler` or direct `httpx` calls

### Switching LLM Providers

Change `MODEL_PROVIDER` and `MODEL_NAME` in `.env`. No code changes.
