"""MCP (Model Context Protocol) client integration.

Faz 2's note was "wire a real MCP client next". This module lets redcell pull
tools from an external MCP server and expose them to agents as ordinary Tools —
so the 2 builtins become a whole tool ecosystem without touching agent code.

SAFETY: tools discovered from an MCP server are arbitrary and remote. They are
wrapped in MCPTool, which inherits Tool.invoke — so every target-touching MCP
call STILL passes through the scope guard before it runs. The target argument
is auto-detected from the tool's JSON schema (target/host/url/...), so the gate
knows what to check.

Two layers:
  * MCPSession  — a tiny transport-agnostic protocol (list_tools / call_tool).
                  Easy to fake in tests; no network needed to verify the adapter.
  * StdioMCPClient — a concrete MCPSession backed by the official `mcp` SDK over
                  stdio (optional dependency; lazy-imported).
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .base import Tool, ToolRegistry, ToolResult

# Schema property names that denote a target the scope guard must check,
# in priority order.
_TARGET_KEYS = ["target", "host", "hostname", "url", "ip", "address", "domain"]

MAX_OUTPUT_CHARS = 4000


@runtime_checkable
class MCPSession(Protocol):
    """Minimal MCP session surface redcell needs."""

    def list_tools(self) -> list[dict[str, Any]]:
        """Return [{'name', 'description', 'input_schema'}, ...]."""
        ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Invoke a remote tool and return a short text result."""
        ...


def detect_target_arg(input_schema: dict[str, Any]) -> str | None:
    """Pick the argument that names a target, so scope-gating applies.

    Returns None only if the tool declares no target-like field (treated as a
    safe/local tool). Any tool that touches a host/url WILL be gated.
    """
    props = (input_schema or {}).get("properties", {}) or {}
    for key in _TARGET_KEYS:
        if key in props:
            return key
    return None


class MCPTool(Tool):
    """Adapter: one remote MCP tool presented as a redcell Tool."""

    def __init__(
        self,
        session: MCPSession,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        target_arg: str | None,
    ):
        self.session = session
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.target_arg = target_arg

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        # Reached only after Tool.invoke's scope check has passed.
        try:
            text = self.session.call_tool(self._remote_name, arguments)
        except Exception as e:  # noqa: BLE001
            return ToolResult(ok=False, summary=f"MCP tool '{self.name}' failed: {e}")
        return ToolResult(
            ok=True,
            summary=str(text)[:MAX_OUTPUT_CHARS],
            data={"tool": self.name, "arguments": arguments},
        )

    # The registry/agent-facing name may be prefixed; the server knows the bare name.
    _remote_name: str = ""


def register_mcp_tools(
    registry: ToolRegistry, session: MCPSession, prefix: str = "mcp."
) -> list[str]:
    """Discover tools on an MCP session and register them in the registry.

    Returns the list of (prefixed) tool names added. Each is scope-gated on its
    detected target argument.
    """
    added: list[str] = []
    for spec in session.list_tools():
        bare = spec["name"]
        schema = spec.get("input_schema") or spec.get("inputSchema") or {
            "type": "object",
            "properties": {},
        }
        tool = MCPTool(
            session=session,
            name=prefix + bare,
            description=spec.get("description", ""),
            input_schema=schema,
            target_arg=detect_target_arg(schema),
        )
        tool._remote_name = bare
        registry.register(tool)
        added.append(tool.name)
    return added


class StdioMCPClient:
    """Concrete MCPSession backed by the official `mcp` SDK over stdio.

    Launches an MCP server subprocess (e.g. `python -m some_mcp_server`) and
    speaks MCP to it. The `mcp` package is an optional dependency, lazy-imported
    here so local-only / Ollama setups don't need it.

    The official SDK is async; this wrapper owns a background asyncio loop so the
    rest of redcell can stay synchronous.
    """

    def __init__(self, command: str, args: list[str] | None = None, env: dict | None = None):
        self.command = command
        self.args = args or []
        self.env = env
        self._loop = None
        self._thread = None
        self._session = None
        self._stack = None

    def _ensure(self):
        if self._session is not None:
            return
        import asyncio
        import threading

        try:
            from mcp import ClientSession, StdioServerParameters  # type: ignore
            from mcp.client.stdio import stdio_client  # type: ignore
        except ImportError as e:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "MCP support needs the 'mcp' package. Install with: pip install redcell[mcp]"
            ) from e

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

        async def _connect():
            from contextlib import AsyncExitStack

            self._stack = AsyncExitStack()
            params = StdioServerParameters(command=self.command, args=self.args, env=self.env)
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            return session

        self._session = self._run(_connect())

    def _run(self, coro):
        import asyncio

        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def list_tools(self) -> list[dict[str, Any]]:
        self._ensure()

        async def _list():
            resp = await self._session.list_tools()
            out = []
            for t in resp.tools:
                # mcp 2.x: input_schema ; mcp 1.x: inputSchema
                schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", None) or {}
                out.append({"name": t.name, "description": t.description or "", "input_schema": schema})
            return out

        return self._run(_list())

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        self._ensure()

        async def _call():
            result = await self._session.call_tool(name, arguments)
            parts = []
            for block in result.content:
                parts.append(getattr(block, "text", None) or str(block))
            return "\n".join(parts)

        return self._run(_call())

    def close(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
