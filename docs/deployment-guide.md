# Deployment Guide

Production deployment walkthrough for AgentForge — from a bare server to a running, HTTPS-enabled application.

---

## Prerequisites

- A server running Linux with Docker and Docker Compose v2 installed
- A domain name with an A record pointed at the server's IP address (required for HTTPS)
- API keys for your LLM provider (OpenAI, Groq, or a local Ollama setup)
- (Optional) YouTube Data API v3 key if using the collector

---

## 1. Server Setup

### Install Docker

Follow Docker's official installation guide for your Linux distribution:
https://docs.docker.com/engine/install/

Verify installation:

```bash
docker --version
docker compose version
```

### Configure Firewall

Open ports 80 and 443 for Caddy. Port 443/udp enables HTTP/3 (QUIC):

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw reload
```

### Set Up DNS

Create an A record pointing your domain to the server's public IP address. DNS propagation typically takes a few minutes but can take up to 48 hours.

Verify resolution before deploying:

```bash
dig your-domain.com +short
# Should return the server's IP address
```

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
```

Edit `.env` and fill in your values. At minimum:

```env
DOMAIN=your-domain.com
OPENAI_API_KEY=sk-...
CORS_ORIGINS=https://your-domain.com
```

For Langfuse keys: start the stack once (Step 3), open the Langfuse UI, create an account, and copy the keys back into `.env`.

### Start Services

**Standalone server (bundled Postgres, Langfuse, and Caddy):**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile bundled --profile prod up -d
```

**Shared infrastructure (Postgres and Langfuse already running elsewhere):**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile prod up -d
```

### Run Database Migrations

After services start, apply Alembic migrations:

```bash
docker compose exec app alembic upgrade head
```

---

## 3. HTTPS

Caddy manages TLS certificates automatically — no manual configuration required.

**How it works:**

- When `DOMAIN` is set to a real domain (e.g., `agents.example.com`), Caddy provisions a Let's Encrypt certificate via the ACME HTTP-01 challenge on port 80.
- When `DOMAIN` is `localhost`, Caddy serves HTTP or generates a locally-trusted certificate. No Let's Encrypt interaction occurs.
- Certificates are stored in the `caddy-data` Docker volume and renewed automatically ~30 days before expiry.

**Requirements for automatic HTTPS:**

- Port 80 must be reachable from the internet (for the ACME challenge)
- DNS must resolve to the server's IP before starting Caddy
- `DOMAIN` must match the DNS record exactly

**Verify HTTPS is working:**

```bash
curl https://your-domain.com/health
# Expected: {"status": "healthy", "database": "healthy", "version": "0.6.0"}
```

---

## 4. Monitoring

### Health Check

```bash
curl https://your-domain.com/health
```

### Service Status

```bash
docker compose ps
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

Log rotation is configured in `docker-compose.prod.yml` (10 MB max, 3 files).

### Langfuse Traces

When running bundled Langfuse, access the observability dashboard at `http://server-ip:3001` (direct port access) or via the Caddy-proxied path at `https://your-domain.com/langfuse/` if you expose it.

---

## 5. Updating

### Pull Latest Changes

```bash
git pull origin main
```

### Rebuild and Restart All Services

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile bundled --profile prod up -d --build
```

### Rebuild a Single Service (Zero Downtime)

```bash
# Rebuild and restart only the app container
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --no-deps --build app
```

### Apply New Migrations

After updating, always run migrations if the release includes schema changes:

```bash
docker compose exec app alembic upgrade head
```

---

## 6. Backup

### Manual Postgres Backup

```bash
# Create a timestamped backup
docker compose exec supabase-db pg_dump -U postgres agentforge \
  > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore from Backup

```bash
cat backup_20260317_020000.sql | \
  docker compose exec -T supabase-db psql -U postgres agentforge
```

### Automated Daily Backups

Set up a cron job on the server:

```bash
crontab -e
```

Add this line (adjust the path and backup directory):

```
0 2 * * * cd /opt/agentforge && docker compose exec -T supabase-db pg_dump -U postgres agentforge > /backups/agentforge_$(date +\%Y\%m\%d).sql
```

---

## Troubleshooting

### Caddy Not Provisioning a Certificate

- Verify ports 80 and 443 are open and reachable from the internet
- Check DNS resolves to the server: `dig your-domain.com +short`
- Confirm `DOMAIN` in `.env` matches your DNS record exactly
- View Caddy logs: `docker compose logs caddy`

### Frontend Not Loading

- Check the frontend container: `docker compose logs frontend`
- Verify nginx is running: `curl http://localhost:3000`
- Open browser developer tools and check the console for API errors
- Confirm `CORS_ORIGINS` in `.env` includes your domain

### Database Connection Issues

- Check the database is healthy: `docker compose exec supabase-db pg_isready -U postgres`
- Verify `DATABASE_URL` in `.env` matches the running database service name
- Check app logs: `docker compose logs app`
- Confirm migrations have run: `docker compose exec app alembic current`

### App Fails to Start

- Check app logs: `docker compose logs app`
- Verify all required env vars are set in `.env`
- Confirm the database service is healthy before the app starts
