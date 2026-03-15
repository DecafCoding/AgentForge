# Phase 3 — Memory & Web Intelligence → v0.3

*AgentForge Starter Kit*

---

## Purpose of This Document

This document contains everything an AI or developer needs to build Phase 3 of AgentForge. It is self-contained. Phase 3 adds long-term agent memory (Mem0), web scraping (Crawl4AI), and web search (Brave Search) — giving agents the ability to remember across sessions and access the open web.

---

## Prerequisites (Phases 1–2 Complete)

Phase 3 assumes the following are already built and working:

**From Phase 1:**
- Project structure with `uv`, `ruff`, Docker Compose (bundled + shared profiles)
- Postgres 15 + pgvector with Alembic migrations and asyncpg driver
- Pydantic AI agent with tool registration and structured output (Pattern 1)
- FastAPI API layer with lifespan hook and APScheduler
- Langfuse observability wired into all agent calls
- Collector/reasoning separation enforced by module structure
- OpenAI + Groq provider switching via env vars
- Reference YouTube monitor agent
- Pytest skeleton and GitHub Actions CI

**From Phase 2:**
- LangGraph multi-agent orchestration (Pattern 2)
- Graph state as Pydantic models flowing between nodes
- Cross-agent Langfuse traces with per-agent child spans
- Reference multi-agent workflow (research/analysis/synthesis)
- Pattern Decision Guide documentation

---

## What Phase 3 Delivers

Three significant capability additions:

1. **Long-term memory (Mem0)** — Agents remember information across sessions. They can reference previous conversations, learn user preferences, and build context over time.
2. **Web scraping (Crawl4AI)** — Collectors can gather structured data from any web page, not just APIs.
3. **Web search (Brave Search)** — Agents can search the web in real-time and incorporate results into responses.

These are not just new tools — memory in particular fundamentally changes how agents are designed.

---

## Technology Additions

| Layer | Tool | Role |
|-------|------|------|
| Agent Development | `mem0ai` | Long-term agent memory with Postgres backend |
| Agent Development | `crawl4ai` | Web scraping and structured data extraction |
| Agent Development | Brave Search API | Web search for agents needing real-time web results |
| Agent Development | `mistralai` (optional) | Mistral provider — strong quality/price ratio |

Add to `pyproject.toml`:
```toml
[project]
dependencies = [
    # ... existing Phase 1 + 2 deps ...
    "mem0ai",
    "crawl4ai",
    "httpx",  # already present, used for Brave Search API calls
]
```

---

## Project Structure Changes

```
agentforge/
├── src/
│   ├── memory/                     # NEW — Long-term memory layer
│   │   ├── __init__.py
│   │   ├── client.py               # Mem0 client setup, Postgres backend config
│   │   ├── store.py                # Memory store interface and implementation
│   │   └── helpers.py              # Memory retrieval and injection helpers
│   │
│   ├── collector/
│   │   ├── base.py                 # EXISTING — Base collector pattern
│   │   ├── youtube.py              # EXISTING — YouTube collector
│   │   └── web_scraper.py          # NEW — Crawl4AI-based web scraping collector
│   │
│   ├── agent/
│   │   ├── agent.py                # MODIFIED — Memory-aware agent option
│   │   ├── tools.py                # MODIFIED — Add web search tool
│   │   └── memory_agent.py         # NEW — Reference memory-aware agent
│   │
│   ├── search/                     # NEW — Web search integration
│   │   ├── __init__.py
│   │   └── brave.py                # Brave Search API client
│   │
│   ├── db/
│   │   └── migrations/versions/    # NEW migration for Mem0 schema
│
├── docs/
│   ├── pattern-decision-guide.md   # EXISTING
│   └── memory-aware-agents.md      # NEW — How agent design changes with memory
│
└── tests/
    ├── test_memory.py              # NEW — Memory store tests
    ├── test_web_scraper.py         # NEW — Crawl4AI collector tests
    └── test_web_search.py          # NEW — Brave Search integration tests
```

---

## Product Backlog Items (PBIs)

### PBI 3.1 — Mem0 Integration

**Description:** Mem0 with Postgres backend, isolated schema (no interference with existing tables), cross-session context storage and retrieval.

**Done when:** Agent references information from previous conversations. Mem0 schema doesn't conflict with app schema.

