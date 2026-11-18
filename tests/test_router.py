"""Tests for the orchestration routers.

RuleRouter — Faz 3, deterministic state machine.
LLMRouter  — Faz 6, objective-aware, observable, bounded-adaptive routing.
Both are exercised offline (the LLM router runs against a scripted provider).
"""
from __future__ import annotations

import pytest

from redcell.agents.router import LLMRouter, RuleRouter, Stage
from redcell.llm.base import LLMResponse, Message
from redcell.state.store import FindingStore


@pytest.fixture
def store(tmp_path):
    s = FindingStore(tmp_path / "findings.db")
    yield s
    s.close()


def _add(store, agent):
    store.add_finding(agent, "port_scan", {"k": "v"}, "found something")


class ScriptedProvider:
    """A fake LLMProvider that returns canned router replies, in order."""

    name = "scripted"

    def __init__(self, *replies: str):
        self._replies = list(replies)
        self.calls = 0

    def available(self) -> bool:
        return True

    def chat(self, tier, messages, tools=None, system=None, temperature=0.0):
        self.calls += 1
        reply = self._replies.pop(0) if self._replies else "DECISION: DONE\nREASON: no more."
        return LLMResponse(message=Message(role="assistant", content=reply), stop_reason="end_turn")


def test_starts_with_recon(store):
    assert RuleRouter().next_stage(store, done=[]) is Stage.RECON


def test_no_recon_findings_skips_to_report(store):
    # recon ran but recorded nothing -> nothing to exploit/verify
    assert RuleRouter().next_stage(store, done=[Stage.RECON]) is Stage.REPORT


def test_recon_findings_lead_to_exploit(store):
    _add(store, "recon")
    assert RuleRouter().next_stage(store, done=[Stage.RECON]) is Stage.EXPLOIT


def test_full_pipeline_order(store):
    _add(store, "recon")
    r = RuleRouter()
    assert r.next_stage(store, [Stage.RECON]) is Stage.EXPLOIT
    assert r.next_stage(store, [Stage.RECON, Stage.EXPLOIT]) is Stage.VERIFY
    assert r.next_stage(store, [Stage.RECON, Stage.EXPLOIT, Stage.VERIFY]) is Stage.REPORT
    assert r.next_stage(store, [Stage.RECON, Stage.EXPLOIT, Stage.VERIFY, Stage.REPORT]) is None


def test_report_only_pipeline_terminates(store):
    # no recon findings path: recon -> report -> done
    r = RuleRouter()
    assert r.next_stage(store, [Stage.RECON, Stage.REPORT]) is None


# --- LLMRouter (Faz 6) -------------------------------------------------------

def test_llm_router_recon_first_without_calling_model(store):
    p = ScriptedProvider("DECISION: exploit\nREASON: should not be reached")
    r = LLMRouter(p)
    assert r.next_stage(store, done=[], objective="map it") is Stage.RECON
    assert p.calls == 0  # recon is deterministic; no API call wasted on step 1


def test_llm_router_honors_model_choice_and_emits_rationale(store):
    events: list[tuple[str, dict]] = []
    p = ScriptedProvider("DECISION: exploit\nREASON: recon found an exposed service.")
    r = LLMRouter(p, on_event=lambda e, pl: events.append((e, pl)))
    _add(store, "recon")

    stage = r.next_stage(store, done=[Stage.RECON], objective="assess it")
    assert stage is Stage.EXPLOIT
    assert p.calls == 1
    route = [pl for e, pl in events if e == "route"]
    assert route and route[0]["source"] == "llm"
    assert route[0]["stage"] == "exploit"
    assert "exposed service" in route[0]["reason"]


def test_llm_router_done_ends_run(store):
    p = ScriptedProvider("DECISION: DONE\nREASON: objective covered and reported.")
    r = LLMRouter(p)
    assert r.next_stage(store, done=[Stage.RECON, Stage.REPORT], objective="x") is None


def test_llm_router_falls_back_on_garbage(store):
    # Unparseable answer -> deterministic RuleRouter decision (progress guaranteed).
    events: list[tuple[str, dict]] = []
    p = ScriptedProvider("I am not going to answer in the requested format at all.")
    r = LLMRouter(p, on_event=lambda e, pl: events.append((e, pl)))
    _add(store, "recon")

    stage = r.next_stage(store, done=[Stage.RECON], objective="x")
    assert stage is Stage.EXPLOIT  # what RuleRouter would pick
    assert any(pl.get("source") == "fallback" for e, pl in events if e == "route")


def test_llm_router_falls_back_on_provider_error(store):
    class Boom(ScriptedProvider):
        def chat(self, *a, **k):
            raise RuntimeError("provider down")

    _add(store, "recon")
    r = LLMRouter(Boom())
    assert r.next_stage(store, done=[Stage.RECON], objective="x") is Stage.EXPLOIT


def test_llm_router_respects_visit_cap(store):
    # exploit has already run to its cap (2); the model asking for it again is
    # out of range, so the router falls back rather than exceeding the cap.
    p = ScriptedProvider("DECISION: exploit\nREASON: one more look.")
    r = LLMRouter(p)
    _add(store, "recon")
    done = [Stage.RECON, Stage.EXPLOIT, Stage.EXPLOIT]
    stage = r.next_stage(store, done=done, objective="x")
    assert stage is not Stage.EXPLOIT  # cap enforced


def test_llm_router_terminates_when_all_caps_exhausted(store):
    p = ScriptedProvider("DECISION: recon\nREASON: should not be consulted.")
    r = LLMRouter(p)
    done = [
        Stage.RECON, Stage.RECON, Stage.EXPLOIT, Stage.EXPLOIT,
        Stage.VERIFY, Stage.VERIFY, Stage.REPORT,
    ]
    assert r.next_stage(store, done=done, objective="x") is None
    assert p.calls == 0  # no candidates -> no API call
