"""Routing: which agent runs next (Faz 3 core; Faz 6 makes the LLM router real).

The orchestrator does not hard-code a sequence. It asks a Router, "given the
objective, the shared state (the FindingStore) and what has already run, which
stage is next?" Returning None ends the run.

Two implementations ship:
  * RuleRouter  — deterministic state machine. Cheap, predictable, testable.
                  This is the default.
  * LLMRouter   — a HIGH-tier model picks the next stage from an objective +
                  a budgeted findings digest, and explains *why*. It is
                  objective-aware, observable (emits a `route` event with its
                  rationale), and adaptive: it may re-run an earlier stage
                  (bounded per stage) when the findings justify it. Any failure
                  or unrecognized answer falls back to RuleRouter, so the loop
                  always makes progress.

Both satisfy the Router protocol, so the CLI can choose at runtime.
"""
from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from ..config import Tier
from ..llm.base import LLMProvider, Message
from ..state import Store
from .base import AgentConfig
from .exploit import exploit_config
from .recon import recon_config
from .report import report_config
from .verify import verify_config


class Stage(str, Enum):
    RECON = "recon"
    EXPLOIT = "exploit"
    VERIFY = "verify"
    REPORT = "report"


def config_for(stage: Stage, max_steps: int) -> AgentConfig:
    """Map a stage to its AgentConfig (system prompt + tier)."""
    return {
        Stage.RECON: recon_config,
        Stage.EXPLOIT: exploit_config,
        Stage.VERIFY: verify_config,
        Stage.REPORT: report_config,
    }[stage](max_steps)


@runtime_checkable
class Router(Protocol):
    def next_stage(
        self, store: Store, done: list[Stage], objective: str = ""
    ) -> Stage | None:
        """Return the next stage to run, or None when the run is complete."""
        ...


class RuleRouter:
    """Deterministic state machine driven by the shared findings state.

    recon -> (if recon found anything) exploit -> verify -> report -> done.
    If recon produced no findings at all, exploit/verify are skipped and we go
    straight to report (nothing to work with). The objective is ignored here —
    it is part of the Router protocol only so the LLMRouter can use it.
    """

    def next_stage(
        self, store: Store, done: list[Stage], objective: str = ""
    ) -> Stage | None:
        if Stage.RECON not in done:
            return Stage.RECON

        recon_found = len(store.list_findings(agent=Stage.RECON.value)) > 0

        if recon_found and Stage.EXPLOIT not in done:
            return Stage.EXPLOIT
        if recon_found and Stage.VERIFY not in done:
            return Stage.VERIFY
        if Stage.REPORT not in done:
            return Stage.REPORT
        return None


# How many times each stage may run in a single assessment. The LLM router is
# adaptive (it can loop back to recon/exploit/verify when findings warrant it),
# but these caps — together with the orchestrator's MAX_STAGES — guarantee the
# run always terminates. Report is a one-shot wrap-up.
_VISIT_CAP: dict[Stage, int] = {
    Stage.RECON: 2,
    Stage.EXPLOIT: 2,
    Stage.VERIFY: 2,
    Stage.REPORT: 1,
}

# Keep the routing prompt small regardless of how many findings pile up.
_DIGEST_CHAR_BUDGET = 1500


