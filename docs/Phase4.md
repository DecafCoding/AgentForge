# Phase 4 — Local AI & Caching → v0.4

*AgentForge Starter Kit*

---

## Purpose of This Document

This document contains everything an AI or developer needs to build Phase 4 of AgentForge. It is self-contained. Phase 4 adds local model serving (Ollama), self-hosted web search (SearXNG), and caching (Redis/Valkey) — making the kit viable for fully local, privacy-first workflows where no data leaves the machine.

---

## Prerequisites (Phases 1–3 Complete)

Phase 4 assumes the following are already built and working:

**From Phase 1:**
- Project structure with `uv`, `ruff`, Docker Compose (bundled + shared profiles)
- Postgres 15 + pgvector with Alembic migrations and asyncpg driver
- Pydantic AI agent with tool registration and structured output (Pattern 1)
- FastAPI API layer with lifespan hook and APScheduler
- Langfuse observability wired into all agent calls
- Collector/reasoning separation enforced by module structure
- OpenAI + Groq provider switching via env vars
- Pytest skeleton and GitHub Actions CI

**From Phase 2:**
- LangGraph multi-agent orchestration (Pattern 2)
- Graph state as Pydantic models, cross-agent Langfuse traces

**From Phase 3:**
- Mem0 long-term memory with Postgres backend
- Crawl4AI web scraping collector
- Brave Search web search tool for agents

---

## What Phase 4 Delivers

Three infrastructure additions that enable fully local, offline, privacy-first agent workflows:

1. **Ollama** — Local LLM serving. Run open-source models on your own hardware as a drop-in replacement for cloud providers. Critical for GPU sharing on a dedicated server.
2. **SearXNG** — Self-hosted web search engine. Agents can search the web without any external API calls or API keys.
3. **Redis/Valkey** — Caching layer for specific, measured bottlenecks. Not a premature optimization — only added to address a documented performance issue.

After this phase, a developer can run the entire AgentForge stack — including model inference, web search, and all agent capabilities — on a local machine or private server with zero external API dependencies.

---

## Design Philosophy

**These are all optional.** The kit works without Ollama, SearXNG, and Redis. Their Docker services are commented out by default or placed behind profiles. A developer who only uses cloud providers never has to think about them.

**Redis/Valkey is not added until something is measurably slow.** Premature caching adds infrastructure complexity without observable benefit. Phase 4 requires identifying a specific bottleneck before Redis is included.

**Ollama is shared infrastructure.** On a dedicated server running multiple projects, Ollama runs once and all projects connect to it via API. Running multiple Ollama instances fights over GPU memory. This follows the same shared infrastructure pattern established in Phase 1 for Postgres and Langfuse.

---

## Technology Additions

| Layer | Tool | Role |
|-------|------|------|
| Infrastructure | Ollama | Local LLM serving (GPU-accelerated) |
| Infrastructure | SearXNG | Self-hosted meta-search engine |
| Infrastructure | Redis / Valkey | Caching layer for measured bottlenecks |

Add to `pyproject.toml` (if any Python client libraries are needed):
```toml
[project]
dependencies = [
    # ... existing Phase 1-3 deps ...
    "redis",  # or "valkey" — only if caching is implemented
]
```

---

## Project Structure Changes

```
agentforge/
├── docker-compose.yml              # MODIFIED — Add Ollama, SearXNG, Redis services
├── .env.example                    # MODIFIED — Add local AI config vars
│
├── src/
│   ├── config.py                   # MODIFIED — Add Ollama provider config
│   │
│   ├── search/
│   │   ├── brave.py                # EXISTING — Brave Search API
│   │   └── searxng.py              # NEW — SearXNG search client
│   │
│   ├── cache/                      # NEW — Caching layer (only if bottleneck identified)
│   │   ├── __init__.py
│   │   └── client.py               # Redis/Valkey connection and cache helpers
│   │
│   ├── agent/
│   │   └── tools.py                # MODIFIED — Add unified search tool (Brave or SearXNG)
│
├── docs/
│   ├── local-ai-guide.md           # NEW — Running fully local with Ollama + SearXNG
│   └── gpu-sharing.md              # NEW — Ollama GPU sharing on dedicated servers
│
└── tests/
    ├── test_ollama_provider.py     # NEW — Ollama provider switching test
    ├── test_searxng.py             # NEW — SearXNG search tests
    └── test_cache.py               # NEW — Cache layer tests (if applicable)
```

