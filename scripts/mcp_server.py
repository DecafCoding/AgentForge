"""Start the AgentForge MCP server as a standalone process.

Supports both stdio transport (for local MCP clients like Claude Desktop)
and HTTP transport (for remote clients).

Usage:
    # stdio — for Claude Desktop and local MCP clients (default):
    uv run python scripts/mcp_server.py

    # HTTP — for remote clients and browser-based MCP clients:
    uv run python scripts/mcp_server.py --transport http

Claude Desktop configuration (~/.config/claude/claude_desktop_config.json
or %APPDATA%/Claude/claude_desktop_config.json on Windows):

    {
      "mcpServers": {
        "agentforge": {
          "command": "uv",
          "args": ["run", "python", "scripts/mcp_server.py"],
          "cwd": "/absolute/path/to/agentforge"
        }
      }
    }
"""

import argparse
import logging

logging.basicConfig(level=logging.INFO)


def main() -> None:
    """Parse transport args and start the MCP server."""
    parser = argparse.ArgumentParser(description="Start the AgentForge MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=None,
        help="Transport protocol (default: MCP_TRANSPORT env var, falls back to stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for HTTP transport (default: MCP_PORT env var, falls back to 8001)",
    )
    args = parser.parse_args()

    from src.config import MCP_PORT, MCP_TRANSPORT
    from src.mcp.server import mcp

    transport = args.transport or MCP_TRANSPORT
    port = args.port or MCP_PORT

    if transport == "http":
        mcp.run(transport="http", port=port)
    else:
        mcp.run()  # stdio is FastMCP's default


if __name__ == "__main__":
    main()
