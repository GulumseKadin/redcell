"""Tool abstraction + registry.

A Tool is the only way an agent affects the world. Each tool declares a
JSON schema (so the model knows how to call it) and runs through the scope
guard. Keep tools thin: wrap a real binary or API, parse its output, and
return a short, token-budgeted summary — never dump raw megabytes into the
model's context.

This mirrors the MCP tool model, so swapping these for a real MCP client
(e.g. a HexStrike-style server) later is a drop-in change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..llm.base import ToolSpec
from ..safety.scope import ScopeGuard


@dataclass
class ToolResult:
    ok: bool
    summary: str                 # short, model-facing text (keep it tight)
    data: dict[str, Any] | None = None   # structured output for the state store


class Tool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]

    #: JSON key in the arguments that names the target to scope-check.
    #: None means the tool touches no target (safe/local only).
    target_arg: str | None = "target"

    def spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, input_schema=self.input_schema)

    def invoke(self, arguments: dict[str, Any], guard: ScopeGuard) -> ToolResult:
        if self.target_arg is not None:
            target = str(arguments.get(self.target_arg, "")).strip()
            if not target:
                return ToolResult(ok=False, summary=f"Missing '{self.target_arg}' argument.")
            guard.check(target=target, action=self.name)  # raises ScopeError if blocked
        return self.run(arguments)

    @abstractmethod
    def run(self, arguments: dict[str, Any]) -> ToolResult:
        """Do the work. Only reached after the scope check passes."""
        raise NotImplementedError


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self) -> list[ToolSpec]:
        return [t.spec() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)
