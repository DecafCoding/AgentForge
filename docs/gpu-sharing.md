# Ollama GPU Sharing on Dedicated Servers

This guide covers running Ollama as shared infrastructure on a dedicated server where multiple AgentForge projects (or other applications) share a single GPU.

---

## The Problem

When multiple projects each run their own Ollama instance, they fight over GPU memory. Two Ollama containers trying to load models simultaneously will crash or fall back to CPU. This defeats the purpose of having a GPU.

---

## The Solution: One Shared Ollama Instance

Run a single Ollama instance on the server. All projects connect to it via the `OLLAMA_HOST` env var. This follows the same shared infrastructure pattern used for Postgres and Langfuse.

```
┌─────────────────────────────────────────┐
│  Dedicated Server                        │
│                                          │
│  ┌──────────┐  ┌──────────┐             │
│  │ Project A │  │ Project B │             │
│  │ OLLAMA_HOST=http://localhost:11434    │
│  └─────┬─────┘  └─────┬─────┘           │
│        │               │                 │
│        └───────┬───────┘                 │
│                │                         │
│        ┌───────▼───────┐                 │
│        │    Ollama      │  ← GPU         │
│        │  (one instance)│                │
│        └───────────────┘                 │
└─────────────────────────────────────────┘
```

---

## Setup

### Option 1: Install Ollama on the Host (Recommended)

Install Ollama directly on the server OS, not in Docker. This gives the best GPU access and simplest management.

```bash
# Install Ollama (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Start the service
systemctl start ollama

# Pull models
ollama pull llama3.1:8b
ollama pull qwen2.5:32b
```

Each project sets:
```env
OLLAMA_HOST=http://localhost:11434
MODEL_PROVIDER=ollama
MODEL_NAME=llama3.1:8b
```

### Option 2: Single Docker Container

If you prefer Docker, run one Ollama container outside of any project's Docker Compose:

```bash
docker run -d \
  --name ollama \
  --gpus all \
  -p 11434:11434 \
  -v ollama-data:/root/.ollama \
  --restart unless-stopped \
  ollama/ollama
```

Each project removes the Ollama service from their `docker-compose.yml` and sets `OLLAMA_HOST` to point at this shared container.

---

## Per-Project Configuration

When using shared Ollama, each project's `docker-compose.yml` should NOT include the Ollama service. Instead, use the shared infrastructure pattern:

```env
# .env — point at the shared Ollama instance
OLLAMA_HOST=http://localhost:11434
MODEL_PROVIDER=ollama
MODEL_NAME=llama3.1:8b
```

Start the project without the `local-ai` profile:
```bash
docker compose up  # No --profile local-ai
```

---

## GPU Memory Management

Ollama manages model loading and unloading automatically:

- **Loading**: When a request arrives for a model, Ollama loads it into GPU memory.
- **Unloading**: Idle models are unloaded after a timeout (default: 5 minutes).
- **Concurrent requests**: Ollama queues requests if GPU memory is full. It does not crash — it waits for memory to free up.

### Best Practices

1. **Use the same model across projects** when possible. Ollama keeps one copy in memory regardless of how many clients are connected.
2. **Avoid loading very large models** (70B+) if multiple projects need concurrent access. Smaller models (7B–13B) are more practical for shared servers.
3. **Monitor GPU usage** with `nvidia-smi`:

```bash
# Real-time GPU memory monitoring
watch -n 1 nvidia-smi

# Check which models Ollama has loaded
curl http://localhost:11434/api/ps
```

### Memory Estimates

| Model Size | GPU Memory Required |
|-----------|-------------------|
| 7B        | ~4–5 GB           |
| 13B       | ~8–10 GB          |
| 32B       | ~18–22 GB         |
| 70B       | ~38–42 GB         |

A consumer GPU (RTX 3090/4090 with 24 GB VRAM) comfortably runs 7B–13B models. A 32B model fits but leaves little room for concurrent requests.

---

## Troubleshooting

### "Out of memory" errors

Too many models loaded simultaneously. Reduce the number of projects using different models, or switch to smaller models.

### Slow inference with multiple projects

Ollama serialises requests to the same model. If one project sends a long request, others queue behind it. This is expected behaviour — not a bug.

### GPU not detected in Docker

Ensure the NVIDIA Container Toolkit is installed:

```bash
# Test GPU access in Docker
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

If this fails, install the toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
