"""Benchmark runner (Faz 5).

Runs one scenario through the real Orchestrator and scores the outcome against
its expectations. Provider and registry are injectable, so the harness is
deterministic in tests (fake provider) and real in the CLI (build_provider).

Metrics collected from the on_event stream + findings store:
  findings   - number of findings recorded
  tools_used - set of tools the agents invoked
  hosts      - hosts any finding was about (via host_from_data)
  blocked    - scope-guard blocks (a non-zero count can be expected or a bug)
  stages     - how many orchestration stages ran
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..agents.orchestrator import Orchestrator
from ..config import Settings
from ..llm.base import LLMProvider
from ..safety.scope import Scope, ScopeGuard
from ..state import host_from_data
from ..state.store import FindingStore
from ..tools.base import ToolRegistry
from ..tools.builtins import default_registry
from .scenario import Scenario


@dataclass
class BenchResult:
    name: str
    passed: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class _Collector:
    def __init__(self) -> None:
        self.tools: set[str] = set()
        self.blocked = 0
        self.stages = 0

    def on_event(self, event: str, payload: dict) -> None:
        if event == "act":
            self.tools.add(payload.get("tool", ""))
        elif event == "blocked":
            self.blocked += 1
        elif event == "stage":
            self.stages += 1


def _scope_from(d: dict[str, Any]) -> Scope:
    allow = d.get("allow", {}) or {}
    deny = d.get("deny", {}) or {}
    return Scope(
        name=d.get("name", "bench"),
        authorization_ref=d.get("authorization_ref", "BENCH"),
        allow_hosts=allow.get("hosts", []),
        allow_domains=allow.get("domains", []),
        deny_hosts=deny.get("hosts", []),
    )


def run_scenario(
    scenario: Scenario,
    provider: LLMProvider,
    registry: ToolRegistry | None = None,
    max_steps: int = 6,
    require_approval: bool = False,
    dry_run: bool = False,
) -> BenchResult:
    guard = ScopeGuard(_scope_from(scenario.scope), require_approval=require_approval, dry_run=dry_run)
    registry = registry or default_registry()

    with tempfile.TemporaryDirectory() as tmp:
        store = FindingStore(Path(tmp) / "bench.db")
        collector = _Collector()
        orch = Orchestrator(
            Settings(max_steps=max_steps), provider, registry, guard, store, collector.on_event
        )
        orch.run(scenario.objective)
        findings = store.list_findings()
        hosts = sorted({h for f in findings if (h := host_from_data(f.data))})
        store.close()

    metrics = {
        "findings": len(findings),
        "tools_used": sorted(collector.tools - {""}),
        "hosts": hosts,
        "blocked": collector.blocked,
        "stages": collector.stages,
    }

    exp = scenario.expect
    reasons: list[str] = []
    if len(findings) < exp.min_findings:
        reasons.append(f"findings {len(findings)} < expected min {exp.min_findings}")
    for t in exp.tools_used:
        if t not in collector.tools:
            reasons.append(f"expected tool '{t}' was not used")
    for h in exp.hosts_touched:
        if h not in hosts:
            reasons.append(f"expected host '{h}' not touched")
    if exp.max_blocked is not None and collector.blocked > exp.max_blocked:
        reasons.append(f"blocked {collector.blocked} > allowed {exp.max_blocked}")

    return BenchResult(name=scenario.name, passed=not reasons, reasons=reasons, metrics=metrics)
