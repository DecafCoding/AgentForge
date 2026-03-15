# Phase 6 — Application Layer & Deployment

*AgentForge Starter Kit*

---

## Purpose of This Document

This document contains everything an AI or developer needs to build Phase 6 of AgentForge. It is self-contained. Phase 6 adds a frontend template (React + Vite + shadcn/ui), reverse proxy with HTTPS (Caddy), and production Docker configuration — making the kit ready for applications that face real users, not just developers testing from the command line.

---

## Prerequisites (Phases 1–5 Complete)

Phase 6 assumes the following are already built and working:

**From Phase 1:**
- Project structure with `uv`, `ruff`, Docker Compose (bundled + shared profiles)
- Postgres 15 + pgvector with Alembic migrations and asyncpg driver
- Pydantic AI agent with tool registration and structured output (Pattern 1)
- FastAPI API layer with lifespan hook and APScheduler
- Langfuse observability wired into all agent calls
- Collector/reasoning separation enforced by module structure
- Multi-provider support (OpenAI, Groq) via env vars
- Pytest skeleton and GitHub Actions CI

**From Phase 2:**
- LangGraph multi-agent orchestration (Pattern 2)
- Cross-agent Langfuse traces

**From Phase 3:**
- Mem0 long-term memory, Crawl4AI web scraping, Brave Search

**From Phase 4:**
- Ollama local model serving, SearXNG self-hosted search, Redis/Valkey caching

**From Phase 5:**
- Ragas evaluation pipelines, FastMCP server exposure, testing patterns documentation

---

## What Phase 6 Delivers

Three capabilities that take AgentForge from a developer tool to a deployable application platform:

1. **Frontend Template** — React + Vite + shadcn/ui connected to the FastAPI backend. A chat-style interface for interacting with agents, displaying structured responses with sources, and showing workflow status.
2. **Reverse Proxy & HTTPS** — Caddy configuration for production routing and automatic HTTPS certificate management. Terminates TLS and routes traffic to the correct services.
3. **Production Docker Configuration** — Resource limits, restart policies, health checks, log management, and a production-specific environment template. Everything needed to run AgentForge reliably on a server.

---

## Design Philosophy

**The frontend is a template, not an application.** It provides the structure, component library, API integration patterns, and styling foundation. Developers customize it for their specific agent's UI needs. It is intentionally minimal — a working starting point, not a finished product.

**Caddy over Nginx/Traefik.** Caddy provides automatic HTTPS via Let's Encrypt with zero configuration, a simple Caddyfile syntax, and sensible defaults. For a single-server deployment, it is the simplest path to production-ready routing.

**Production config is a separate concern.** Development and production Docker configurations are separate. The production config adds resource limits, restart policies, and health checks that would be annoying during development.

---

## Technology Additions

| Layer | Tool | Role |
|-------|------|------|
| Application | React 18 | UI framework |
| Application | Vite | Build tool and dev server |
| Application | shadcn/ui | Component library (Tailwind CSS based) |
| Application | TypeScript | Frontend type safety |
| Infrastructure | Caddy | Reverse proxy, automatic HTTPS |

---

## Project Structure Changes

