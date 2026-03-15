# AgentForge — Product Requirements Document

*Last updated: March 2026*

---

## Executive Summary

AgentForge is an opinionated, open-source, code-first development stack for building AI agents in Python. It solves the fragmented tooling problem — where developers waste hours per week navigating 70+ tools across 7 categories — by shipping a curated, pre-integrated, tested foundation. Clone the repo, run one command, start writing agent logic.

AgentForge is not a framework with enforced constraints. It's a pre-wired stack with opinionated patterns and sensible defaults. Developers can follow the patterns or deviate — the value is that the boring plumbing is already done and the architectural decisions are already made.

The MVP (v0.1–v0.2) delivers two complete agent patterns: a single agent with tools (Pydantic AI) and multi-agent orchestration (LangGraph + Pydantic AI). Both are demonstrated through separate reference implementations, not toy examples.

---

## Mission Statement

Make building AI agents as fast as starting a React app — by shipping the tooling decisions, integration code, and architectural patterns that every agent developer would otherwise spend weeks assembling from scratch.

---

## Target Users

**Primary:** Python developers building AI agents who write code (not drag-and-drop). They know Python, have used at least one LLM API, and are frustrated by the time spent on tooling setup rather than agent logic.

**Secondary:** Solo developers and small teams running AI projects on personal servers or cloud VMs who want a coherent, self-hosted stack without vendor lock-in.

**Not the target:** No-code/low-code builders (served by n8n, Flowise, Open WebUI), enterprise teams needing managed platforms, or developers looking for a visual workflow builder.

---

## MVP Scope

### In Scope (v0.1 + v0.2)

- **Complete single-agent pattern** — Pydantic AI agent with tool registration, structured output, and model-agnostic provider support (OpenAI + Groq)
- **Complete multi-agent pattern** — LangGraph orchestrating Pydantic AI agents with conditional edges, parallel branches, and state management via Pydantic models
- **Collector/reasoning separation** — Enforced by module structure. Collectors have zero LLM imports. Agents have zero scheduler imports. They share the database and nothing else
- **Database layer** — Postgres 15 + pgvector with Alembic migrations and asyncpg driver
- **Observability** — Langfuse tracing on every agent call (prompt, response, tokens, cost, latency), including cross-agent traces for multi-agent workflows
- **API layer** — FastAPI with lifespan hook for APScheduler integration
- **Scheduling** — APScheduler in-process for collector tasks
- **Dual deployment support** — Docker profiles + env vars for both developer laptop (bundled) and dedicated server (shared infrastructure)
- **Testing skeleton** — Pytest patterns for agents, collectors, and API routes
- **CI/CD** — GitHub Actions for lint, test, build
- **Documentation** — README quickstart, architecture overview, pattern decision guide

### Explicitly Out of Scope

- **Frontend** — No UI ships in the MVP. Deferred to Phase 6
- **Authentication/authorization** — No auth layer. The kit assumes single-user, private deployment
- **Full Supabase stack** — No GoTrue, Kong, Storage, or Realtime. Raw Postgres + pgvector only
- **Local model serving** — No Ollama/vLLM in MVP. Cloud providers (OpenAI, Groq) are sufficient
- **Long-term memory** — No Mem0. Deferred to Phase 3 for validation through ArtimesOne
- **Web scraping** — No Crawl4AI. Deferred until a collector actually needs it
- **Evaluation pipelines** — No Ragas. Meaningless without a dataset
- **MCP server exposure** — No FastMCP. Deferred to Phase 5
- **Caching** — No Redis/Valkey. Premature until a bottleneck is measured
- **Revenue features** — No premium templates, hosted version, or paid add-ons

---

## Development Phases

### Phase 1 — Core Platform (Single Agent Pattern) → v0.1

**Goal:** The minimum viable kit. Clone, run one command, build a single agent end-to-end.