---

## Product Backlog Items (PBIs)

### PBI 4.1 — Ollama Integration

**Description:** Docker service, Pydantic AI provider config, GPU sharing documentation.

**Done when:** A local model via Ollama is a drop-in replacement for a cloud provider by changing two env vars.

**Implementation details:**

**Docker Compose addition:**

```yaml
services:
  # --- Existing bundled services ---
  # supabase-db, langfuse-server, langfuse-db (from Phase 1)

  # --- Local AI infrastructure ---
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
    # GPU config is optional — Ollama falls back to CPU if no GPU is available

volumes:
  ollama-data:
```

**Provider configuration update in `src/config.py`:**

```python
# Existing providers
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")  # openai | groq | ollama
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

def get_model_string() -> str:
    """Return the model string Pydantic AI expects."""
    if MODEL_PROVIDER == "ollama":
        return f"ollama:{MODEL_NAME}"
    elif MODEL_PROVIDER == "groq":
        return f"groq:{MODEL_NAME}"
    return f"openai:{MODEL_NAME}"
```

**Pydantic AI Ollama integration:**

Pydantic AI has native `OllamaModel` support:

```python
from pydantic_ai.models.ollama import OllamaModel

# When MODEL_PROVIDER is "ollama":
model = OllamaModel(
    model_name=MODEL_NAME,  # e.g., "llama3.1:8b", "qwen2.5:32b", "mistral:7b"
    base_url=OLLAMA_HOST,
)
```

**Provider factory pattern:**

```python
# src/config.py
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.ollama import OllamaModel

def create_model():
    """Create the appropriate model based on provider config."""
    if MODEL_PROVIDER == "ollama":
        return OllamaModel(model_name=MODEL_NAME, base_url=OLLAMA_HOST)
    elif MODEL_PROVIDER == "groq":
        return OpenAIModel(
            model_name=MODEL_NAME,
            base_url="https://api.groq.com/openai/v1",
            api_key=GROQ_API_KEY,
        )
    else:
        return OpenAIModel(model_name=MODEL_NAME, api_key=OPENAI_API_KEY)
```

**Model pulling:** Ollama requires models to be pulled before first use. Add a helper script:

```python
# scripts/pull_model.py
"""Pull a model into Ollama. Run after Ollama container is up."""
import httpx
import os
import sys

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL = sys.argv[1] if len(sys.argv) > 1 else "llama3.1:8b"

response = httpx.post(f"{OLLAMA_HOST}/api/pull", json={"name": MODEL}, timeout=600)
print(f"Pulled {MODEL}: {response.status_code}")
```

**GPU sharing on a dedicated server:**

When multiple AgentForge projects run on the same server:
- One Ollama instance serves all projects
- Each project connects via `OLLAMA_HOST` env var pointing to the shared instance
- Ollama manages GPU memory allocation between concurrent requests
- Do NOT run multiple Ollama containers — they will fight over GPU memory

### PBI 4.2 — SearXNG Setup

**Description:** Self-hosted search engine, agent search tool integration.

**Done when:** Agents search the web without external API calls.

**Implementation details:**

**Docker Compose addition:**

```yaml
services:
  searxng:
    image: searxng/searxng
    profiles: ["bundled", "local-ai"]
    ports:
      - "8080:8080"
    volumes:
      - ./config/searxng:/etc/searxng
    environment:
      - SEARXNG_BASE_URL=http://localhost:8080/
```

**SearXNG configuration file (`config/searxng/settings.yml`):**

