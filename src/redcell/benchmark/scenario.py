"""Benchmark scenarios (Faz 5).

A scenario is a reproducible task + the scope it runs in + what a good run is
expected to produce. The harness runs the real orchestrator and checks the
outcome against these expectations — so you can track whether changes to
prompts, routing, or models make the agent better or worse over time.

YAML shape (a list):
    - name: "localhost fingerprint"
      objective: "Fingerprint the local web service and identify it."
      scope:
        name: "bench-local"
        authorization_ref: "BENCH"
        allow: { hosts: ["127.0.0.1"], domains: ["localhost"] }
        deny:  { hosts: [] }
      expect:
        min_findings: 1
        tools_used: ["http_fingerprint"]   # all of these must appear
        max_blocked: 0                      # scope violations tolerated (0 = none)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Expect:
    min_findings: int = 0
    tools_used: list[str] = field(default_factory=list)
    hosts_touched: list[str] = field(default_factory=list)
    max_blocked: int | None = None


@dataclass
class Scenario:
    name: str
    objective: str
    scope: dict[str, Any]
    expect: Expect

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Scenario":
        exp = d.get("expect", {}) or {}
        return cls(
            name=d["name"],
            objective=d["objective"],
            scope=d.get("scope", {}),
            expect=Expect(
                min_findings=int(exp.get("min_findings", 0)),
                tools_used=list(exp.get("tools_used", [])),
                hosts_touched=list(exp.get("hosts_touched", [])),
                max_blocked=exp.get("max_blocked"),
            ),
        )


def load_scenarios(path: str | Path) -> list[Scenario]:
    data = yaml.safe_load(Path(path).read_text()) or []
    return [Scenario.from_dict(d) for d in data]
