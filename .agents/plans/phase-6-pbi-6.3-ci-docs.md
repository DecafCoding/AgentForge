# PBI 6.3 — CI/CD & Documentation

The following plan should be complete, but its important that you validate documentation and codebase patterns and task sanity before you start implementing.

Pay special attention to naming of existing utils types and models. Import from the right files etc.

## Feature Description

Update the CI pipeline to lint and build the frontend, and write deployment and frontend customization documentation. This is the wrap-up PBI that makes Phase 6 complete and production-ready.

## User Story

As an AI agent developer
I want CI to validate my frontend changes and comprehensive deployment documentation
So that I can deploy with confidence and customize the frontend template for my agent's needs.

## Problem Statement

After PBIs 6.1 and 6.2, the frontend exists and Docker infrastructure is in place, but CI doesn't validate frontend changes (TypeScript errors, build failures could slip through), and there's no documentation for deployment or frontend customization.

## Solution Statement

Add a frontend CI job (TypeScript check + build), write a deployment guide covering server setup through running application, and write a frontend customization guide for modifying the template.

## Feature Metadata

**Feature Type**: Enhancement
**Estimated Complexity**: Low
**Primary Systems Affected**: `.github/workflows/ci.yml`, `docs/deployment-guide.md`, `docs/frontend-customization.md`
**Dependencies**: None (documentation only + CI config)
**Prerequisite**: PBIs 6.1 and 6.2 must be complete

---

## CONTEXT REFERENCES

### Relevant Codebase Files — IMPORTANT: YOU MUST READ THESE FILES BEFORE IMPLEMENTING!

- `.github/workflows/ci.yml` (lines 1-94) — Why: Existing CI pipeline structure. New frontend job must follow the same patterns (job naming, step structure, caching).
- `docs/local-ai-guide.md` — Why: Example of existing documentation style and depth.
- `docs/memory-aware-agents.md` — Why: Example of existing documentation structure.
- `docs/pattern-decision-guide.md` — Why: Example of how architectural decisions are documented.
- `docker-compose.yml` — Why: Referenced in deployment guide for startup commands.
- `docker-compose.prod.yml` — Why: Referenced in deployment guide for production commands.
- `.env.production.example` — Why: Referenced in deployment guide for configuration.
- `frontend/package.json` — Why: Needed to understand npm scripts for CI.

### New Files to Create

- `docs/deployment-guide.md` — Production deployment walkthrough
- `docs/frontend-customization.md` — How to modify the frontend template

### Files to Modify

- `.github/workflows/ci.yml` — Add frontend lint/build job

### Relevant Documentation