```yaml
use_default_settings: true
server:
  secret_key: "change-this-to-a-random-string"
  bind_address: "0.0.0.0"
search:
  formats:
    - html
    - json    # Required for API access
engines:
  # Enable engines relevant to agent use cases
  - name: google
    engine: google
    shortcut: g
  - name: duckduckgo
    engine: duckduckgo
    shortcut: ddg
  - name: wikipedia
    engine: wikipedia
    shortcut: wp
```

**`src/search/searxng.py`** — SearXNG client:

```python
import httpx
import os
from pydantic import BaseModel

SEARXNG_HOST = os.getenv("SEARXNG_HOST", "http://searxng:8080")

class SearchResult(BaseModel):
    title: str
    url: str
    description: str

async def search_web_local(query: str, count: int = 5) -> list[SearchResult]:
    """Search the web using self-hosted SearXNG. No external API keys needed."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SEARXNG_HOST}/search",
            params={"q": query, "format": "json", "number_of_results": count},
        )
        response.raise_for_status()
        data = response.json()

    results = []
    for item in data.get("results", [])[:count]:
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            description=item.get("content", ""),
        ))
    return results
```

**Unified search tool:**

The agent should have a single `web_search` tool that routes to either Brave or SearXNG based on configuration:

```python
# src/agent/tools.py
from src.search.brave import search_web as brave_search
from src.search.searxng import search_web_local as searxng_search

SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "brave")  # brave | searxng

async def web_search(query: str) -> list[dict]:
    """Search the web. Uses Brave or SearXNG based on SEARCH_PROVIDER config."""
    if SEARCH_PROVIDER == "searxng":
        results = await searxng_search(query, count=5)
    else:
        results = await brave_search(query, count=5)
    return [r.model_dump() for r in results]
```

### PBI 4.3 — Redis/Valkey Caching

**Description:** Caching layer for a specific, measured bottleneck.

**Done when:** Cache addresses a documented bottleneck with measurable improvement.

**IMPORTANT:** This PBI should only be implemented after a specific bottleneck has been identified and documented. Do not add caching speculatively.

**Implementation details (when a bottleneck is identified):**

**Docker Compose addition:**

```yaml
services:
  redis:
    image: redis:7-alpine  # or valkey/valkey:7-alpine
    profiles: ["bundled", "cache"]
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

volumes:
  redis-data:
```

**`src/cache/client.py`:**

```python
import redis.asyncio as redis
import os
import json
from typing import Optional

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "false").lower() == "true"

_pool: Optional[redis.Redis] = None

async def create_cache_pool() -> Optional[redis.Redis]:
    """Create Redis connection pool. Returns None if caching is disabled."""
    global _pool
    if not CACHE_ENABLED:
        return None
    _pool = redis.from_url(REDIS_URL, decode_responses=True)
    return _pool

async def close_cache_pool():
    global _pool
    if _pool:
        await _pool.close()

async def cache_get(key: str) -> Optional[str]:
    """Get a value from cache. Returns None if cache miss or caching disabled."""
    if not _pool:
        return None
    return await _pool.get(key)

async def cache_set(key: str, value: str, ttl_seconds: int = 3600):
    """Set a value in cache with TTL."""
    if not _pool:
        return
    await _pool.set(key, value, ex=ttl_seconds)
```

**Where caching might be valuable (identify before implementing):**
- Embedding generation for frequently queried content
- Database query results for expensive aggregations
- Web search results for repeated queries within a time window
- Agent responses for identical questions (with careful cache invalidation)

**Cache invalidation rules:**
- Every cached value must have a TTL (no indefinite caching)
- Document what invalidates each cache entry
- Caching should be transparent — the system works identically without it, just slower

---

## Updated Docker Compose (Full Phase 4)

