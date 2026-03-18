# PBI 6.2 — Reverse Proxy & Production Docker

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Add Docker packaging for the frontend, Caddy reverse proxy for production routing with automatic HTTPS, production Docker Compose overrides with resource limits/health checks/log rotation, and a production environment template.

## User Story

As an AI agent developer deploying to a server
I want a reverse proxy with automatic HTTPS and production-ready Docker configuration
So that I can deploy my agent application securely without manually configuring certificates or resource limits.

## Problem Statement

After PBI 6.1, the frontend runs locally via Vite dev server but has no production container. There is no reverse proxy to route traffic, no HTTPS, and no production-specific Docker configuration (resource limits, health checks, log rotation).

## Solution Statement

Create a frontend Dockerfile (multi-stage: node build + nginx serve), add Caddy as a reverse proxy with automatic Let's Encrypt HTTPS, create a production Docker Compose override file, and provide a production environment template.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `frontend/Dockerfile`, `frontend/nginx.conf`, `config/caddy/Caddyfile`, `docker-compose.yml`, `docker-compose.prod.yml`, `.env.production.example`
**Dependencies**: Caddy 2 (Docker image), nginx (in frontend container)
**Prerequisite**: PBI 6.1 must be complete (frontend application exists and builds)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `docker-compose.yml` (lines 1-151) — Why: Existing service definitions, profiles, and volume patterns. New services (frontend, caddy) must follow the same conventions.
- `Dockerfile` (lines 1-48) — Why: Existing multi-stage build pattern for the backend. Frontend Dockerfile should follow similar conventions.
- `.env.example` (lines 1-118+) — Why: Current env var documentation pattern. Production template must follow same format.
- `src/api/routes.py` (lines 30-34) — Why: The `/health` endpoint that Docker health checks will hit.

### New Files to Create

- `frontend/Dockerfile` — Multi-stage build (node:20-alpine → nginx:alpine)
- `frontend/nginx.conf` — Nginx config for SPA serving + API proxy
- `config/caddy/Caddyfile` — Caddy reverse proxy configuration
- `docker-compose.prod.yml` — Production overrides (resource limits, health checks, logging)
- `.env.production.example` — Production environment template

### Relevant Documentation — YOU SHOULD READ THESE BEFORE IMPLEMENTING!