**Implementation details:**

**Schema isolation strategy:**

Mem0 must use a **separate Postgres schema** (not a separate database) to avoid conflicts with the existing application tables. This keeps everything in one Postgres instance while preventing table name collisions.

```sql
-- Migration: create mem0 schema
CREATE SCHEMA IF NOT EXISTS mem0;
```

Configure Mem0 to use this schema in its Postgres connection settings.

**`src/memory/client.py`** — Mem0 setup:
```python
from mem0 import Memory

def create_memory_client() -> Memory:
    """Initialize Mem0 with Postgres backend using isolated schema."""
    config = {
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "dbname": os.getenv("POSTGRES_DB", "agentforge"),
                "user": os.getenv("POSTGRES_USER", "postgres"),
                "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
                "host": os.getenv("POSTGRES_HOST", "supabase-db"),
                "port": int(os.getenv("POSTGRES_PORT", "5432")),
                "collection_name": "agent_memories",
            }
        },
        "llm": {
            "provider": os.getenv("MODEL_PROVIDER", "openai"),
            "config": {
                "model": os.getenv("MEMORY_MODEL", "gpt-4o-mini"),
                "api_key": os.getenv("OPENAI_API_KEY"),
            }
        }
    }
    return Memory.from_config(config)
```

**`src/memory/store.py`** — Memory store interface:
```python
from abc import ABC, abstractmethod
from typing import Optional

class BaseMemoryStore(ABC):
    """Interface for memory storage. Implementations can use Mem0 or other backends."""

    @abstractmethod
    async def add(self, content: str, user_id: str, metadata: Optional[dict] = None) -> str:
        """Store a memory. Returns memory ID."""
        ...

    @abstractmethod
    async def search(self, query: str, user_id: str, limit: int = 5) -> list[dict]:
        """Search memories relevant to query for a specific user."""
        ...

    @abstractmethod
    async def get_all(self, user_id: str) -> list[dict]:
        """Get all memories for a user."""
        ...

class Mem0MemoryStore(BaseMemoryStore):
    """Mem0-backed memory store implementation."""

    def __init__(self, client: Memory):
        self.client = client

    async def add(self, content: str, user_id: str, metadata: Optional[dict] = None) -> str:
        result = self.client.add(content, user_id=user_id, metadata=metadata or {})
        return result["id"]

    async def search(self, query: str, user_id: str, limit: int = 5) -> list[dict]:
        results = self.client.search(query, user_id=user_id, limit=limit)
        return results

    async def get_all(self, user_id: str) -> list[dict]:
        return self.client.get_all(user_id=user_id)
```

**`src/memory/helpers.py`** — Memory injection helpers:
```python
async def get_relevant_context(memory_store: BaseMemoryStore, query: str, user_id: str) -> str:
    """Retrieve relevant memories and format as context string for agent prompt."""
    memories = await memory_store.search(query, user_id=user_id, limit=5)
    if not memories:
        return ""

    context_parts = ["Relevant context from previous conversations:"]
    for mem in memories:
        context_parts.append(f"- {mem['memory']}")

    return "\n".join(context_parts)

async def store_interaction(memory_store: BaseMemoryStore, question: str, answer: str, user_id: str):
    """Store a question/answer interaction as a memory."""
    content = f"User asked: {question}\nAssistant answered: {answer}"
    await memory_store.add(content, user_id=user_id, metadata={"type": "interaction"})
```

**Mem0 lifecycle management:**
- Initialize Mem0 client in FastAPI lifespan hook (alongside db pool and scheduler)
- Store in `app.state.memory` for access in routes
- Mem0 client should be gracefully shut down on app shutdown

### PBI 3.2 — Crawl4AI Integration

**Description:** Web scraping collector pattern, structured data extraction from web pages.

**Done when:** Collector fetches and parses a web page into structured data stored in Postgres.

**Implementation details:**