| PBI | Description | Done When |
|-----|-------------|-----------|
| 1.1 | **Project Scaffolding** — `pyproject.toml` (uv-managed), ruff config, `.env.example`, project directory structure, `README.md` skeleton | Project structure matches architecture spec; `uv sync` resolves all deps |
| 1.2 | **Docker Compose Setup** — App container (python:3.12-slim), Postgres 15 + pgvector (bundled profile), Langfuse server + Langfuse DB (bundled profile), env var overrides for shared infra | `docker compose --profile bundled up` starts all services; `docker compose up` starts only the app |
| 1.3 | **Database Layer** — asyncpg connection pool, Alembic migration setup, initial schema (pgvector extension enabled), typed async query functions | `alembic upgrade head` creates all tables; queries return typed Pydantic models |
| 1.4 | **Collector Module** — APScheduler setup via FastAPI lifespan hook, base collector pattern, minimal reference collector (fetches and stores data on schedule) | Collector runs on schedule, stores data in Postgres, has zero LLM imports |
| 1.5 | **Agent Module** — Pydantic AI agent with tool registration, structured output, database query tools | Agent answers questions using stored data; tools are registered and callable |
| 1.6 | **Observability Integration** — Langfuse client setup, trace decorators, context helpers wired into every agent call | Full reasoning chain visible in Langfuse (prompt, response, tokens, cost, latency) |
| 1.7 | **API Layer** — FastAPI app factory, middleware, routes for agent interaction (`POST /api/ask`), request/response schemas | API accepts questions and returns agent-generated, source-cited answers |
| 1.8 | **Model Provider Configuration** — OpenAI (primary) + Groq (secondary), env-based provider switching, `.env.example` with all provider options | Switching providers requires changing two env vars, zero code changes |
| 1.9 | **Testing & CI/CD** — Pytest skeleton with patterns for collector, agent, and API tests; GitHub Actions workflow for lint (ruff), test, build | Tests pass in CI; lint is enforced; new PRs run the full pipeline |
| 1.10 | **Scripts & Seed Data** — `seed.py` for initial data population, `collect.py` for manual collection trigger | Developer can populate data and trigger collection without the scheduler |
| 1.11 | **Documentation** — README quickstart (clone to working agent in <15 min), architecture overview, `.env.example` with comments, shared infrastructure setup guide | A new developer can follow the README and have a working agent without asking questions |

### Phase 2 — Multi-Agent Orchestration → v0.2

**Goal:** Add LangGraph as Pattern 2. Developers now have both architectural patterns with clear guidance on when to use each.

| PBI | Description | Done When |
|-----|-------------|-----------|
| 2.1 | **LangGraph Integration** — LangGraph dependency, graph setup pattern, Pydantic AI agents composing inside graph nodes | A multi-agent workflow runs end-to-end; each node is a standard Pydantic AI agent |
| 2.2 | **State Management** — Graph state defined as Pydantic models, state passing between nodes, serialization | State flows correctly between agents; Pydantic models serialize/deserialize cleanly |
| 2.3 | **Cross-Agent Observability** — Langfuse traces that span the full multi-agent workflow with per-agent detail as child spans | Single Langfuse trace shows entire workflow with nested agent-level detail |
| 2.4 | **Pattern 2 Reference Example** — Working multi-agent example demonstrating conditional edges, parallel execution, and state-dependent routing | Example is clear enough that a developer can adapt it to their own multi-agent problem |
| 2.5 | **Pattern Decision Guide** — Documentation explaining Pattern 1 vs Pattern 2 vs plain Python orchestration with concrete decision criteria and examples | Developer can read the guide and know which pattern to use for their use case |

### Phase 3 — Memory & Web Intelligence → v0.3

**Goal:** Agents remember across sessions and can scrape the web.

| PBI | Description | Done When |
|-----|-------------|-----------|
| 3.1 | **Mem0 Integration** — Mem0 with Postgres backend, isolated schema (no interference with existing tables), cross-session context storage and retrieval | Agent references info from previous conversations; Mem0 schema doesn't conflict with app schema |
| 3.2 | **Crawl4AI Integration** — Web scraping collector pattern, structured data extraction from web pages | Collector fetches and parses a web page into structured data stored in Postgres |
| 3.3 | **Web Search API** — Brave Search integration for agents needing real-time web results | Agent can search the web and incorporate results into responses |
| 3.4 | **Memory-Aware Agent Patterns** — Documentation on how agent design changes with long-term memory, guidelines for predictability | Developer understands what changes when memory is added and how to keep agents predictable |