- [Caddy Reverse Proxy Quick Start](https://caddyserver.com/docs/quick-starts/reverse-proxy)
  - Why: Caddyfile syntax for reverse_proxy directive
- [Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https)
  - Why: Understanding localhost (self-signed) vs real domain (Let's Encrypt) behavior
- [Caddy Docker documentation](https://hub.docker.com/_/caddy)
  - Why: Correct volume mounts (`/data`, `/config`) and image tags

### Patterns to Follow

**Docker Compose Service Pattern (from `docker-compose.yml`):**
```yaml
services:
  service-name:
    image: ...
    profiles: ["bundled"]
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

**Existing Backend Dockerfile Pattern (from `Dockerfile`):**
- Two-stage build (builder → runtime)
- Copy dependency manifest first for cache efficiency
- Slim runtime image

---

## IMPLEMENTATION PLAN

### Phase 1: Frontend Docker

Create the Dockerfile and nginx config for serving the built React SPA.

### Phase 2: Caddy Reverse Proxy

Create the Caddyfile for routing traffic to frontend and backend.

### Phase 3: Docker Compose Updates

Add frontend and caddy services to docker-compose.yml, create production overrides.

### Phase 4: Production Environment

Create the production environment template.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: CREATE `frontend/Dockerfile` — Multi-stage frontend build

- **IMPLEMENT**: Two-stage build: node:20-alpine for building, nginx:alpine for serving.
- **PATTERN**: Mirror the backend Dockerfile's two-stage approach (builder → runtime).

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

- **VALIDATE**: `cd frontend && docker build -t agentforge-frontend .`

---

### Task 2: CREATE `frontend/nginx.conf` — SPA routing + API proxy

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

- **GOTCHA**: The `proxy_pass` uses Docker service name `app` — only works inside the Docker network. Does not work standalone.
- **VALIDATE**: Visual inspection — verify nginx directives are correct.

---

### Task 3: CREATE `config/caddy/Caddyfile` — Reverse proxy configuration

- **IMPLEMENT**: Caddy configuration routing frontend and API traffic. Uses `handle` (not `handle_path`) to preserve the `/api/` prefix since FastAPI routes include it.

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

- **GOTCHA**: `handle` blocks are evaluated by specificity — more specific paths (`/api/*`) match before the catch-all. When `DOMAIN` is `localhost`, Caddy uses self-signed HTTPS or HTTP. When set to a real domain, Caddy auto-provisions Let's Encrypt certificates. Use `handle` not `handle_path` to preserve the URL prefix.
- **VALIDATE**: Visual inspection.

---

### Task 4: UPDATE `docker-compose.yml` — Add frontend and caddy services

- **IMPLEMENT**: Add `frontend` and `caddy` service definitions. Frontend always runs. Caddy runs with the `prod` profile.
- **PATTERN**: Follow existing service patterns (profiles, depends_on, environment with defaults).

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

Also add Phase 6 env var to the `app` service `environment` block:
```yaml
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:5173}
```

- **GOTCHA**: Caddy uses the `prod` profile — only started for production. Port 443/udp is for HTTP/3 (QUIC) support. Frontend has no profile — starts with any `docker compose up`.
- **VALIDATE**: `docker compose config --services` (should list all services including `frontend` and `caddy`)

---

### Task 5: CREATE `docker-compose.prod.yml` — Production overrides

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

### Task 6: CREATE `.env.production.example` — Production environment template

- **IMPLEMENT**: A complete production environment template with production-appropriate values.

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

## TESTING STRATEGY

### Docker Build Tests

- `docker build -t agentforge-frontend ./frontend` — verify frontend image builds
- `docker compose build` — verify all images build
- `docker compose config --services` — verify service list is correct

### Integration Tests

- `docker compose up app frontend` — verify frontend serves at `http://localhost:3000`
- Submit a question through the frontend at port 3000 and verify API proxying works via nginx
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` — verify production config merges correctly

---

## VALIDATION COMMANDS

### Level 1: Docker Build

```bash
cd frontend && docker build -t agentforge-frontend .
docker compose config --services
```

### Level 2: Docker Compose Validation

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --services
```

### Level 3: Integration Test

```bash
docker compose --profile bundled up -d
# Wait for services to start, then:
curl http://localhost:3000        # Frontend
curl http://localhost:8000/health  # Backend health
```

---

## ACCEPTANCE CRITERIA

- [ ] Frontend Docker image builds successfully (multi-stage: node build → nginx serve)
- [ ] Frontend nginx config serves SPA correctly (all routes → index.html)
- [ ] Frontend nginx proxies `/api/*` to the backend container
- [ ] Caddy routes `/` to frontend and `/api/*` to backend
- [ ] When `DOMAIN` is a real domain, Caddy provisions HTTPS automatically
- [ ] When `DOMAIN` is `localhost`, stack works without HTTPS issues
- [ ] `docker compose -f docker-compose.yml -f docker-compose.prod.yml up` starts all services
- [ ] All services have restart policies (`unless-stopped`) in production config
- [ ] All services have resource limits (CPU and memory) in production config
- [ ] Production logging configured with rotation (max-size, max-file)
- [ ] `.env.production.example` documents all production environment variables

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (Tasks 1-6)
- [ ] Each task validation passed
- [ ] Docker builds succeed
- [ ] Docker Compose config validates
- [ ] All acceptance criteria met

---

## NOTES

### Key Design Decisions

1. **Caddy on `prod` profile only**: Caddy is a production concern. During development, the Vite dev server proxies API requests directly. This avoids port conflicts and extra containers during development.

2. **Frontend always builds**: Unlike Caddy, the frontend service has no profile — it starts with any `docker compose up` command. This lets developers test the production build locally at port 3000.

3. **`handle` not `handle_path`**: Caddy's `handle_path` strips the matched prefix before proxying. Since FastAPI routes are defined as `/api/ask` (with the prefix), we use `handle` to preserve the full path.

4. **Port 443/udp for HTTP/3**: Caddy supports HTTP/3 (QUIC) out of the box. The UDP port mapping enables this.

### Routing Architecture

```
Internet
    ↓
  Caddy (:80/:443)
    ├── /              → frontend (:80)     React SPA
    ├── /api/*         → app (:8000)        FastAPI backend
    ├── /health        → app (:8000)        Health check
    └── /langfuse/*    → langfuse (:3000)   Observability UI (optional)
```

### Deployment Commands

```bash
# Development (laptop)
docker compose --profile bundled up

# Production (standalone server with bundled infra)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile bundled --profile prod up -d

# Production (shared infrastructure)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile prod up -d

# View logs
docker compose logs -f app

# Rolling restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps app
```