```
agentforge/
├── docker-compose.yml              # EXISTING — Development config
├── docker-compose.prod.yml         # NEW — Production overrides
├── Caddyfile                       # NEW — Caddy reverse proxy config
│
├── frontend/                       # NEW — React frontend application
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── Dockerfile                  # Frontend container (nginx serving built assets)
│   │
│   ├── src/
│   │   ├── main.tsx                # App entry point
│   │   ├── App.tsx                 # Root component with routing
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                 # shadcn/ui components
│   │   │   │   ├── button.tsx
│   │   │   │   ├── input.tsx
│   │   │   │   ├── card.tsx
│   │   │   │   ├── badge.tsx
│   │   │   │   ├── scroll-area.tsx
│   │   │   │   └── skeleton.tsx
│   │   │   │
│   │   │   ├── chat/
│   │   │   │   ├── ChatInterface.tsx    # Main chat UI
│   │   │   │   ├── MessageBubble.tsx    # Individual message display
│   │   │   │   ├── SourceCard.tsx       # Source citation display
│   │   │   │   └── InputBar.tsx         # Message input with send button
│   │   │   │
│   │   │   └── layout/
│   │   │       ├── Header.tsx
│   │   │       ├── Sidebar.tsx
│   │   │       └── MainLayout.tsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useAgent.ts         # Hook for POST /api/ask
│   │   │   └── useWorkflow.ts      # Hook for POST /api/research
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts              # API client (fetch wrapper)
│   │   │   └── utils.ts            # Utility functions
│   │   │
│   │   └── types/
│   │       └── api.ts              # TypeScript types matching API schemas
│   │
│   └── public/
│       └── favicon.svg
│
├── src/                            # EXISTING backend
│   ├── api/
│   │   ├── main.py                 # MODIFIED — Add CORS middleware
│   │   └── routes.py               # MODIFIED — Add streaming endpoint (optional)
│
├── config/
│   └── caddy/
│       └── Caddyfile               # Caddy configuration
│
└── docs/
    ├── deployment-guide.md         # NEW — Production deployment walkthrough
    └── frontend-customization.md   # NEW — How to modify the frontend template
```

---

## Product Backlog Items (PBIs)

### PBI 6.1 — Frontend Template

**Description:** React + Vite + shadcn/ui, connected to FastAPI backend.

**Done when:** Template renders agent responses from the API.

**Implementation details:**

**Frontend setup:**

```bash
# Initialize with Vite
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install

# Add shadcn/ui
npx shadcn-ui@latest init
npx shadcn-ui@latest add button input card badge scroll-area skeleton

# Add API client dependency
npm install @tanstack/react-query
```

**`frontend/src/types/api.ts`** — TypeScript types matching the FastAPI schemas:

```typescript
export interface AskRequest {
  question: string;
}

export interface Source {
  title: string;
  video_id: string;
  url: string;
}

export interface AskResponse {
  answer: string;
  sources: Source[];
}

export interface ResearchRequest {
  query: string;
}

export interface WorkflowResponse {
  result: string;
  steps_completed: number;
  agents_used: string[];
}
```

**`frontend/src/lib/api.ts`** — API client:

```typescript
const API_BASE = import.meta.env.VITE_API_BASE || "/api";

export async function askAgent(question: string): Promise<AskResponse> {
  const response = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export async function runResearch(query: string): Promise<WorkflowResponse> {
  const response = await fetch(`${API_BASE}/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}
```

**`frontend/src/hooks/useAgent.ts`** — React Query hook:

```typescript
import { useMutation } from "@tanstack/react-query";
import { askAgent, AskResponse } from "../lib/api";

export function useAgent() {
  return useMutation<AskResponse, Error, string>({
    mutationFn: (question: string) => askAgent(question),
  });
}
```

**`frontend/src/components/chat/ChatInterface.tsx`** — Main chat UI:

```tsx
import { useState } from "react";
import { useAgent } from "../../hooks/useAgent";
import { MessageBubble } from "./MessageBubble";
import { InputBar } from "./InputBar";
import { ScrollArea } from "../ui/scroll-area";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}

export function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const agent = useAgent();

  const handleSend = async (question: string) => {
    // Add user message
    setMessages((prev) => [...prev, { role: "user", content: question }]);

    // Call agent API
    const response = await agent.mutateAsync(question);

    // Add assistant response
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: response.answer,
        sources: response.sources,
      },
    ]);
  };

  return (
    <div className="flex flex-col h-full">
      <ScrollArea className="flex-1 p-4">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {agent.isPending && <MessageBubble loading />}
      </ScrollArea>
      <InputBar onSend={handleSend} disabled={agent.isPending} />
    </div>
  );
}
```

**`frontend/src/components/chat/MessageBubble.tsx`:**

```tsx
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { Skeleton } from "../ui/skeleton";
import { SourceCard } from "./SourceCard";

