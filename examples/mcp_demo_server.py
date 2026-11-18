"""A tiny example MCP server for redcell demos.

Exposes one tool, `web_probe`, over stdio using the official MCP SDK's FastMCP.
redcell discovers it via --mcp and scope-gates it on the `url` argument.

Run indirectly:
    redcell run --mcp "python /abs/path/examples/mcp_demo_server.py" "..."
"""
from __future__ import annotations

import httpx

try:  # mcp >= 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

server = _Server("redcell-demo-tools")


@server.tool()
def web_probe(url: str) -> str:
    """Fetch HTTP status and response headers for a URL."""
    r = httpx.get(url, follow_redirects=True, timeout=15.0)
    headers = "\n".join(f"{k}: {v}" for k, v in r.headers.items())
    return f"HTTP {r.status_code} for {url}\n{headers}"


if __name__ == "__main__":
    server.run()