**`src/collector/web_scraper.py`:**
```python
from crawl4ai import AsyncWebCrawler
from src.collector.base import BaseCollector
from pydantic import BaseModel
from asyncpg import Pool

class ScrapedPage(BaseModel):
    url: str
    title: str
    content: str
    extracted_data: dict
    scraped_at: datetime

class WebScrapingCollector(BaseCollector):
    """Collector that scrapes web pages using Crawl4AI.

    NO LLM imports. Crawl4AI's extraction is deterministic/rule-based.
    """

    def __init__(self, pool: Pool, urls: list[str]):
        super().__init__(pool)
        self.urls = urls

    async def collect(self) -> int:
        """Scrape configured URLs and store results."""
        count = 0
        async with AsyncWebCrawler() as crawler:
            for url in self.urls:
                result = await crawler.arun(url=url)
                if result.success:
                    await self._store_result(url, result)
                    count += 1
        return count

    async def _store_result(self, url: str, result):
        """Store scraped content in Postgres."""
        await self.pool.execute(
            """INSERT INTO scraped_pages (url, title, content, scraped_at)
               VALUES ($1, $2, $3, NOW())
               ON CONFLICT (url) DO UPDATE SET
               content = EXCLUDED.content, scraped_at = NOW()""",
            url, result.metadata.get("title", ""), result.markdown
        )
```

**Crawl4AI considerations:**
- Crawl4AI supports both simple and LLM-based extraction strategies
- For the collector module, use **only the rule-based/CSS extraction** — no LLM imports in collectors
- If LLM-based extraction is needed, it belongs in the agent module, not the collector
- Crawl4AI can run in headless browser mode for JavaScript-rendered pages
- Rate limiting and politeness (robots.txt respect) should be configured

**Database migration for scraped pages:**
```sql
CREATE TABLE scraped_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url VARCHAR NOT NULL UNIQUE,
    title VARCHAR,
    content TEXT,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),
    scraped_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scraped_pages_url ON scraped_pages(url);
```

**Scheduler registration:**
Add web scraping jobs to APScheduler alongside existing YouTube collection jobs. URLs to scrape should be configurable via environment variables or a config file.

### PBI 3.3 — Web Search API (Brave Search)

**Description:** Brave Search integration for agents needing real-time web results.

**Done when:** Agent can search the web and incorporate results into responses.

**Implementation details:**

**`src/search/brave.py`:**
```python
import httpx
import os
from pydantic import BaseModel

BRAVE_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

class SearchResult(BaseModel):
    title: str
    url: str
    description: str

async def search_web(query: str, count: int = 5) -> list[SearchResult]:
    """Search the web using Brave Search API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            BRAVE_SEARCH_URL,
            headers={"X-Subscription-Token": BRAVE_API_KEY},
            params={"q": query, "count": count},
        )
        response.raise_for_status()
        data = response.json()

    results = []
    for item in data.get("web", {}).get("results", []):
        results.append(SearchResult(
            title=item["title"],
            url=item["url"],
            description=item.get("description", ""),
        ))
    return results
```

**Agent tool registration:**

Add `search_web` as a tool available to agents:

```python
# In src/agent/tools.py
from src.search.brave import search_web as brave_search

async def web_search(query: str) -> list[dict]:
    """Search the web for real-time information."""
    results = await brave_search(query, count=5)
    return [r.model_dump() for r in results]
```

**Note:** The Brave Search API call is made from the **agent module** (not the collector) because it is triggered by human interaction, not on a schedule. This is consistent with the collector/reasoning boundary — the agent uses web search as a tool during reasoning.

**Environment variables:**
```env
BRAVE_SEARCH_API_KEY=BSA-...    # Brave Search API key
```

### PBI 3.4 — Memory-Aware Agent Patterns

**Description:** Documentation on how agent design changes with long-term memory, guidelines for predictability.

**Done when:** Developer understands what changes when memory is added and how to keep agents predictable.

**Implementation details:**

**`src/agent/memory_agent.py`** — Reference memory-aware agent:
```python
from pydantic_ai import Agent
from src.config import get_model_string
from src.memory.helpers import get_relevant_context, store_interaction

async def run_memory_agent(question: str, user_id: str, pool, memory_store):
    """Run an agent with memory context injection."""
    # 1. Retrieve relevant memories
    memory_context = await get_relevant_context(memory_store, question, user_id)

    # 2. Build dynamic system prompt with memory
    system_prompt = f"""You are a YouTube content research assistant with memory.
    You remember previous conversations and can reference them.

    {memory_context}

    Use your tools to find relevant information. Always cite sources."""

    # 3. Create agent with memory-augmented prompt
    agent = Agent(
        model=get_model_string(),
        system_prompt=system_prompt,
        tools=[query_videos, search_videos, web_search],
        result_type=AgentResponse,
    )

    # 4. Run agent
    result = await agent.run(question, deps=pool)

    # 5. Store this interaction as a memory
    await store_interaction(memory_store, question, result.data.answer, user_id)

    return result
```

