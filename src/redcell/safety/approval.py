"""Operator approval policies (Faz 8).

Faz 0 baked a raw `input()` prompt into the ScopeGuard. That is impossible to
test, impossible to automate, and it collides with the live `--ui` dashboard.
This module lifts the decision out into a small, pluggable `ApprovalPolicy` so
the guard asks a policy object "may this in-scope action run?" and the CLI, the
benchmark harness, or a future UI can each supply their own.

Every policy answers one question: `decide(target, action) -> bool`.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable


@runtime_checkable
class ApprovalPolicy(Protocol):
    def decide(self, target: str, action: str) -> bool:
        """Return True to allow the action on the target, False to decline."""
        ...


class AutoApproval:
    """Non-interactive policy: always allow (or always deny). Used by the
    benchmark harness and by `redcell run --yes`."""

    def __init__(self, allow: bool = True):
        self.allow = allow

    def decide(self, target: str, action: str) -> bool:
        return self.allow


class CallbackApproval:
    """Wrap any callable `(target, action) -> bool` as a policy — the seam a
    dashboard or remote approver plugs into."""

    def __init__(self, fn: Callable[[str, str], bool]):
        self._fn = fn

    def decide(self, target: str, action: str) -> bool:
        return bool(self._fn(target, action))


class CliApproval:
    """Interactive policy: ask once per action on stdin. The default when a run
    requires approval and nothing else is supplied."""

    def __init__(self, prompt: Callable[[str], str] = input):
        self._prompt = prompt

    def decide(self, target: str, action: str) -> bool:
        reply = self._prompt(f"[approval] run '{action}' on '{target}'? [y/N] ").strip().lower()
        return reply in {"y", "yes"}
