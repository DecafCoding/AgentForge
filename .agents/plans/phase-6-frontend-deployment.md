# Feature: Phase 6 — Application Layer & Deployment

> **This is the parent plan.** Phase 6 has been broken into three PBIs for incremental delivery:
>
> 1. **[PBI 6.1 — Frontend Template](phase-6-pbi-6.1-frontend-template.md)** (23 tasks) — Backend prep + React chat interface
> 2. **[PBI 6.2 — Reverse Proxy & Production Docker](phase-6-pbi-6.2-proxy-production-docker.md)** (6 tasks) — Dockerfiles, Caddy, production compose
> 3. **[PBI 6.3 — CI/CD & Documentation](phase-6-pbi-6.3-ci-docs.md)** (3 tasks) — CI pipeline, deployment guide, customization guide
>
> Execute PBIs in order. Each depends on the previous one being complete.

The following plan contains the full consolidated details. Refer to the individual PBI files for execution.

## Feature Description

Phase 6 takes AgentForge from a developer-only API to a deployable application platform. It adds three capabilities:

1. **Frontend Template** — React + Vite + TypeScript + shadcn/ui + TanStack React Query chat interface connected to the FastAPI backend. A working starting point for custom agent UIs.
2. **Reverse Proxy & HTTPS** — Caddy configuration for production routing with automatic Let's Encrypt HTTPS certificate management.
3. **Production Docker Configuration** — Resource limits, restart policies, health checks, log rotation, and a production environment template.

## User Story

As an AI agent developer
I want a pre-built frontend template and production deployment configuration
So that I can go from agent logic to a deployed, HTTPS-enabled application without assembling frontend tooling or production infrastructure from scratch.

## Problem Statement

AgentForge currently only exposes agents through API endpoints (`POST /api/ask`, `POST /api/research`, `POST /api/ask/memory`). Developers must build their own frontend and figure out production deployment (HTTPS, resource limits, health checks) independently. This is exactly the kind of boring plumbing that AgentForge aims to eliminate.

## Solution Statement

Ship a minimal but functional React chat interface as a template, wire it to the existing API, add Caddy as a reverse proxy for automatic HTTPS, and provide a production Docker Compose override file with resource limits, health checks, and log management. The frontend is intentionally minimal — a starting point, not a finished product.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: High (spans frontend + infrastructure + Docker + docs)
**Primary Systems Affected**: `frontend/` (new), `src/api/main.py`, `src/api/routes.py`, `docker-compose.yml`, new `docker-compose.prod.yml`
**Dependencies**: React 18, Vite, TypeScript, shadcn/ui, TanStack React Query, Tailwind CSS v4, Caddy 2, nginx (frontend container)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `src/api/routes.py` (lines 1-146) — Why: All existing API endpoints that the frontend must call. Contains `/health`, `POST /api/ask`, `POST /api/research`, `POST /api/ask/memory`.
- `src/api/schemas.py` (lines 1-74) — Why: Pydantic request/response schemas that TypeScript types must mirror exactly. `AskRequest`, `AskResponse`, `ResearchRequest`, `WorkflowResponse`, `MemoryAskRequest`, `MemoryAskResponse`, `HealthResponse`.
- `src/agent/models.py` (lines 1-35) — Why: The `Source` model used across all API responses. TypeScript `Source` interface must match this.
- `src/api/main.py` (lines 84-108) — Why: `create_app()` function where CORS middleware must be added. Understand current middleware setup.
- `docker-compose.yml` (lines 1-151) — Why: Existing service definitions, profiles, and volume patterns. New services (frontend, caddy) must follow the same conventions.
- `Dockerfile` (lines 1-48) — Why: Existing multi-stage build pattern for the backend. Frontend Dockerfile should follow similar conventions.
- `.env.example` (lines 1-118) — Why: Current env var documentation pattern. New Phase 6 vars must follow the same format.
- `src/config.py` (lines 1-151) — Why: Configuration loading pattern. New `CORS_ORIGINS` config must follow the same pattern.
- `.github/workflows/ci.yml` (lines 1-94) — Why: CI pipeline that must be updated to lint/build the frontend.
- `tests/test_api.py` (lines 1-127) — Why: Existing API test patterns. Health check test already exists at line 16.
- `tests/conftest.py` (lines 1-90) — Why: Test fixture patterns for mocking app state.

### New Files to Create