### Phase 4 — Local AI & Caching → v0.4

**Goal:** Fully local, privacy-first workflows. No data leaves the machine.

| PBI | Description | Done When |
|-----|-------------|-----------|
| 4.1 | **Ollama Integration** — Docker service, Pydantic AI provider config, GPU sharing documentation | Local model is a drop-in replacement for cloud provider via env var change |
| 4.2 | **SearXNG Setup** — Self-hosted search engine, agent search tool integration | Agents search the web without external API calls |
| 4.3 | **Redis/Valkey Caching** — Caching layer for a specific measured bottleneck | Cache addresses a documented bottleneck with measurable improvement |

### Phase 5 — Evaluation & Quality

**Goal:** Measure and improve agent quality. Expose capabilities to the MCP ecosystem.

| PBI | Description | Done When |
|-----|-------------|-----------|
| 5.1 | **Ragas Evaluation Pipelines** — Evaluation setup, metrics against real agent output | Pipeline produces actionable metrics from real interactions |
| 5.2 | **FastMCP Server Exposure** — Agent capabilities exposed as MCP tools | An agent tool is callable from an MCP client |
| 5.3 | **Testing Patterns Documentation** — Comprehensive guide for unit testing agents, integration testing multi-agent workflows, evaluation as practice | Developer has clear patterns for testing every layer of the stack |

### Phase 6 — Application Layer & Deployment

**Goal:** Ship-ready applications. Frontend template, HTTPS, production config.

| PBI | Description | Done When |
|-----|-------------|-----------|
| 6.1 | **Frontend Template** — React + Vite + shadcn/ui, connected to FastAPI backend | Template renders agent responses from the API |
| 6.2 | **Reverse Proxy & HTTPS** — Caddy configuration for production routing | HTTPS terminates at Caddy; services are routed correctly |
| 6.3 | **Production Docker Configuration** — Resource limits, restart policies, production env template | Production compose file runs reliably with appropriate constraints |

---

## Core Architecture & Tech Stack

### Layered Architecture