- [GitHub Actions setup-node](https://github.com/actions/setup-node)
  - Why: Node.js setup action for CI
- [Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https)
  - Why: Referenced in deployment guide for HTTPS setup

### Patterns to Follow

**CI Job Pattern (from `.github/workflows/ci.yml`):**
```yaml
  job-name:
    name: Display Name
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
      # ... setup steps
      # ... validation steps
```

**Documentation Pattern (from existing docs):**
- Clear headers with `##` sections
- Code blocks for all commands
- Step-by-step instructions
- Notes/warnings where appropriate

---

## IMPLEMENTATION PLAN

### Phase 1: CI Pipeline Update

Add a frontend job to the GitHub Actions workflow.

### Phase 2: Deployment Documentation

Write the deployment guide covering the full server-to-running-app path.

### Phase 3: Customization Documentation

Write the frontend customization guide for template modification.

---

## STEP-BY-STEP TASKS

IMPORTANT: Execute every task in order, top to bottom. Each task is atomic and independently testable.

---

### Task 1: UPDATE `.github/workflows/ci.yml` — Add frontend CI job

- **IMPLEMENT**: Add a `frontend` job that runs TypeScript checks and builds the frontend.
- **PATTERN**: Follow the existing `lint` and `test` job patterns.

Add after the `test` job:

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

- **GOTCHA**: The `defaults.run.working-directory` sets all `run` steps to execute inside `frontend/`. The `cache-dependency-path` must point to the lock file for npm caching to work.
- **VALIDATE**: Visual inspection — verify YAML indentation is correct. Optionally push and check GitHub Actions.

---

### Task 2: CREATE `docs/deployment-guide.md` — Production deployment walkthrough

- **IMPLEMENT**: Comprehensive guide from server setup to running application.
- **PATTERN**: Follow existing docs style (clear headers, code blocks, step-by-step).

The document should cover these sections:

```markdown
# Deployment Guide

Production deployment walkthrough for AgentForge.

---

## Prerequisites

- A server with Docker and Docker Compose installed
- A domain name pointed to the server's IP (for HTTPS)
- API keys for your LLM provider (OpenAI, Groq, or Ollama for local)
- (Optional) YouTube API key for the collector

---

## 1. Server Setup

### Install Docker

[Link to Docker's official install docs for the server OS]

### Configure Firewall

Open ports 80 (HTTP) and 443 (HTTPS) for Caddy:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp  # HTTP/3
```

### Set Up DNS

Create an A record pointing your domain to the server's IP address.
Wait for DNS propagation (can take up to 48 hours, usually minutes).

---

## 2. Application Deployment

### Clone the Repository

```bash
git clone https://github.com/your-org/agentforge.git
cd agentforge
```

### Configure Environment

```bash
cp .env.production.example .env
# Edit .env with your values:
# - DOMAIN=your-domain.com
# - OPENAI_API_KEY=sk-...
# - LANGFUSE keys (get from Langfuse dashboard after first start)
```

### Start Services

**Standalone server (bundled infrastructure):**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile bundled --profile prod up -d
```

**Shared infrastructure (Postgres/Langfuse already running):**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile prod up -d
```

### Run Database Migrations

```bash
docker compose exec app alembic upgrade head
```

---

## 3. HTTPS

Caddy handles HTTPS automatically:

- **Real domain**: When `DOMAIN` is set to a real domain (e.g., `agents.example.com`),
  Caddy automatically provisions a Let's Encrypt TLS certificate. No manual certificate
  management is needed.
- **Localhost**: When `DOMAIN` is `localhost`, Caddy serves HTTP or uses a self-signed
  certificate. No Let's Encrypt interaction occurs.
- **Certificate renewal**: Caddy renews certificates automatically, typically 30 days
  before expiry.

**Requirements for automatic HTTPS:**
- Port 80 must be accessible from the internet (for ACME HTTP-01 challenge)
- DNS must resolve to the server's IP
- `DOMAIN` must be set to the actual domain name

---

## 4. Monitoring

### Health Check

```bash
curl https://your-domain.com/health
# Returns: {"status": "healthy", "database": "healthy", "version": "0.6.0"}
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f app
docker compose logs -f frontend
docker compose logs -f caddy
```

### Langfuse Traces

If using bundled Langfuse, access the dashboard at `https://your-domain.com/langfuse/`
(if exposed via Caddy) or directly at `http://server-ip:3001`.

---

## 5. Updating

### Pull Latest Changes

```bash
git pull origin main
```

### Rebuild and Restart

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile bundled --profile prod up -d --build
```

### Rolling Restart (App Only)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --no-deps --build app
```

---

## 6. Backup

### Postgres Backup

```bash
# Create a backup
docker compose exec supabase-db pg_dump -U postgres agentforge > backup_$(date +%Y%m%d).sql

# Restore from backup
cat backup_20260317.sql | docker compose exec -T supabase-db psql -U postgres agentforge
```

### Automated Backups

Set up a cron job for daily backups:

```bash
crontab -e
# Add:
0 2 * * * cd /path/to/agentforge && docker compose exec -T supabase-db pg_dump -U postgres agentforge > /backups/agentforge_$(date +\%Y\%m\%d).sql
```

---

## Troubleshooting

### Caddy Not Getting Certificates

- Verify ports 80 and 443 are open: `sudo netstat -tlnp | grep -E ':(80|443)'`
- Check DNS resolution: `dig your-domain.com`
- View Caddy logs: `docker compose logs caddy`

### Frontend Not Loading

- Check frontend container: `docker compose logs frontend`
- Verify nginx is serving: `curl http://localhost:3000`
- Check browser console for API errors

### Database Connection Issues

- Check database health: `docker compose exec supabase-db pg_isready -U postgres`
- Verify DATABASE_URL in .env matches the running database
- Check app logs: `docker compose logs app`
```

- **VALIDATE**: Visual inspection — verify all sections are covered and commands are correct.

---

### Task 3: CREATE `docs/frontend-customization.md` — Frontend template modification guide

- **IMPLEMENT**: Guide for customizing the chat UI, adding pages, connecting new endpoints, and styling.
- **PATTERN**: Follow existing docs style.

The document should cover these sections:

```markdown
# Frontend Customization Guide

How to modify the AgentForge frontend template for your agent's needs.

The frontend is a **template, not a framework**. It provides the structure, component
library, API integration patterns, and styling foundation. Modify it freely for your
specific agent's UI needs.

---

## Project Structure

```
frontend/
├── src/
│   ├── main.tsx              # App entry point (QueryClientProvider)
│   ├── App.tsx               # Root component
│   ├── index.css             # Global styles + Tailwind + CSS variables
│   │
│   ├── components/
│   │   ├── ui/               # shadcn/ui components (auto-generated)
│   │   ├── chat/             # Chat interface components
│   │   │   ├── ChatInterface.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── SourceCard.tsx
│   │   │   └── InputBar.tsx
│   │   └── layout/           # Page layout
│   │       ├── Header.tsx
│   │       └── MainLayout.tsx
│   │
│   ├── hooks/                # React Query hooks
│   │   ├── useAgent.ts       # POST /api/ask
│   │   └── useWorkflow.ts    # POST /api/research
│   │
│   ├── lib/
│   │   ├── api.ts            # API client (fetch wrapper)
│   │   └── utils.ts          # shadcn/ui cn() utility
│   │
│   └── types/
│       └── api.ts            # TypeScript types matching backend schemas
│
├── vite.config.ts            # Vite config (plugins, dev proxy)
└── index.html                # HTML entry point
```

---

## Changing the Chat UI

### Modifying Message Display

Edit `src/components/chat/MessageBubble.tsx` to change how messages render.

### Adding New Message Types

Add new display modes to MessageBubble for different response types
(e.g., workflow results with confidence scores, memory-aware responses).

### Customizing the Input

Edit `src/components/chat/InputBar.tsx` to add features like:
- File upload button
- Voice input
- Mode switcher (agent vs. research workflow)

---

## Connecting New API Endpoints

### Step 1: Add TypeScript Types

Add interfaces to `src/types/api.ts` matching your new Pydantic schemas.

### Step 2: Add API Client Function

Add a function to `src/lib/api.ts`:

```typescript
export async function myNewEndpoint(data: MyRequest): Promise<MyResponse> {
  return request<MyResponse>("/my-endpoint", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
```

### Step 3: Create a React Query Hook

Create `src/hooks/useMyEndpoint.ts`:

```typescript
import { useMutation } from "@tanstack/react-query";
import { myNewEndpoint } from "../lib/api";
import type { MyResponse } from "../types/api";

export function useMyEndpoint() {
  return useMutation<MyResponse, Error, MyRequest>({
    mutationFn: (data) => myNewEndpoint(data),
  });
}
```

### Step 4: Use in a Component

```typescript
const mutation = useMyEndpoint();
const handleSubmit = () => mutation.mutateAsync(data);
```

---

## Styling

### Tailwind CSS

This project uses Tailwind CSS v4, which requires no configuration files.
All customization is done via CSS variables in `src/index.css`.

### shadcn/ui Theme

shadcn/ui uses CSS variables for theming. Modify the variables in `src/index.css`
to change colors, border radius, and other design tokens.

### Adding shadcn/ui Components

```bash
npx shadcn@latest add dialog dropdown-menu tabs
```

Browse available components at https://ui.shadcn.com/docs/components.

---

## Adding Pages (React Router)

The template ships as a single-page chat interface. To add multiple pages:

1. Install React Router: `npm install react-router-dom`
2. Set up routes in `App.tsx`
3. Create page components in `src/pages/`

---

## Building for Production

```bash
# Local build
npm run build

# Docker build
docker build -t agentforge-frontend .
```

The production build outputs to `dist/` and is served by nginx in the Docker container.
```

- **VALIDATE**: Visual inspection — verify all sections are covered.

---

## TESTING STRATEGY

### CI Validation

- Push to a branch and verify the GitHub Actions frontend job runs
- TypeScript check and build should pass

### Documentation Review

- All code examples are correct and copy-pasteable
- All referenced files and paths exist
- All deployment commands are tested and work

---

## VALIDATION COMMANDS

### Level 1: CI Config

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

### Level 2: Documentation Links

```bash
# Verify all referenced files exist
ls docs/deployment-guide.md docs/frontend-customization.md
```

---

## ACCEPTANCE CRITERIA

- [ ] CI pipeline includes frontend TypeScript check and build job
- [ ] CI frontend job uses Node.js 20 with npm caching
- [ ] `docs/deployment-guide.md` covers: prerequisites, server setup, deployment, HTTPS, monitoring, updating, backup
- [ ] `docs/frontend-customization.md` covers: project structure, chat UI changes, new endpoints, styling, building
- [ ] A developer can follow the deployment guide from clone to running HTTPS application
- [ ] All documentation code examples are correct and consistent with the actual codebase

---

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (Tasks 1-3)
- [ ] CI YAML is valid
- [ ] Documentation is complete and accurate
- [ ] All acceptance criteria met
- [ ] Phase 6 is complete — all PBIs (6.1, 6.2, 6.3) delivered

---

## NOTES

### What This Completes

PBI 6.3 is the final PBI of Phase 6, which is the final phase of the AgentForge MVP roadmap. After this:

| Phase | What It Added |
|-------|---------------|
| Phase 1 | Core platform — single agent with tools, data collection, observability, Docker |
| Phase 2 | Multi-agent orchestration — LangGraph, cross-agent tracing |
| Phase 3 | Memory & web intelligence — Mem0, Crawl4AI, Brave Search |
| Phase 4 | Local AI & caching — Ollama, SearXNG, Redis |
| Phase 5 | Evaluation & quality — Ragas, FastMCP, testing patterns |
| Phase 6 | Application layer — React frontend, Caddy HTTPS, production Docker |

A developer can now clone AgentForge, choose their pattern (single agent or multi-agent), build their agent logic, and deploy it as a production application with a frontend, HTTPS, and observability.