**Frontend application (`frontend/`):**
- `frontend/package.json` — NPM project manifest
- `frontend/tsconfig.json` — TypeScript configuration with path aliases
- `frontend/tsconfig.app.json` — App-specific TS config
- `frontend/tsconfig.node.json` — Node-specific TS config (for vite.config.ts)
- `frontend/vite.config.ts` — Vite config with React plugin, Tailwind CSS v4 plugin, path aliases, dev proxy
- `frontend/index.html` — HTML entry point
- `frontend/postcss.config.js` — NOT NEEDED (Tailwind v4 uses Vite plugin, no PostCSS)
- `frontend/tailwind.config.js` — NOT NEEDED (Tailwind v4 uses CSS-based config)
- `frontend/src/main.tsx` — App entry point with QueryClientProvider
- `frontend/src/App.tsx` — Root component with layout
- `frontend/src/index.css` — Global styles with `@import "tailwindcss"` and shadcn/ui CSS variables
- `frontend/src/lib/utils.ts` — shadcn/ui `cn()` utility (auto-generated by shadcn init)
- `frontend/src/lib/api.ts` — API client functions (askAgent, runResearch, askWithMemory)
- `frontend/src/types/api.ts` — TypeScript interfaces matching FastAPI schemas
- `frontend/src/hooks/useAgent.ts` — React Query mutation hook for `/api/ask`
- `frontend/src/hooks/useWorkflow.ts` — React Query mutation hook for `/api/research`
- `frontend/src/components/ui/` — shadcn/ui components (button, input, card, badge, scroll-area, skeleton)
- `frontend/src/components/chat/ChatInterface.tsx` — Main chat UI
- `frontend/src/components/chat/MessageBubble.tsx` — Individual message display
- `frontend/src/components/chat/SourceCard.tsx` — Source citation display
- `frontend/src/components/chat/InputBar.tsx` — Message input with send button
- `frontend/src/components/layout/Header.tsx` — App header
- `frontend/src/components/layout/MainLayout.tsx` — Page layout wrapper
- `frontend/public/favicon.svg` — App favicon
- `frontend/Dockerfile` — Multi-stage build (node:20-alpine → nginx:alpine)
- `frontend/nginx.conf` — Nginx config for SPA serving + API proxy

**Infrastructure:**
- `docker-compose.prod.yml` — Production overrides (resource limits, health checks, logging)
- `config/caddy/Caddyfile` — Caddy reverse proxy configuration
- `.env.production.example` — Production environment template

**Documentation:**
- `docs/deployment-guide.md` — Server setup → deployed application walkthrough
- `docs/frontend-customization.md` — How to modify the frontend template

**Backend modifications:**
- `src/api/main.py` — ADD CORS middleware
- `src/api/routes.py` — UPDATE health endpoint to check database status
- `src/config.py` — ADD `CORS_ORIGINS` and `DOMAIN` config vars
- `.env.example` — ADD Phase 6 env vars
- `docker-compose.yml` — ADD frontend and caddy services
- `.github/workflows/ci.yml` — ADD frontend lint/build job
- `.gitignore` — ADD `frontend/node_modules/`, `frontend/dist/`

### Relevant Documentation — YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [shadcn/ui Vite Installation](https://ui.shadcn.com/docs/installation/vite)
  - Specific section: Vite template initialization
  - Why: The `npx shadcn@latest init -t vite` command handles all config automatically
