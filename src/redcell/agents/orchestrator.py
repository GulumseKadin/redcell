"""Orchestrator (Faz 3): run specialized agents in a state-driven loop.

Instead of a hard-coded sequence, the orchestrator asks a Router which stage
runs next, given the shared findings state and what has already run. Each
agent's task is built from the previous stages' findings (the hand-off), so
exploit sees recon's findings, verify sees exploit's, and report sees all.

The Router is injected, so the CLI can pick RuleRouter (default, cheap) or
LLMRouter (model-driven) at runtime without changing this code.
"""
from __future__ import annotations

from ..config import Settings
from ..llm.base import LLMProvider
from ..safety.scope import ScopeGuard
from ..state import Store
from ..tools.base import ToolRegistry
from .base import Agent
from .router import Router, RuleRouter, Stage, config_for

# Which prior stages each stage should receive as hand-off context.
HANDOFF_SOURCES: dict[Stage, list[Stage]] = {
    Stage.RECON: [],
    Stage.EXPLOIT: [Stage.RECON],
    Stage.VERIFY: [Stage.EXPLOIT],
    Stage.REPORT: [Stage.RECON, Stage.EXPLOIT, Stage.VERIFY],
}

MAX_STAGES = 8  # safety cap against a misbehaving router looping forever


def _findings_digest(store: Store, agents: list[Stage]) -> str:
    """Token-budgeted plain-text digest of prior findings (summaries only)."""
    lines: list[str] = []
    for stage in agents:
        for f in store.list_findings(agent=stage.value):
            lines.append(f"- [{f.agent}/{f.tool}] {f.summary}")
    return "\n".join(lines)


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        provider: LLMProvider,
        registry: ToolRegistry,
        guard: ScopeGuard,
        store: Store,
        on_event=None,
        router: Router | None = None,
    ):
        self.settings = settings
        self.provider = provider
        self.registry = registry
        self.guard = guard
        self.store = store
        self.on_event = on_event or (lambda e, p: None)
        self.router = router or RuleRouter()

    def _build_task(self, stage: Stage, objective: str) -> str:
        header = (
            f"Objective: {objective}\n"
            f"Authorized scope: {self.guard.scope.name} "
            f"({self.guard.scope.authorization_ref}).\n"
        )
        sources = HANDOFF_SOURCES.get(stage, [])
        digest = _findings_digest(self.store, sources) if sources else ""
        if not sources:
            return header + "Begin reconnaissance."
        if digest:
            return (
                header
                + f"Findings from prior stages ({', '.join(s.value for s in sources)}):\n"
                + digest
                + f"\n\nBegin your {stage.value} work based on the above."
            )
        return header + (
            f"No findings were recorded by prior stages. "
            f"Do your best {stage.value} work given the objective, or report that "
            f"there is nothing to act on."
        )

    def run(self, objective: str) -> None:
        done: list[Stage] = []
        for _ in range(MAX_STAGES):
            stage = self.router.next_stage(self.store, done, objective)
            if stage is None:
                break
            self.on_event("stage", {"stage": stage.value, "done": [s.value for s in done]})
            agent = Agent(
                config=config_for(stage, self.settings.max_steps),
                provider=self.provider,
                registry=self.registry,
                guard=self.guard,
                store=self.store,
                on_event=self.on_event,
            )
            agent.run(self._build_task(stage, objective))
            done.append(stage)