```
┌─────────────────────────────────────────┐
│  Application Layer                       │
│  FastAPI  ·  APScheduler                │
├─────────────────────────────────────────┤
│  Agent Layer                             │
│  Pydantic AI  ·  LangGraph (Phase 2)    │
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

### Technology Stack (MVP)

| Layer | Tool | Role |
|-------|------|------|
| Language | Python 3.12 | Runtime |
| Package Manager | uv | Dependency management, venv, lockfile |
| Agent Framework | Pydantic AI | Tool registration, structured output, provider abstraction |
| Multi-Agent (Phase 2) | LangGraph | Graph-based orchestration of Pydantic AI agents |
| Observability | Langfuse | Traces, cost tracking, latency |
| API | FastAPI + Uvicorn | ASGI backend |
| Scheduling | APScheduler | In-process scheduled tasks |
| Database | Postgres 15 + pgvector | Storage + vector similarity search |
| Migrations | Alembic | Schema versioning |
| DB Driver | asyncpg | Async Postgres |
| Validation | Pydantic | Data models throughout |
| HTTP Client | httpx | Async HTTP for collectors |
| Environment | python-dotenv | `.env` loading |
| Testing | Pytest + pytest-asyncio | Test framework |
| Linting | Ruff | Replaces flake8 + black + isort |
| Orchestration | Docker Compose | Service management |

### LLM Provider Strategy

| Provider | Phase | Notes |
|----------|-------|-------|
| OpenAI | Phase 1 | Primary. Native Pydantic AI provider |
| Groq | Phase 1 | Secondary. OpenAI-compatible API, 300-500 tok/s |
| Mistral | Phase 3 | Strong quality/price ratio |
| Ollama | Phase 4 | Local inference, GPU sharing |
| vLLM | Phase 4 | High-throughput local alternative |

Provider switching is two env vars (`MODEL_PROVIDER`, `MODEL_NAME`). Zero code changes.

---

## Key Features / Agent Tools

### What Ships in the Kit

- **Agent with tools pattern** — Pydantic AI agent that receives input, selects tools, returns structured output
- **Database query tools** — Typed async functions for querying collected data
- **Collector scheduling** — APScheduler runs collectors on configurable intervals
- **Trace-everything observability** — Every agent call traced with full prompt/response/cost/latency
- **Docker profiles for dual deployment** — `--profile bundled` for laptop; env var overrides for shared server infra
- **Multi-agent workflows (Phase 2)** — LangGraph graphs with conditional edges, parallel branches, Pydantic model state

### What Ships as a Separate Reference Example

- **YouTube monitor agent** — Collects video metadata on schedule, answers questions about it via the agent. Demonstrates the full collector/reasoning separation pattern end-to-end

---

## Core Patterns

### 1. Collector/Reasoning Separation

The most important architectural boundary. Enforced by module structure, not convention.

- **Collector module** — imports: httpx, asyncpg, pydantic. Runs on schedule. Fetches external data. Stores to Postgres. Zero token spend
- **Agent module** — imports: pydantic-ai, langfuse. Runs on human interaction only. Reads from Postgres. Invokes LLM. Token spend proportional to human interactions
- **The boundary test:** If `src/collector/` imports from `pydantic_ai` or `langfuse`, the boundary is violated. If `src/agent/` imports from `apscheduler` or makes direct HTTP calls, the boundary is violated

### 2. Interface-Driven Extensibility

The core defines contracts. Skills and collectors implement those contracts. Adding a capability never changes the core.

**Critical rule:** No interface is designed in the abstract. Build one real implementation first, then extract the interface from what it actually needed.

### 3. Model-Agnostic Design

No collector or deterministic component depends on a specific LLM provider. The reasoning layer is isolated behind Pydantic AI's provider abstraction. Switching models is a config change.

### 4. Shared Infrastructure vs. Bundled Services

Two deployment modes from a single Docker Compose file:

- **Developer laptop:** `docker compose --profile bundled up` — all services start (Postgres, Langfuse, app)
- **Dedicated server:** Set `DATABASE_URL`, `LANGFUSE_HOST`, etc. in `.env` → `docker compose up` — only the app starts, connects to shared infra

**Boundary rule:** A service belongs in shared infrastructure if it outlives any single project. Postgres is shared (one instance, one database per project). The app container is project-owned.

### 5. Agent Pattern Selection

| Pattern | Tool | Use When |
|---------|------|----------|
| Single agent with tools | Pydantic AI | One agent, multiple tools, implicit orchestration via tool-calling loop |
| Multi-agent orchestration | LangGraph + Pydantic AI | Multiple agents, conditional routing, parallel branches, stateful coordination |
| Plain Python | `await agent.run()` | Fixed linear sequence, no conditional branching |

**The test:** If "what happens next?" always has the same answer regardless of previous output → plain Python. If it depends on previous output → LangGraph.

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Kit name | **AgentForge** |
| Positioning | Pre-wired stack with opinionated patterns and sensible defaults. Not an enforced framework |
| Reference implementation | Separate example repo. Kit ships clean with minimal agent; YouTube monitor is a standalone reference project |
| Postgres topology | Shared instance on dedicated server (one Postgres, separate databases per project) |
| Full Supabase stack | Excluded. Raw Postgres + pgvector only. GoTrue/Storage/Realtime not needed for single-user deployment |
| Frontend | Deferred to Phase 6. Kit is useful without UI |
| Anthropic provider | Excluded from Phase 1 due to pricing. Can be added at any phase |

---

*This PRD is the canonical product reference for AgentForge. Architecture details live in `ARCHITECTURE.md`. Phase execution details live in `DevPlan.md`. This document governs what ships and why.*