- [Tailwind CSS v4 Vite Plugin](https://tailwindcss.com/docs)
  - Specific section: Vite integration
  - Why: v4 uses `@tailwindcss/vite` plugin — NO PostCSS config, NO `tailwind.config.js` needed
- [TanStack React Query v5 Quick Start](https://tanstack.com/query/v5/docs/react/quick-start)
  - Specific section: QueryClientProvider setup
  - Why: Wrapping app with QueryClientProvider, using useMutation for POST requests
- [Caddy Reverse Proxy Quick Start](https://caddyserver.com/docs/quick-starts/reverse-proxy)
  - Specific section: Caddyfile syntax for reverse_proxy
  - Why: Routing `/api/*` to backend, everything else to frontend
- [Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https)
  - Specific section: How Caddy handles localhost vs real domains
  - Why: Understanding that localhost gets self-signed certs, real domains get Let's Encrypt
- [Vite Proxy Configuration](https://vite.dev/config/server-options#server-proxy)
  - Specific section: server.proxy
  - Why: Proxying `/api` to `http://localhost:8000` during development

### Patterns to Follow

**Naming Conventions:**
- Python: `snake_case` functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants
- TypeScript: `camelCase` functions/variables, `PascalCase` components/interfaces, `UPPER_SNAKE_CASE` constants
- Files: Python `snake_case.py`, React `PascalCase.tsx` for components, `camelCase.ts` for utilities

**Config Loading Pattern (from `src/config.py`):**
```python
CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
```

**API Route Pattern (from `src/api/routes.py`):**
```python
@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Return service health status."""
```

**Docker Compose Service Pattern (from `docker-compose.yml`):**
```yaml
services:
  service-name:
    image: ...
    profiles: ["bundled"]  # or no profile for always-on
    ports:
      - "host:container"
    volumes:
      - named-volume:/path
    environment:
      VAR: ${VAR:-default}
    depends_on:
      dependency:
        condition: service_healthy
        required: false
```

**Test Pattern (from `tests/test_api.py`):**
```python
async def test_health_returns_200(client):
    """GET /health returns 200 with status ok."""
    response = await client.get("/health")
    assert response.status_code == 200
```

**Env Example Pattern (from `.env.example`):**
```env
# -----------------------------------------------------------------------------
# Section Name (Phase N)
# Description of what these vars do.
# Additional usage notes.
# -----------------------------------------------------------------------------
VAR_NAME=default-value
```

---

## IMPLEMENTATION PLAN

### Phase 1: Backend Preparation

Add CORS middleware, enhance health endpoint, add new config vars. These backend changes must be in place before the frontend can connect.

**Tasks:**
- Add `CORS_ORIGINS` and `DOMAIN` to `src/config.py`
- Add CORS middleware to `src/api/main.py`
- Enhance `/health` endpoint to check database connectivity
- Update `.env.example` with Phase 6 vars
- Update `.gitignore` for frontend artifacts

### Phase 2: Frontend Application

Scaffold the React + Vite + TypeScript project, add shadcn/ui and TanStack React Query, build the chat interface.

**Tasks:**
- Initialize Vite React-TS project
- Configure shadcn/ui with Vite template
- Add TanStack React Query
- Create API client and TypeScript types
- Build chat interface components
- Configure Vite dev proxy

### Phase 3: Docker & Infrastructure

Add frontend Dockerfile, Caddy configuration, production Docker Compose overrides.

**Tasks:**
- Create frontend Dockerfile (multi-stage)
- Create frontend nginx.conf for SPA serving
- Create Caddyfile for reverse proxy routing
- Add frontend + caddy services to docker-compose.yml
- Create docker-compose.prod.yml with production overrides
- Create .env.production.example

### Phase 4: CI/CD & Documentation

Update CI pipeline, write deployment and customization guides.

**Tasks:**
- Add frontend lint/build job to CI
- Write deployment guide
- Write frontend customization guide

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: UPDATE `src/config.py` — Add Phase 6 configuration variables

- **IMPLEMENT**: Add `CORS_ORIGINS` and `DOMAIN` config constants after the MCP Server section (after line 105).
- **PATTERN**: Follow the existing section pattern with comment headers (see lines 95-105 for Phase 5 example).
- **IMPORTS**: No new imports needed — uses existing `os.getenv`.

```python
# ---------------------------------------------------------------------------
# Frontend & Deployment (Phase 6)
# ---------------------------------------------------------------------------
CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
DOMAIN: str = os.getenv("DOMAIN", "localhost")
```

- **VALIDATE**: `uv run python -c "from src.config import CORS_ORIGINS, DOMAIN; print(CORS_ORIGINS, DOMAIN)"`

---

### Task 2: UPDATE `src/api/main.py` — Add CORS middleware

- **IMPLEMENT**: Import `CORSMiddleware` from `fastapi.middleware.cors` and `CORS_ORIGINS` from `src.config`. Add CORS middleware in `create_app()` before `include_router()`.
- **PATTERN**: Follow FastAPI CORS middleware docs. Split `CORS_ORIGINS` on comma to support multiple origins.
- **IMPORTS**: `from fastapi.middleware.cors import CORSMiddleware` and `from src.config import CORS_ORIGINS` (add to existing config import).
- **GOTCHA**: Must add middleware BEFORE `include_router()`. The `allow_origins` param takes a list, not a string — split on comma.

```python
from fastapi.middleware.cors import CORSMiddleware
from src.config import CORS_ORIGINS, validate_provider_config

# In create_app():
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in CORS_ORIGINS.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(router)
```

- **VALIDATE**: `uv run python -c "from src.api.main import app; print('CORS configured')"`

---

### Task 3: UPDATE `src/api/routes.py` — Enhance health endpoint

- **IMPLEMENT**: Update the `/health` endpoint to check database connectivity. Accept `Request` parameter, attempt `SELECT 1` via the pool, return database status.
- **PATTERN**: Follow existing route handler pattern (lines 37-63). The `HealthResponse` schema needs updating too.
- **GOTCHA**: Must handle the case where pool is unavailable gracefully. Don't let the health check crash.

Update `src/api/schemas.py` — extend `HealthResponse`:
```python
class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    database: str = "unknown"
    version: str = "0.6.0"
```

Update `src/api/routes.py` — enhanced health endpoint:
```python
@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health(request: Request) -> HealthResponse:
    """Health check endpoint for Docker and load balancers."""
    pool = getattr(request.app.state, "pool", None)
    db_status = "unknown"

    if pool is not None:
        try:
            await pool.fetchval("SELECT 1")
            db_status = "healthy"
        except Exception:
            db_status = "unhealthy"

    return HealthResponse(
        status="healthy" if db_status != "unhealthy" else "degraded",
        database=db_status,
        version="0.6.0",
    )
```

- **GOTCHA**: The existing test `test_health_returns_200` in `tests/test_api.py` expects `{"status": "ok"}`. This test must be updated to match the new response shape: `{"status": "healthy", "database": "unknown", "version": "0.6.0"}`. The mock_pool in conftest.py does not wire up `fetchval`, so `pool.fetchval("SELECT 1")` will return the AsyncMock default (None, which is truthy enough to not raise), making `db_status = "healthy"`. Update the test assertion accordingly.
- **VALIDATE**: `uv run pytest tests/test_api.py::test_health_returns_200 -v`

---

### Task 4: UPDATE `.env.example` — Add Phase 6 environment variables

- **IMPLEMENT**: Add Phase 6 section at the end of `.env.example`.
- **PATTERN**: Follow existing section format (comment header, description, variable=default).

```env
# -----------------------------------------------------------------------------
# Frontend & Deployment (Phase 6)
# CORS_ORIGINS: Comma-separated list of allowed origins for CORS.
# Default points to the Vite dev server. Set to your domain in production.
# DOMAIN: Domain name for Caddy HTTPS. Use "localhost" for local development.
# Set to a real domain (e.g., agents.example.com) for automatic Let's Encrypt.
# VITE_API_BASE: Frontend API base URL. Default "/api" works with Caddy proxy.
# -----------------------------------------------------------------------------
CORS_ORIGINS=http://localhost:5173
DOMAIN=localhost
VITE_API_BASE=/api
```

- **VALIDATE**: Visual inspection — verify the section follows the existing format.

---

### Task 5: UPDATE `.gitignore` — Add frontend artifacts

- **IMPLEMENT**: Add frontend-specific ignores.

```gitignore
# Frontend (Phase 6)
frontend/node_modules/
frontend/dist/
```

- **VALIDATE**: `cat .gitignore | grep frontend`

---

### Task 6: CREATE `frontend/` — Scaffold Vite React-TS project

- **IMPLEMENT**: Run the following commands from the project root:

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

- **GOTCHA**: This creates a fresh Vite project. We will modify the generated files in subsequent tasks.
- **VALIDATE**: `cd frontend && npm run dev` (starts on port 5173, Ctrl+C to stop)

---

### Task 7: UPDATE `frontend/` — Initialize shadcn/ui

- **IMPLEMENT**: From the `frontend/` directory:

```bash
npx shadcn@latest init -t vite
```

This command will:
- Install Tailwind CSS v4 + `@tailwindcss/vite` plugin
- Configure `vite.config.ts` with the Tailwind plugin
- Set up path aliases (`@/` → `./src/`)
- Configure `tsconfig.json` path aliases
- Create `src/lib/utils.ts` with the `cn()` utility
- Set up CSS variables in `src/index.css`

Then add required components:
```bash
npx shadcn@latest add button input card badge scroll-area skeleton
```

- **GOTCHA**: The CLI is now `shadcn` (not `shadcn-ui`). The `-t vite` flag selects the Vite template. If prompted for options, select defaults.
- **VALIDATE**: `cd frontend && npm run build` (should compile without errors)

---

### Task 8: ADD `frontend/` — Install TanStack React Query

- **IMPLEMENT**: From the `frontend/` directory:

```bash
npm install @tanstack/react-query
```

- **VALIDATE**: `cd frontend && node -e "require('@tanstack/react-query')"`

---

### Task 9: CREATE `frontend/src/types/api.ts` — TypeScript types matching API schemas

- **IMPLEMENT**: Create TypeScript interfaces that mirror `src/api/schemas.py` and `src/agent/models.py` exactly.
- **PATTERN**: Match the Pydantic model field names and types exactly.

```typescript
/**
 * TypeScript interfaces matching the FastAPI backend schemas.
 *
 * These types mirror the Pydantic models in src/api/schemas.py and
 * src/agent/models.py. Keep them in sync when the backend changes.
 */

export interface Source {
  title: string;
  video_id: string;
  url: string;
}

export interface AskRequest {
  question: string;
}

export interface AskResponse {
  answer: string;
  sources: Source[];
}

export interface ResearchRequest {
  query: string;
}

export interface WorkflowResponse {
  answer: string;
  sources: Source[];
  confidence: number;
}

export interface MemoryAskRequest {
  question: string;
  user_id: string;
}

export interface MemoryAskResponse {
  answer: string;
  sources: Source[];
  confidence: number;
}

export interface HealthResponse {
  status: string;
  database: string;
  version: string;
}
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit`

---

### Task 10: CREATE `frontend/src/lib/api.ts` — API client

- **IMPLEMENT**: Create fetch-based API client functions for all three endpoints.
- **PATTERN**: Use `import.meta.env.VITE_API_BASE` for the base URL (configurable via env var, defaults to `/api`).
- **GOTCHA**: In dev mode, Vite proxy handles routing to `localhost:8000`. In production, Caddy/nginx handles it. The `VITE_API_BASE` env var lets both work.

```typescript
/**
 * API client for the AgentForge backend.
 *
 * Uses the native fetch API. The base URL is configurable via the
 * VITE_API_BASE environment variable (defaults to "/api").
 */

import type { AskResponse, HealthResponse, MemoryAskResponse, WorkflowResponse } from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new ApiError(response.status, `API error: ${response.status}`);
  }
  return response.json();
}

export async function askAgent(question: string): Promise<AskResponse> {
  return request<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export async function runResearch(query: string): Promise<WorkflowResponse> {
  return request<WorkflowResponse>("/research", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export async function askWithMemory(
  question: string,
  userId: string,
): Promise<MemoryAskResponse> {
  return request<MemoryAskResponse>("/ask/memory", {
    method: "POST",
    body: JSON.stringify({ question, user_id: userId }),
  });
}

export async function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { method: "GET" });
}
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit`

---

### Task 11: CREATE `frontend/src/hooks/useAgent.ts` — React Query hook for /api/ask

- **IMPLEMENT**: Create a `useMutation` hook wrapping `askAgent`.

```typescript
/**
 * React Query mutation hook for the single-agent endpoint.
 */

import { useMutation } from "@tanstack/react-query";
import { askAgent } from "../lib/api";
import type { AskResponse } from "../types/api";

export function useAgent() {
  return useMutation<AskResponse, Error, string>({
    mutationFn: (question: string) => askAgent(question),
  });
}
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit`

---

### Task 12: CREATE `frontend/src/hooks/useWorkflow.ts` — React Query hook for /api/research

- **IMPLEMENT**: Create a `useMutation` hook wrapping `runResearch`.

```typescript
/**
 * React Query mutation hook for the multi-agent research workflow.
 */

import { useMutation } from "@tanstack/react-query";
import { runResearch } from "../lib/api";
import type { WorkflowResponse } from "../types/api";

export function useWorkflow() {
  return useMutation<WorkflowResponse, Error, string>({
    mutationFn: (query: string) => runResearch(query),
  });
}
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit`

---

### Task 13: CREATE `frontend/src/components/chat/SourceCard.tsx`

- **IMPLEMENT**: A compact card displaying a cited source with a link.

```tsx
import { Badge } from "../ui/badge";
import type { Source } from "../../types/api";

interface SourceCardProps {
  source: Source;
}

export function SourceCard({ source }: SourceCardProps) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-2 rounded-md border p-2 text-sm hover:bg-muted transition-colors"
    >
      <Badge variant="outline" className="shrink-0">
        Source
      </Badge>
      <span className="truncate">{source.title}</span>
    </a>
  );
}
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit`

---

### Task 14: CREATE `frontend/src/components/chat/MessageBubble.tsx`

- **IMPLEMENT**: Display a single message (user or assistant) with optional sources and loading state.

```tsx
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Skeleton } from "../ui/skeleton";
import { SourceCard } from "./SourceCard";
import type { Source } from "../../types/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}

interface MessageBubbleProps {
  message?: Message;
  loading?: boolean;
}

export function MessageBubble({ message, loading }: MessageBubbleProps) {
  if (loading) {
    return (
      <div className="mb-4">
        <Skeleton className="h-4 w-3/4 mb-2" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    );
  }

  if (!message) return null;

  return (
    <div className={`mb-4 ${message.role === "user" ? "flex justify-end" : ""}`}>
      <div className={message.role === "user" ? "max-w-[80%]" : "max-w-[90%]"}>
        <Badge variant={message.role === "user" ? "default" : "secondary"} className="mb-1">
          {message.role === "user" ? "You" : "Agent"}
        </Badge>
        <Card className="p-3">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          {message.sources && message.sources.length > 0 && (
            <div className="mt-3 space-y-1.5 border-t pt-2">
              {message.sources.map((source, i) => (
                <SourceCard key={i} source={source} />
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

export type { Message };
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit`

---

### Task 15: CREATE `frontend/src/components/chat/InputBar.tsx`

- **IMPLEMENT**: Text input with send button, handles Enter key submission.

```tsx
import { useState } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";

interface InputBarProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function InputBar({ onSend, disabled }: InputBarProps) {
  const [value, setValue] = useState("");

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex gap-2 border-t p-4">
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question..."
        disabled={disabled}
        className="flex-1"
      />
      <Button onClick={handleSubmit} disabled={disabled || !value.trim()}>
        Send
      </Button>
    </div>
  );
}
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit`

---

### Task 16: CREATE `frontend/src/components/chat/ChatInterface.tsx`

- **IMPLEMENT**: Main chat UI composing MessageBubble, InputBar, and the useAgent hook.

```tsx
import { useRef, useEffect, useState } from "react";
import { useAgent } from "../../hooks/useAgent";
import type { Message } from "./MessageBubble";
import { MessageBubble } from "./MessageBubble";
import { InputBar } from "./InputBar";
import { ScrollArea } from "../ui/scroll-area";
import type { Source } from "../../types/api";

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const agent = useAgent();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, agent.isPending]);

  const handleSend = async (question: string) => {
    setMessages((prev) => [...prev, { role: "user", content: question }]);

    try {
      const response = await agent.mutateAsync(question);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.answer,
          sources: response.sources,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
        },
      ]);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <ScrollArea className="flex-1 p-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Ask a question to get started.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {agent.isPending && <MessageBubble loading />}
        <div ref={bottomRef} />
      </ScrollArea>
      <InputBar onSend={handleSend} disabled={agent.isPending} />
    </div>
  );
}
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit`

---

### Task 17: CREATE `frontend/src/components/layout/Header.tsx`

- **IMPLEMENT**: Simple app header with title.

```tsx
export function Header() {
  return (
    <header className="border-b px-6 py-3">
      <h1 className="text-lg font-semibold">AgentForge</h1>
    </header>
  );
}
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit`

---

### Task 18: CREATE `frontend/src/components/layout/MainLayout.tsx`

- **IMPLEMENT**: Full-page layout wrapping header and content.

```tsx
import { Header } from "./Header";

interface MainLayoutProps {
  children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className="flex flex-col h-screen">
      <Header />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit`

---

### Task 19: UPDATE `frontend/src/main.tsx` — Wire up QueryClientProvider

- **IMPLEMENT**: Replace the generated `main.tsx` with the app entry point wrapping everything in QueryClientProvider.

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 1,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
```

- **VALIDATE**: `cd frontend && npx tsc --noEmit`

---

### Task 20: UPDATE `frontend/src/App.tsx` — Root component

- **IMPLEMENT**: Replace the generated `App.tsx` with layout + chat interface.

```tsx
import { ChatInterface } from "./components/chat/ChatInterface";
import { MainLayout } from "./components/layout/MainLayout";

function App() {
  return (
    <MainLayout>
      <ChatInterface />
    </MainLayout>
  );
}

export default App;
```

- **VALIDATE**: `cd frontend && npm run build`

---

### Task 21: UPDATE `frontend/vite.config.ts` — Add dev proxy

- **IMPLEMENT**: Add a `server.proxy` configuration so that `/api` requests during development are proxied to the FastAPI backend at `localhost:8000`. The Tailwind and React plugins should already be configured by shadcn init.

```typescript
// Add to the existing defineConfig:
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
```

- **GOTCHA**: The shadcn init may have already configured vite.config.ts. Only ADD the `server` block — don't overwrite existing plugins.
- **VALIDATE**: `cd frontend && npm run build`

---

### Task 22: CREATE `frontend/Dockerfile` — Multi-stage frontend build

- **IMPLEMENT**: Two-stage build: node:20-alpine for building, nginx:alpine for serving.

```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- **VALIDATE**: Visual inspection — verify two-stage pattern matches backend Dockerfile conventions.

---

### Task 23: CREATE `frontend/nginx.conf` — SPA routing + API proxy

- **IMPLEMENT**: Nginx config that serves the built SPA and proxies `/api/` to the backend.

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # SPA routing — return index.html for all non-file routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to the FastAPI backend
    location /api/ {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy health check
    location /health {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
    }
}
```

- **GOTCHA**: The `proxy_pass` uses Docker service name `app` — only works inside Docker network.
- **VALIDATE**: Visual inspection — verify nginx directives are correct.

---

### Task 24: CREATE `config/caddy/Caddyfile` — Reverse proxy configuration

- **IMPLEMENT**: Caddy configuration routing frontend and API traffic.

```
{$DOMAIN:localhost} {
    # API — proxy to FastAPI backend
    handle /api/* {
        reverse_proxy app:8000
    }

    # Health check — proxy to backend
    handle /health {
        reverse_proxy app:8000
    }

    # Langfuse — optional observability UI
    handle /langfuse/* {
        reverse_proxy langfuse-server:3000
    }

    # Frontend — serves the React app (default handler)
    handle {
        reverse_proxy frontend:80
    }
}
```

- **GOTCHA**: `handle` blocks are evaluated in order of specificity. More specific paths (`/api/*`) must come before the catch-all. When `DOMAIN` is `localhost`, Caddy uses self-signed HTTPS or HTTP. When set to a real domain, Caddy auto-provisions Let's Encrypt certificates.
- **VALIDATE**: Visual inspection.

---

### Task 25: UPDATE `docker-compose.yml` — Add frontend and caddy services

- **IMPLEMENT**: Add `frontend` and `caddy` service definitions. Frontend always runs. Caddy runs with the `prod` profile.

Add after the `app` service block (before `volumes:`):

```yaml
  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - app
    restart: unless-stopped

  caddy:
    image: caddy:2-alpine
    profiles: ["prod"]
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./config/caddy/Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
      - caddy-config:/config
    environment:
      DOMAIN: ${DOMAIN:-localhost}
    depends_on:
      - app
      - frontend
    restart: unless-stopped
```

Add to the `volumes:` section:
```yaml
  caddy-data:
  caddy-config:
```

Also add Phase 6 env vars to the `app` service `environment` block:
```yaml
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:5173}
```

- **GOTCHA**: Caddy uses the `prod` profile — it's only started for production deployments. For local dev, developers use `npm run dev` (Vite dev server) directly with the proxy. Port 443/udp is for HTTP/3 support.
- **VALIDATE**: `docker compose config --services` (should list: supabase-db, langfuse-db, langfuse-server, ollama, searxng, redis, app, frontend, caddy)

---

### Task 26: CREATE `docker-compose.prod.yml` — Production overrides

- **IMPLEMENT**: Production-specific overrides for resource limits, health checks, and logging.

```yaml
services:
  app:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "0.5"
          memory: 512M
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  frontend:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:80 || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 3

  supabase-db:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 4G
        reservations:
          memory: 1G
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  caddy:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M

  langfuse-server:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G

  ollama:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

- **VALIDATE**: `docker compose -f docker-compose.yml -f docker-compose.prod.yml config --services`

---

### Task 27: CREATE `.env.production.example` — Production environment template

- **IMPLEMENT**: A complete production environment template. Follow the format of `.env.example` but with production-appropriate values and comments.

```env
# =============================================================================
# AgentForge — Production Environment
# Copy to .env and fill in values before deploying.
# =============================================================================

# Domain (required for HTTPS via Caddy)
DOMAIN=agents.example.com

# Database (point to shared Postgres on server)
DATABASE_URL=postgresql://agentforge:STRONG_PASSWORD@supabase-db:5432/agentforge

# Langfuse
LANGFUSE_HOST=http://langfuse-server:3000
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

# LLM Provider
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o
OPENAI_API_KEY=sk-...

# CORS (set to your domain)
CORS_ORIGINS=https://agents.example.com

# Frontend API base
VITE_API_BASE=/api

# Collector
YOUTUBE_API_KEY=...
COLLECTION_INTERVAL_MINUTES=60

# Memory
MEMORY_ENABLED=true
MEMORY_MODEL=gpt-4o-mini

# Search
SEARCH_PROVIDER=brave
BRAVE_SEARCH_API_KEY=BSA-...
BRAVE_SEARCH_ENABLED=true

# Caching
CACHE_ENABLED=false
REDIS_URL=redis://redis:6379/0
```

- **VALIDATE**: Visual inspection.

---

### Task 28: UPDATE `tests/test_api.py` — Fix health check test

- **IMPLEMENT**: Update the health check test to match the new response schema.
- **PATTERN**: Follow existing test patterns in the file.

```python
async def test_health_returns_200(client):
    """GET /health returns 200 with healthy status."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data
    assert data["version"] == "0.6.0"
```

- **VALIDATE**: `uv run pytest tests/test_api.py::test_health_returns_200 -v`

---

### Task 29: UPDATE `.github/workflows/ci.yml` — Add frontend CI job

- **IMPLEMENT**: Add a `frontend` job that runs lint and build checks.

```yaml
  # ---------------------------------------------------------------------------
  # Frontend — TypeScript check + build
  # ---------------------------------------------------------------------------
  frontend:
    name: Frontend
    runs-on: ubuntu-latest

    defaults:
      run:
        working-directory: frontend

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Type check
        run: npx tsc --noEmit

      - name: Build
        run: npm run build
```

- **VALIDATE**: Visual inspection — verify YAML indentation is correct.

---

### Task 30: CREATE `docs/deployment-guide.md` — Production deployment walkthrough

- **IMPLEMENT**: A step-by-step guide covering server setup, DNS, Docker deployment, HTTPS, monitoring, updates, and backups. Cover both bundled (standalone server) and shared infrastructure modes.
- **PATTERN**: Follow existing documentation style in `docs/` (markdown with clear headers, code blocks).
- **SECTIONS**:
  1. Prerequisites (Docker, domain name, API keys)
  2. Server Setup (install Docker, configure firewall 80/443, DNS)
  3. Shared Infrastructure (running Postgres, Langfuse, Ollama as shared services)
  4. Application Deployment (clone repo, configure .env, start services)
  5. HTTPS (how Caddy auto-provisions certificates)
  6. Monitoring (health endpoints, Langfuse traces, logs)
  7. Updating (pull images, restart)
  8. Backup (Postgres backup strategy)
- **VALIDATE**: Visual inspection.

---

### Task 31: CREATE `docs/frontend-customization.md` — Frontend template modification guide

- **IMPLEMENT**: Guide for customizing the chat UI, adding pages, connecting new endpoints, styling, and building.
- **SECTIONS**:
  1. Changing the Chat UI (modifying ChatInterface.tsx, adding message types)
  2. Adding New Pages (if React Router is added)
  3. Connecting New API Endpoints (adding hooks, types, API client functions)
  4. Styling (Tailwind customization, shadcn/ui theme via CSS variables)
  5. Building for Production (`npm run build`, Docker image)
- **VALIDATE**: Visual inspection.

---

### Task 32: CREATE `frontend/public/favicon.svg` — App favicon

- **IMPLEMENT**: Simple SVG favicon for AgentForge.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#18181b"/>
  <text x="16" y="23" text-anchor="middle" font-family="system-ui" font-size="18" font-weight="bold" fill="#fafafa">AF</text>
</svg>
```

- **VALIDATE**: Visual inspection.

---

## TESTING STRATEGY

### Backend Tests (Python/Pytest)

- Update existing `test_health_returns_200` to match new response schema (Task 28)
- Run full existing test suite to verify no regressions from CORS/health changes
- Health check test should verify database status field is present

### Frontend Tests (TypeScript)

- TypeScript compilation (`npx tsc --noEmit`) serves as the primary validation for type correctness
- Production build (`npm run build`) validates that all components compile and bundle correctly
- Manual testing of the chat interface against the running backend

### Integration Tests

- Run `docker compose up` and verify frontend loads at `http://localhost:3000`
- Submit a question through the chat UI and verify response renders with sources
- Verify the Vite dev proxy works: `cd frontend && npm run dev`, then submit questions at `http://localhost:5173`

### Edge Cases

- Empty chat state displays placeholder message
- API error returns user-friendly error message in chat
- Long messages wrap properly
- Multiple sources render correctly
- Enter key submits, Shift+Enter does not
- Input is disabled while agent is processing

---

## VALIDATION COMMANDS

### Level 1: Backend Syntax & Style

```bash
uv run ruff check .
uv run ruff format --check .
```

**Expected**: All commands pass with exit code 0.

### Level 2: Backend Tests

```bash
uv run pytest tests/ -v --tb=short
```

**Expected**: All tests pass, including updated health check test.

### Level 3: Frontend Type Check & Build

```bash
cd frontend && npx tsc --noEmit
cd frontend && npm run build
```

**Expected**: Zero TypeScript errors. Build produces `frontend/dist/` directory.

### Level 4: Docker Build

```bash
docker compose build app frontend
docker compose config --services
```

**Expected**: Both images build successfully. Services list includes `frontend` and `caddy`.

### Level 5: Manual Validation

```bash
# Start backend
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# In another terminal, start frontend dev server
cd frontend && npm run dev

# Open http://localhost:5173 in browser
# Submit a question and verify response renders
```

---

## ACCEPTANCE CRITERIA

- [ ] `frontend/` directory contains a complete React + Vite + TypeScript + shadcn/ui application
- [ ] `npm run dev` in `frontend/` starts a development server connected to the FastAPI backend via proxy
- [ ] Chat interface sends questions to `POST /api/ask` and displays structured responses with sources
- [ ] Frontend Docker image builds and serves production build via nginx
- [ ] Caddy routes `/` to frontend and `/api/*` to backend
- [ ] When `DOMAIN` is a real domain, Caddy provisions HTTPS automatically
- [ ] When `DOMAIN` is `localhost`, stack works without HTTPS
- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml up` starts all services with production settings
- [ ] All services have restart policies (`unless-stopped`)
- [ ] All services have resource limits (CPU and memory) in production config
- [ ] Health check endpoint (`/health`) checks database connectivity and is used by Docker health checks
- [ ] Production logging configured with rotation (max-size, max-file)
- [ ] `.env.production.example` documents all production environment variables
- [ ] `docs/deployment-guide.md` provides complete deployment walkthrough
- [ ] `docs/frontend-customization.md` covers modifying the template
- [ ] CORS configured and works correctly (frontend at different origin during development)
- [ ] Backend tests pass with zero regressions
- [ ] Frontend builds with zero TypeScript errors
- [ ] CI pipeline includes frontend lint/build job

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (Tasks 1-32)
- [ ] Each task validation passed immediately
- [ ] All validation commands executed successfully:
  - [ ] Level 1: `ruff check`, `ruff format --check`
  - [ ] Level 2: `pytest tests/ -v`
  - [ ] Level 3: `tsc --noEmit`, `npm run build`
  - [ ] Level 4: `docker compose build`
  - [ ] Level 5: Manual browser testing
- [ ] Full backend test suite passes
- [ ] No linting errors
- [ ] No formatting errors
- [ ] Frontend builds successfully
- [ ] All acceptance criteria met
- [ ] Code reviewed for quality and maintainability

---

## NOTES

### Key Design Decisions

1. **Tailwind CSS v4 (not v3)**: v4 uses `@tailwindcss/vite` plugin — no `tailwind.config.js` or `postcss.config.js` needed. Zero-config content detection. The Phase 6 spec mentions PostCSS but this is outdated for v4.

2. **shadcn CLI is now `shadcn` (not `shadcn-ui`)**: The package was renamed. Use `npx shadcn@latest init -t vite` which handles Tailwind v4, path aliases, and all configuration automatically.

3. **Caddy on `prod` profile only**: Caddy is a production concern. During development, the Vite dev server proxies API requests directly. This avoids port conflicts and extra containers during development.

4. **Frontend always builds**: Unlike Caddy, the frontend service has no profile — it starts with any `docker compose up` command. This lets developers test the production build locally.

5. **Health endpoint enhanced, not replaced**: The existing `/health` endpoint is enhanced to check database connectivity while maintaining backward compatibility. Version bumped to `0.6.0`.

6. **No React Router**: The Phase 6 spec keeps the frontend as a single-page chat interface. React Router can be added later if pages are needed, but it's unnecessary complexity for the template.

### Implementation Risks

- **shadcn init may produce unexpected output**: The `npx shadcn@latest init -t vite` command is interactive. If running non-interactively, use `--defaults --yes` flags.
- **Tailwind v4 CSS variables**: shadcn/ui components rely on CSS variables. The shadcn init should configure these, but verify the `index.css` has the correct `@theme` block.
- **Docker networking**: Frontend nginx proxies to `app:8000` using Docker service names. This only works inside the Docker network — verify the `docker-compose.yml` services are on the same default network.
- **CORS in production**: When using Caddy, CORS may be unnecessary (same origin). But during development with Vite dev server, CORS is required. The `CORS_ORIGINS` env var handles both cases.

### What the Phase 6 Spec Says vs What's Changed

| Spec Says | Current Reality | Action |
|-----------|----------------|--------|
| `npx shadcn-ui@latest init` | CLI renamed to `npx shadcn@latest` | Use new CLI name |
| PostCSS + tailwind.config.js | Tailwind v4 uses Vite plugin, no config files | Use `@tailwindcss/vite` |
| Separate `Caddyfile` at root | Better organized in `config/caddy/` | Place in `config/caddy/Caddyfile` |
| Health returns `{"status": "ok"}` | Enhanced to check DB + return version | Update existing test |