class LLMRouter:
    """LLM-driven routing (Faz 6 — the real thing).

    Decisioning:
      1. Recon always runs first (deterministic, no API call wasted on step 1).
      2. After that, a HIGH-tier model is given the objective, which stages have
         run and how often, and a budgeted digest of the findings, then picks
         the next stage from the ones still under their visit cap — or DONE.
      3. It must justify the pick in one line; that rationale is surfaced via the
         `route` event so an operator can see *why* the pipeline moved.
      4. Anything unexpected (provider error, unparseable or out-of-range answer)
         falls back to RuleRouter's deterministic choice, so progress is
         guaranteed and the interface stays identical to RuleRouter.

    The caps in `_VISIT_CAP` plus the orchestrator's MAX_STAGES bound the run.
    """

    def __init__(self, provider: LLMProvider, on_event=None):
        self.provider = provider
        self.on_event = on_event or (lambda e, p: None)
        self._fallback = RuleRouter()

    # --- public API ----------------------------------------------------------
    def next_stage(
        self, store: Store, done: list[Stage], objective: str = ""
    ) -> Stage | None:
        # 1. Recon first, always — cheap and non-negotiable.
        if Stage.RECON not in done:
            return Stage.RECON

        # 2. Which stages may still run (under their per-stage cap)?
        candidates = self._candidates(done)
        if not candidates:
            return None

        # 3. Ask the model.
        system, prompt = self._build_messages(store, done, objective, candidates)
        try:
            resp = self.provider.chat(
                tier=Tier.HIGH,
                messages=[Message(role="user", content=prompt)],
                tools=[],
                system=system,
            )
            answer = resp.message.content or ""
        except Exception as e:  # noqa: BLE001 - never let routing crash the run
            return self._fallback_decision(store, done, objective, f"provider error: {e}")

        decision, reason = self._parse(answer)

        if decision == "DONE":
            self._emit(None, reason or "model signalled the assessment is complete", "llm")
            return None
        for stage in candidates:
            if stage.value == decision:
                self._emit(stage, reason or "(no rationale given)", "llm")
                return stage

        # 4. Unrecognized / out-of-range -> deterministic fallback.
        return self._fallback_decision(
            store, done, objective, f"unrecognized router answer: {answer.strip()[:120]!r}"
        )

    # --- helpers -------------------------------------------------------------
    def _candidates(self, done: list[Stage]) -> list[Stage]:
        visits: dict[Stage, int] = {s: 0 for s in Stage}
        for s in done:
            visits[s] = visits.get(s, 0) + 1
        return [s for s in Stage if visits[s] < _VISIT_CAP[s]]

    def _build_messages(
        self, store: Store, done: list[Stage], objective: str, candidates: list[Stage]
    ) -> tuple[str, str]:
        system = (
            "You are the orchestrator of an AUTHORIZED red-team assessment. Decide "
            "which specialized agent runs next so the objective is met efficiently. "
            "Stages: recon (discover surface), exploit (assess weak points), verify "
            "(confirm/refute claims), report (write up findings). You MAY loop back "
            "to an earlier stage when new findings justify it. Stop once the "
            "objective is adequately covered and a report has been written.\n\n"
            "Answer in EXACTLY two lines:\n"
            "DECISION: <one of "
            + ", ".join(s.value for s in candidates)
            + ", or DONE>\n"
            "REASON: <one short sentence>"
        )
        counts = self._visit_summary(done)
        digest = self._digest(store)
        prompt = (
            f"Objective: {objective or '(unspecified)'}\n"
            f"Stages run so far: {counts or 'none'}.\n"
            f"Selectable next stages: {', '.join(s.value for s in candidates)}, or DONE.\n\n"
            f"Findings so far:\n{digest}\n\n"
            "What runs next?"
        )
        return system, prompt

    @staticmethod
    def _visit_summary(done: list[Stage]) -> str:
        if not done:
            return ""
        counts: dict[str, int] = {}
        for s in done:
            counts[s.value] = counts.get(s.value, 0) + 1
        return ", ".join(
            f"{name}x{n}" if n > 1 else name for name, n in counts.items()
        )

    @staticmethod
    def _digest(store: Store) -> str:
        """Budgeted plain-text digest: newest findings first, truncated to fit."""
        findings = store.list_findings()
        if not findings:
            return "(no findings yet)"
        lines: list[str] = []
        used = 0
        for f in reversed(findings):  # newest first — most relevant to routing
            line = f"- [{f.agent}/{f.tool}] {f.summary}".replace("\n", " ")
            if used + len(line) > _DIGEST_CHAR_BUDGET and lines:
                lines.append(f"- (+{len(findings) - len(lines)} earlier finding(s) omitted)")
                break
            lines.append(line)
            used += len(line)
        return "\n".join(lines)

    @staticmethod
    def _parse(answer: str) -> tuple[str, str]:
        """Pull (DECISION, REASON) out of the model reply, tolerantly.

        Prefers the structured 'DECISION:' / 'REASON:' lines, but also recognizes
        a bare stage word or 'done' anywhere in the text.
        """
        decision = ""
        reason = ""
        for raw in answer.splitlines():
            line = raw.strip()
            low = line.lower()
            if low.startswith("decision:"):
                decision = line.split(":", 1)[1].strip()
            elif low.startswith("reason:"):
                reason = line.split(":", 1)[1].strip()

        text = (decision or answer).lower()
        if "done" in text:
            return "DONE", reason
        for stage in Stage:
            if stage.value in text:
                return stage.value, reason
        return "", reason

    def _fallback_decision(
        self, store: Store, done: list[Stage], objective: str, why: str
    ) -> Stage | None:
        stage = self._fallback.next_stage(store, done, objective)
        self._emit(stage, f"fell back to rule router ({why})", "fallback")
        return stage

    def _emit(self, stage: Stage | None, reason: str, source: str) -> None:
        self.on_event(
            "route",
            {"stage": stage.value if stage else None, "reason": reason, "source": source},
        )