export function MessageBubble({ message, loading }: Props) {
  if (loading) {
    return (
      <div className="mb-4">
        <Skeleton className="h-4 w-3/4 mb-2" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    );
  }

  return (
    <div className={`mb-4 ${message.role === "user" ? "text-right" : ""}`}>
      <Badge variant={message.role === "user" ? "default" : "secondary"}>
        {message.role}
      </Badge>
      <Card className="mt-1 p-3">
        <p className="text-sm">{message.content}</p>
        {message.sources?.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.sources.map((source, i) => (
              <SourceCard key={i} source={source} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
```

**Backend CORS update in `src/api/main.py`:**

```python
from fastapi.middleware.cors import CORSMiddleware

def create_app() -> FastAPI:
    app = FastAPI(title="AgentForge", lifespan=lifespan)

    # CORS for frontend development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes.router)
    return app
```

**Frontend Dockerfile:**

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

**Frontend nginx.conf (for serving SPA):**

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### PBI 6.2 — Reverse Proxy & HTTPS

**Description:** Caddy configuration for production routing.

**Done when:** HTTPS terminates at Caddy. Services are routed correctly.

**Implementation details:**

**`Caddyfile`:**

```
{$DOMAIN:localhost} {
    # Frontend — serves the React app
    handle {
        reverse_proxy frontend:80
    }

    # API — proxy to FastAPI backend
    handle /api/* {
        reverse_proxy app:8000
    }

    # Langfuse — optional, only if exposed
    handle /langfuse/* {
        reverse_proxy langfuse-server:3000
    }

    # Automatic HTTPS via Let's Encrypt (when DOMAIN is set to a real domain)
    # For localhost, Caddy serves HTTP or self-signed HTTPS
}
```

**Docker Compose addition:**

```yaml
services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
      - caddy-config:/config
    environment:
      DOMAIN: ${DOMAIN:-localhost}
    depends_on:
      - app
      - frontend

volumes:
  caddy-data:
  caddy-config:
```

**How Caddy handles HTTPS:**
- When `DOMAIN` is set to a real domain (e.g., `agents.example.com`), Caddy automatically provisions a Let's Encrypt TLS certificate
- When `DOMAIN` is `localhost`, Caddy serves locally with self-signed certificates or plain HTTP
- Zero manual certificate management
- Automatic certificate renewal

**Routing architecture:**

```
Internet
    ↓
  Caddy (:80/:443)
    ├── /              → frontend (:80)     React SPA
    ├── /api/*         → app (:8000)        FastAPI backend
    └── /langfuse/*    → langfuse (:3000)   Observability UI (optional)
```

### PBI 6.3 — Production Docker Configuration

**Description:** Resource limits, restart policies, production env template.

**Done when:** Production compose file runs reliably with appropriate constraints.

**Implementation details:**

**`docker-compose.prod.yml`** — Production overrides (used with `docker compose -f docker-compose.yml -f docker-compose.prod.yml up`):

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
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
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
      test: ["CMD", "curl", "-f", "http://localhost:80"]
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

**Health check endpoint in FastAPI:**

```python
# Add to src/api/routes.py
@router.get("/health")
async def health(request: Request):
    """Health check endpoint for Docker and load balancers."""
    pool = request.app.state.pool
    try:
        await pool.fetchval("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": "0.6.0",
    }
```

**`.env.production.example`** — Production environment template:

```env
# === Production Environment ===
# Copy to .env and fill in values before deploying

# Domain (required for HTTPS)
DOMAIN=agents.example.com

# Database (point to shared Postgres on server)
DATABASE_URL=postgresql://agentforge:STRONG_PASSWORD@postgres:5432/agentforge

# Langfuse (point to shared Langfuse)
LANGFUSE_HOST=http://langfuse:3000
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

# LLM Provider
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o
OPENAI_API_KEY=sk-...

# CORS (set to your domain)
CORS_ORIGINS=https://agents.example.com

# Frontend API base (for production, API is at same domain)
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

# Caching (enable only if needed)
CACHE_ENABLED=false
REDIS_URL=redis://redis:6379/0
```

**Production deployment commands:**

```bash
# Development (laptop)
docker compose --profile bundled up

# Production (server with shared infra)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Production with bundled infra (standalone server)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile bundled up -d

# View logs
docker compose logs -f app

# Rolling restart (zero downtime if multiple replicas)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps app
```

---

## Documentation

### `docs/deployment-guide.md`

Should cover:

1. **Prerequisites:** Docker, domain name (for HTTPS), API keys
2. **Server setup:** Install Docker, configure firewall (80, 443), set up DNS
3. **Shared infrastructure setup:** How to run Postgres, Langfuse, Ollama as shared services for multiple projects
4. **Application deployment:** Clone repo, configure `.env`, start services
5. **HTTPS:** How Caddy auto-provisions certificates
6. **Monitoring:** Checking health endpoints, viewing Langfuse traces, reading logs
7. **Updating:** How to pull new images and restart
8. **Backup:** Postgres backup strategy for production data

### `docs/frontend-customization.md`

Should cover:

1. **Changing the chat UI:** How to modify `ChatInterface.tsx`, add new message types
2. **Adding new pages:** Router setup, creating new views
3. **Connecting to new API endpoints:** Adding hooks, types, API client functions
4. **Styling:** Tailwind customization, shadcn/ui theme configuration
5. **Building for production:** `npm run build`, Docker image creation

---

## Acceptance Criteria (Phase 6 Complete)

All of these must be true (in addition to all Phase 1–5 criteria still passing):

1. `frontend/` directory contains a complete React + Vite + TypeScript + shadcn/ui application
2. `npm run dev` in `frontend/` starts a development server that connects to the FastAPI backend
3. The chat interface sends questions to `POST /api/ask` and displays structured responses with sources
4. The frontend Docker image builds and serves the production build via nginx
5. Caddy routes `/` to the frontend and `/api/*` to the backend
6. When `DOMAIN` is set to a real domain, Caddy provisions HTTPS certificates automatically
7. When `DOMAIN` is `localhost`, the stack works without HTTPS
8. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up` starts all services with production settings
9. All services have restart policies (`unless-stopped`)
10. All services have resource limits (CPU and memory)
11. Health check endpoints exist for the app (`/health`) and are used by Docker health checks
12. Production logging is configured with rotation (max-size, max-file)
13. `.env.production.example` documents all production environment variables
14. `docs/deployment-guide.md` provides a complete walkthrough from server setup to running application
15. `docs/frontend-customization.md` covers modifying the template for custom agent UIs
16. CORS is configured and works correctly (frontend at different origin during development)
17. A developer can go from clone to deployed, HTTPS-enabled application by following the documentation

---

## What This Completes

Phase 6 is the final phase of the AgentForge MVP roadmap. After this phase, the kit delivers:

| Phase | What It Added |
|-------|---------------|
| Phase 1 | Core platform — single agent with tools, data collection, observability, Docker |
| Phase 2 | Multi-agent orchestration — LangGraph, Pattern 2, cross-agent tracing |
| Phase 3 | Memory & web intelligence — Mem0, Crawl4AI, Brave Search |
| Phase 4 | Local AI & caching — Ollama, SearXNG, Redis |
| Phase 5 | Evaluation & quality — Ragas, FastMCP, testing patterns |
| Phase 6 | Application layer — React frontend, Caddy HTTPS, production Docker |

A developer can now clone AgentForge, choose their pattern (single agent or multi-agent), build their agent logic, and deploy it as a production application with a frontend, HTTPS, and observability — using cloud providers or fully local infrastructure.

---

*This document is the complete specification for Phase 6 of AgentForge. It contains everything needed to add the frontend, reverse proxy, and production deployment without referencing external documents.*