```yaml
services:
  # --- Phase 1 bundled infrastructure ---
  supabase-db:
    image: postgres:15
    profiles: ["bundled"]
    # ... (unchanged from Phase 1)

  langfuse-server:
    image: langfuse/langfuse
    profiles: ["bundled"]
    # ... (unchanged from Phase 1)

  langfuse-db:
    image: postgres:15
    profiles: ["bundled"]
    # ... (unchanged from Phase 1)

  # --- Phase 4 local AI infrastructure ---
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

  redis:
    image: redis:7-alpine
    profiles: ["bundled", "cache"]
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

  # --- App container (always starts) ---
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: ${DATABASE_URL:-postgresql://postgres:postgres@supabase-db:5432/agentforge}
      LANGFUSE_HOST: ${LANGFUSE_HOST:-http://langfuse-server:3000}
      MODEL_PROVIDER: ${MODEL_PROVIDER:-openai}
      MODEL_NAME: ${MODEL_NAME:-gpt-4o}
      OLLAMA_HOST: ${OLLAMA_HOST:-http://ollama:11434}
      SEARCH_PROVIDER: ${SEARCH_PROVIDER:-brave}
      SEARXNG_HOST: ${SEARXNG_HOST:-http://searxng:8080}
      REDIS_URL: ${REDIS_URL:-redis://redis:6379/0}
      CACHE_ENABLED: ${CACHE_ENABLED:-false}
      # ... all other env vars ...

volumes:
  supabase-data:
  ollama-data:
  redis-data:
```

**Deployment modes after Phase 4:**

| Mode | Command | What Starts |
|------|---------|-------------|
| App only (shared infra) | `docker compose up` | App container only |
| Full bundled (laptop) | `docker compose --profile bundled up` | Everything |
| Local AI only | `docker compose --profile local-ai up` | App + Ollama + SearXNG |
| With caching | `docker compose --profile cache up` | App + Redis |

---

## Updated Environment Variables

Add to `.env.example`:

```env
# === Local AI (Phase 4) ===
OLLAMA_HOST=http://ollama:11434   # Ollama API endpoint
# MODEL_PROVIDER=ollama           # Uncomment to use local models
# MODEL_NAME=llama3.1:8b          # Local model name

# === Search Provider (Phase 4) ===
SEARCH_PROVIDER=brave              # brave | searxng
SEARXNG_HOST=http://searxng:8080   # SearXNG endpoint (when using searxng)

# === Caching (Phase 4 — only enable when a bottleneck is identified) ===
CACHE_ENABLED=false
REDIS_URL=redis://redis:6379/0
```

---

## Acceptance Criteria (Phase 4 Complete)

All of these must be true (in addition to all Phase 1–3 criteria still passing):

1. Ollama Docker service starts with `--profile bundled` or `--profile local-ai`
2. Setting `MODEL_PROVIDER=ollama` and `MODEL_NAME=llama3.1:8b` (or similar) uses Ollama as the model provider with zero code changes
3. Pydantic AI agents work identically with Ollama as they do with OpenAI/Groq
4. `scripts/pull_model.py` successfully downloads a model into Ollama
5. GPU passthrough is configured in Docker Compose (with graceful CPU fallback)
6. SearXNG Docker service starts and returns search results via JSON API
7. Setting `SEARCH_PROVIDER=searxng` routes agent web search to SearXNG instead of Brave
8. Agents produce identical search behavior with either search provider
9. Redis Docker service starts with `--profile cache` and is accessible
10. If a caching bottleneck was identified: cache addresses it with measurable improvement. If no bottleneck was found: Redis config exists but `CACHE_ENABLED=false` by default
11. All three services (Ollama, SearXNG, Redis) are optional — the kit works without them
12. `docs/local-ai-guide.md` covers running the full stack locally with zero external dependencies
13. `docs/gpu-sharing.md` covers running Ollama as shared infrastructure on a multi-project server
14. All existing Phase 1–3 tests still pass
15. New tests cover: Ollama provider switching, SearXNG search, cache operations

---

## What Is NOT in Phase 4

These remain deferred:

- **vLLM** — High-throughput alternative to Ollama. Can be added alongside Ollama later if concurrent request throughput becomes a concern. Not needed for the initial local AI story.
- **Evaluation pipelines** (Ragas) → Phase 5
- **MCP server exposure** (FastMCP) → Phase 5
- **Frontend / UI** → Phase 6
- **Reverse proxy / HTTPS** (Caddy) → Phase 6

---

*This document is the complete specification for Phase 4 of AgentForge. It contains everything needed to add local AI and caching without referencing external documents.*
