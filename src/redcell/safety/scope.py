"""Scope enforcement + human approval gate.

This is the most important module in the framework. Every tool that could
touch a target routes its arguments through `ScopeGuard` BEFORE execution.
Nothing outside the authorized scope runs — full stop.

scope.yaml format:
    name: "Acme external assessment 2026"
    authorization_ref: "SOW-2026-0042"     # your paperwork reference
    allow:
      hosts: ["10.0.5.0/24", "app.acme-test.example"]
      domains: ["acme-test.example"]
    deny:
      hosts: ["10.0.5.1"]                   # e.g. gateway you must not touch
"""
from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .approval import ApprovalPolicy
from urllib.parse import urlparse


def host_of(target: str) -> str:
    """Extract the bare host from a target that may carry a scheme/port/path.

    'http://127.0.0.1:11434/foo' -> '127.0.0.1'
    'app.test.example:8443'      -> 'app.test.example'
    '10.0.5.42'                  -> '10.0.5.42'
    Scope matching is always done on this normalized host, so the model can
    hand a tool a full URL and the gate still decides on the host alone.
    """
    t = (target or "").strip()
    if not t:
        return ""
    if "://" not in t:
        t = "//" + t  # let urlparse treat the whole thing as a netloc
    return urlparse(t).hostname or ""

import yaml  # PyYAML; add to deps if you keep YAML scopes


class ScopeError(Exception):
    """Raised when an action targets something outside the authorized scope."""


@dataclass
class Scope:
    name: str
    authorization_ref: str
    allow_hosts: list[str] = field(default_factory=list)
    allow_domains: list[str] = field(default_factory=list)
    deny_hosts: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "Scope":
        p = Path(path)
        if not p.exists():
            raise ScopeError(
                f"No scope file at {p}. Refusing to run without a defined, "
                "authorized scope. Create one with `redcell scope init`."
            )
        data = yaml.safe_load(p.read_text()) or {}
        if not data.get("authorization_ref"):
            raise ScopeError("scope.yaml must include an 'authorization_ref' (your written authorization).")
        allow = data.get("allow", {})
        deny = data.get("deny", {})
        return cls(
            name=data.get("name", "unnamed"),
            authorization_ref=data["authorization_ref"],
            allow_hosts=allow.get("hosts", []),
            allow_domains=allow.get("domains", []),
            deny_hosts=deny.get("hosts", []),
        )

    def permits(self, target: str) -> bool:
        """True only if `target` (host/IP/domain) is inside scope and not denied.

        The target is normalized to its bare host first, so a scheme or port
        (e.g. 'http://host:8443/path') is matched on 'host'.
        """
        target = host_of(target)
        if self._matches_any(target, self.deny_hosts):
            return False
        if self._host_in(target, self.allow_hosts):
            return True
        return self._domain_in(target, self.allow_domains)

    # --- matching helpers ----------------------------------------------------
    @staticmethod
    def _as_ip(value: str) -> ipaddress._BaseAddress | None:
        try:
            return ipaddress.ip_address(value)
        except ValueError:
            return None

    def _host_in(self, target: str, patterns: list[str]) -> bool:
        ip = self._as_ip(target)
        for pat in patterns:
            if "/" in pat and ip is not None:
                if ip in ipaddress.ip_network(pat, strict=False):
                    return True
            elif pat == target:
                return True
        return False

    @staticmethod
    def _domain_in(target: str, domains: list[str]) -> bool:
        return any(target == d or target.endswith("." + d) for d in domains)

    def _matches_any(self, target: str, patterns: list[str]) -> bool:
        return self._host_in(target, patterns)


@dataclass
class AuditEntry:
    """One scope-gate decision, kept for the run's audit trail (Faz 8)."""

    target: str
    action: str
    allowed: bool
    reason: str   # "allowed" | "blocked:out-of-scope" | "blocked:dry-run" | "blocked:declined"
    at: float = field(default_factory=time.time)


class ScopeGuard:
    """Wraps a Scope with the approval/dry-run policy and does the gating.

    Faz 8: the approval decision is delegated to a pluggable ApprovalPolicy, and
    every decision (allowed or blocked) is appended to `self.audit`. The
    constructor stays backward compatible — pass only `require_approval`/`dry_run`
    and it builds the interactive CLI policy on demand.
    """

    def __init__(
        self,
        scope: Scope,
        require_approval: bool,
        dry_run: bool,
        approval: ApprovalPolicy | None = None,
    ):
        self.scope = scope
        self.require_approval = require_approval
        self.dry_run = dry_run
        self.approval = approval
        self.audit: list[AuditEntry] = []

    def check(self, target: str, action: str) -> None:
        """Raise ScopeError unless `action` on `target` is allowed. Blocking."""
        if not self.scope.permits(target):
            self._record(target, action, False, "blocked:out-of-scope")
            raise ScopeError(
                f"BLOCKED: '{target}' is not in authorized scope "
                f"'{self.scope.name}' ({self.scope.authorization_ref})."
            )
        if self.dry_run:
            self._record(target, action, False, "blocked:dry-run")
            raise ScopeError(f"DRY-RUN: would run '{action}' on '{target}' (nothing executed).")
        if self.require_approval and not self._approve(target, action):
            self._record(target, action, False, "blocked:declined")
            raise ScopeError(f"Operator declined '{action}' on '{target}'.")
        self._record(target, action, True, "allowed")

    def _approve(self, target: str, action: str) -> bool:
        # Lazily build the interactive policy so existing callers that never set
        # one keep the original CLI-prompt behavior.
        if self.approval is None:
            from .approval import CliApproval

            self.approval = CliApproval()
        return self.approval.decide(target, action)

    def _record(self, target: str, action: str, allowed: bool, reason: str) -> None:
        self.audit.append(AuditEntry(target=target, action=action, allowed=allowed, reason=reason))

    def audit_summary(self) -> dict[str, int]:
        """Counts by disposition, for an end-of-run line."""
        out: dict[str, int] = {}
        for e in self.audit:
            out[e.reason] = out.get(e.reason, 0) + 1
        return out
