"""Shared-state interface.

Agents only ever call `add_finding` / `list_findings` (+ `close`). Anything that
implements this Store protocol can back the shared state — SQLite (default) or
a Neo4j graph (Faz 4) — without agents noticing. The `Finding` record is the
common currency returned by both.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class Finding:
    id: int
    agent: str
    tool: str
    summary: str
    data: dict[str, Any]
    created_at: float


# Argument keys (in a finding's data / tool arguments) that name a host/target.
# Used by graph stores to link a Finding to the Host it is about.
_TARGET_KEYS = ["target", "host", "hostname", "url", "ip", "address", "domain"]


def host_from_data(data: dict[str, Any]) -> str | None:
    """Best-effort extraction of the host a finding is about, for graph edges."""
    from ..safety.scope import host_of

    if not isinstance(data, dict):
        return None
    candidates = dict(data)
    args = data.get("arguments")
    if isinstance(args, dict):
        candidates = {**args, **candidates}
    for key in _TARGET_KEYS:
        val = candidates.get(key)
        if isinstance(val, str) and val.strip():
            host = host_of(val)
            if host:
                return host
    return None


@runtime_checkable
class Store(Protocol):
    def add_finding(self, agent: str, tool: str, data: dict[str, Any], summary: str) -> int: ...
    def list_findings(self, agent: str | None = None) -> list[Finding]: ...
    def close(self) -> None: ...
