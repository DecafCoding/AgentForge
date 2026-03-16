# Running AgentForge Fully Local

This guide covers running the entire AgentForge stack — model inference, web search, memory, and all agent capabilities — on a local machine with zero external API dependencies.

---

## Prerequisites

- **Docker** with Docker Compose v2
- **NVIDIA Container Toolkit** (optional — for GPU-accelerated inference)
  - Not required. Ollama falls back to CPU if no GPU is available.
- **Sufficient disk space** — models range from 4 GB (7B) to 60+ GB (70B)

---

## Quick Start

### 1. Start Local AI Services

```bash
docker compose --profile local-ai up -d
```

This starts:
- **Ollama** on port 11434 (local LLM serving)
- **SearXNG** on port 8080 (self-hosted web search)

### 2. Pull a Model

```bash
uv run python scripts/pull_model.py llama3.1:8b
```

This downloads the model into Ollama. First pull takes a few minutes depending on model size and connection speed.

### 3. Configure Environment

Add to your `.env` file:

```env
MODEL_PROVIDER=ollama
MODEL_NAME=llama3.1:8b
SEARCH_PROVIDER=searxng
```

### 4. Start the App

```bash
# If using bundled Postgres + Langfuse:
docker compose --profile bundled up -d

# Or start just the app (with shared infra):
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

You now have a fully local AI agent stack with no external API calls.

---

## Ollama — Local Model Serving

### How It Works

Ollama runs open-source LLMs locally. It provides an OpenAI-compatible API that Pydantic AI connects to via its Ollama provider. Switching from a cloud provider to Ollama requires changing two env vars — zero code changes.

### Recommended Models

| Model | Size | Use Case |
|-------|------|----------|
| `llama3.1:8b` | ~4.7 GB | Good balance of speed and quality. Best starting point. |
| `qwen2.5:7b` | ~4.4 GB | Strong reasoning, good for structured output. |
| `qwen2.5:32b` | ~19 GB | Higher quality, needs more RAM/VRAM. |
| `mistral:7b` | ~4.1 GB | Fast, good for simple tasks. |
| `llama3.1:70b` | ~39 GB | Best quality, needs significant GPU memory. |

### Pulling Models

```bash
# Default (llama3.1:8b)
uv run python scripts/pull_model.py

# Specific model
uv run python scripts/pull_model.py qwen2.5:32b

# List pulled models
curl http://localhost:11434/api/tags
```

### CPU vs GPU

- **With GPU**: Ollama uses NVIDIA GPUs via CUDA. Inference is 10-50x faster.
- **Without GPU**: Ollama falls back to CPU. Usable for small models (7B), slow for larger ones.
- The Docker Compose GPU config is optional — if the NVIDIA driver isn't installed, Ollama starts in CPU-only mode.

### Structured Output

Some models produce better structured JSON output than others. If your agent uses `result_type` (Pydantic models), prefer:
- `llama3.1:8b` or larger — reliable structured output
- `qwen2.5` family — strong at following output schemas

If a model produces malformed JSON, try a larger model or one specifically trained for instruction following.

---

## SearXNG — Self-Hosted Web Search

### How It Works

SearXNG is a meta-search engine that aggregates results from multiple search engines (Google, DuckDuckGo, Wikipedia, etc.) without requiring API keys. AgentForge's `web_search` tool routes to SearXNG when `SEARCH_PROVIDER=searxng`.

### Configuration

SearXNG is configured via `config/searxng/settings.yml`. The default config enables:
- JSON API format (required for programmatic access)
- All default search engines

To customise which engines are used, edit `settings.yml`:

```yaml
use_default_settings: true
server:
  secret_key: "your-secret-key"
  bind_address: "0.0.0.0"
search:
  formats:
    - html
    - json
```

### Switching Between Search Providers

```env
# Use Brave Search (cloud API — requires API key)
SEARCH_PROVIDER=brave

# Use SearXNG (self-hosted — no API key needed)
SEARCH_PROVIDER=searxng
```

The agent's `web_search` tool works identically with either provider.

### Troubleshooting

**SearXNG returns HTML instead of JSON:**
Ensure `json` is listed under `search.formats` in `config/searxng/settings.yml`.

**No search results:**
Some upstream engines may rate-limit SearXNG. Wait a few minutes and retry, or add more engines in `settings.yml`.

---

## Full Local Stack

With `--profile bundled` and `--profile local-ai`, the complete stack includes:

| Service | Port | Purpose |
|---------|------|---------|
| Postgres + pgvector | 5432 | Database |
| Langfuse | 3001 | Observability |
| Ollama | 11434 | Local LLM |
| SearXNG | 8080 | Web search |
| App | 8000 | AgentForge API |

```bash
# Start everything
docker compose --profile bundled --profile local-ai up -d

# Pull a model
uv run python scripts/pull_model.py llama3.1:8b
```

Set in `.env`:
```env
MODEL_PROVIDER=ollama
MODEL_NAME=llama3.1:8b
SEARCH_PROVIDER=searxng
```

No external API keys needed. All data stays on your machine.

---

## Troubleshooting

### Ollama container won't start (GPU error)

If you see an error about NVIDIA devices, your system either doesn't have an NVIDIA GPU or the NVIDIA Container Toolkit isn't installed. Ollama will work without GPU — remove the `deploy.resources` section from `docker-compose.yml` for the Ollama service, or simply ignore the error as Ollama will fall back to CPU.

### Model pulls fail

Ensure the Ollama container is running and accessible:

```bash
curl http://localhost:11434/api/tags
```

If this returns an error, check `docker compose logs ollama`.

### Agent responses are slow

Local models on CPU are significantly slower than cloud APIs. Options:
- Use a smaller model (`llama3.1:8b` instead of `70b`)
- Add a GPU (even a consumer GPU dramatically improves speed)
- Use Ollama for development, cloud providers for production