**`docs/memory-aware-agents.md`** — Documentation covering:

1. **What changes with memory:**
   - Agents now have context that persists across sessions
   - The system prompt becomes dynamic (injected with relevant memories)
   - Agent behavior is no longer stateless — it depends on history
   - Token usage increases (memory context added to every prompt)

2. **Predictability guidelines:**
   - Always make memory injection explicit — never silently modify behavior
   - Limit the number of memories injected per request (5-10 max)
   - Log which memories were used in each response (via Langfuse metadata)
   - Provide a way to clear/reset memories for debugging
   - Memory should supplement, not override, the core system prompt

3. **Memory patterns:**
   - **User preference learning:** Store stated preferences, retrieve for future interactions
   - **Cross-session context:** Remember what was discussed in previous sessions
   - **Behavioral pattern recognition:** Track recurring questions or topics
   - **Anti-pattern:** Using memory as a replacement for proper database queries

4. **Testing memory-aware agents:**
   - Test with empty memory (new user experience)
   - Test with populated memory (returning user)
   - Test memory relevance (are the right memories retrieved?)
   - Test memory accumulation (does performance degrade over time?)

---

## Updated Environment Variables

Add these to `.env.example`:

```env
# === Memory (Phase 3) ===
MEMORY_MODEL=gpt-4o-mini         # Model used by Mem0 for memory operations
MEMORY_ENABLED=true               # Enable/disable memory (for testing without memory)

# === Web Search (Phase 3) ===
BRAVE_SEARCH_API_KEY=BSA-...     # Brave Search API key
BRAVE_SEARCH_ENABLED=true        # Enable/disable web search tool

# === Web Scraping (Phase 3) ===
SCRAPE_URLS=                     # Comma-separated URLs to scrape on schedule
SCRAPE_INTERVAL_MINUTES=360      # How often to run web scraping collector

# === Additional Provider (Phase 3) ===
MISTRAL_API_KEY=                 # Optional — Mistral provider
```

---

## Acceptance Criteria (Phase 3 Complete)

All of these must be true (in addition to all Phase 1 + 2 criteria still passing):

1. Mem0 is initialized with a Postgres backend using an isolated schema (`mem0`)
2. Mem0's tables do not conflict with the existing application schema
3. An agent can store memories from a conversation
4. An agent in a subsequent session can retrieve and reference memories from a previous session
5. Memory injection into the agent prompt is explicit and logged in Langfuse
6. Crawl4AI scrapes a web page and stores structured content in Postgres
7. The web scraping collector (`src/collector/web_scraper.py`) has zero LLM imports
8. Web scraping runs on schedule via APScheduler
9. Brave Search returns web results that an agent can use as a tool
10. The memory-aware agent reference implementation works end-to-end
11. `docs/memory-aware-agents.md` covers design changes, predictability guidelines, and testing patterns
12. All existing Phase 1 + 2 tests still pass
13. New tests cover: memory storage/retrieval, web scraping, web search, memory-aware agent behavior
14. Memory can be disabled via env var (`MEMORY_ENABLED=false`) for testing without memory

---

## What Is NOT in Phase 3

These remain deferred:

- **Local model serving** (Ollama, vLLM) → Phase 4
- **Local web search** (SearXNG) → Phase 4
- **Caching** (Redis/Valkey) → Phase 4
- **Evaluation pipelines** (Ragas) → Phase 5
- **MCP server exposure** (FastMCP) → Phase 5
- **Frontend / UI** → Phase 6
- **Reverse proxy / HTTPS** (Caddy) → Phase 6
- **Crawl4AI LLM-based extraction** — Only rule-based extraction in collectors; LLM extraction belongs in agent module if needed

---

*This document is the complete specification for Phase 3 of AgentForge. It contains everything needed to add memory and web intelligence without referencing external documents.*
