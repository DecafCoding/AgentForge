# MCP Integration Guide

*AgentForge — Connecting MCP Clients to Agent Tools*

---

## What MCP Enables

The Model Context Protocol (MCP) is a standard for exposing tool capabilities to AI systems. By wrapping AgentForge agent tools as MCP tools, any MCP-compatible client — Claude Desktop, Cursor, VS Code Copilot, or custom applications — can invoke AgentForge's capabilities without knowing the FastAPI endpoint or implementation details. The client discovers available tools, their parameters, and their descriptions through the MCP protocol.

---

## Available Tools

| Tool | Description | Returns |
|------|-------------|---------|
| `ask_agent` | Ask the YouTube research agent a question | Answer string |
| `search_videos` | Full-text video database search | List of video dicts |
| `get_channel_summary` | Channel stats (video count, views, latest upload) | Stats dict or error string |
| `run_research_workflow` | Multi-agent research → analysis → synthesis | Synthesised answer string |

All tools are **read-only** — no data mutation or admin operations are exposed.

---

## Running the Server

```bash
# stdio (for Claude Desktop and local clients — default):
uv run python scripts/mcp_server.py

# HTTP (for remote clients):
uv run python scripts/mcp_server.py --transport http --port 8001

# Via environment variables:
MCP_TRANSPORT=http MCP_PORT=8001 uv run python scripts/mcp_server.py
```

Environment variables `MCP_TRANSPORT` (default: `stdio`) and `MCP_PORT` (default: `8001`) are configured in `.env`. CLI flags override env vars.

---

## Claude Desktop Configuration

### macOS

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agentforge": {
      "command": "uv",
      "args": ["run", "python", "scripts/mcp_server.py"],
      "cwd": "/absolute/path/to/agentforge"
    }
  }
}
```

### Windows

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agentforge": {
      "command": "uv",
      "args": ["run", "python", "scripts/mcp_server.py"],
      "cwd": "C:\\path\\to\\agentforge"
    }
  }
}
```

Restart Claude Desktop after editing. The AgentForge server should appear in the tools panel. You can then ask Claude to use the `ask_agent`, `search_videos`, `get_channel_summary`, or `run_research_workflow` tools.

---

## Mounting into FastAPI (Optional)

For teams that prefer a single process serving both REST and MCP:

```python
# In src/api/main.py, after create_app():
from src.mcp.server import mcp

app.mount("/mcp", mcp.http_app(path="/"))
```

Note: the MCP server's own lifespan (DB pool) is independent of the FastAPI lifespan — both run their own pool lifecycle. See the FastMCP documentation on `combine_lifespans()` if pool sharing is needed.

---

## Testing MCP Connectivity

```bash
# Verify the server starts and responds (HTTP transport):
uv run python scripts/mcp_server.py --transport http &
curl http://localhost:8001/

# Verify --help works:
uv run python scripts/mcp_server.py --help

# Run the MCP server tests:
uv run pytest tests/test_mcp_server.py -v
```

For stdio transport, use an MCP inspector tool or Claude Desktop to verify connectivity.

---

## Security Guidance

- The MCP server exposes **read-only tools only** — no data mutation, no admin operations.
- **stdio transport** (default) is local-only — safe for personal use without authentication.
- **HTTP transport** exposes the server on the network. Add a reverse proxy with authentication (e.g., Caddy with basic auth) before exposing publicly.
- Never expose mutation tools (`upsert_*`, `delete_*`) via MCP.
- The server creates its own database pool via lifespan — it does not share credentials with the FastAPI app unless explicitly configured.
