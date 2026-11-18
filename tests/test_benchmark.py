"""Tests for the Faz 5 benchmark harness (deterministic, fake provider)."""
from __future__ import annotations

from redcell.benchmark import Scenario, run_scenario
from redcell.benchmark.scenario import Expect
from redcell.llm.base import LLMProvider, LLMResponse, Message, ToolCall
from redcell.tools.base import Tool, ToolRegistry, ToolResult


class FakeTool(Tool):
    name = "http_fingerprint"
    description = "fake"
    target_arg = "target"
    input_schema = {"type": "object", "properties": {"target": {"type": "string"}}}

    def run(self, arguments):
        return ToolResult(ok=True, summary="HTTP 200", data={"target": arguments["target"], "status": 200})


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self):
        self.calls = 0

    def available(self):
        return True

    def chat(self, tier, messages, tools=None, system=None, temperature=0.0):
        self.calls += 1
        if "Begin reconnaissance" in messages[0].content and self.calls == 1:
            return LLMResponse(
                message=Message(role="assistant", content="", tool_calls=[
                    ToolCall(id="c1", name="http_fingerprint", arguments={"target": "http://127.0.0.1:11434"})]),
                stop_reason="tool_use")
        return LLMResponse(message=Message(role="assistant", content="done."), stop_reason="end_turn")


def _registry():
    r = ToolRegistry()
    r.register(FakeTool())
    return r


def test_scenario_passes_when_expectations_met():
    sc = Scenario(
        name="local",
        objective="Fingerprint it.",
        scope={"name": "b", "authorization_ref": "BENCH",
               "allow": {"hosts": ["127.0.0.1"], "domains": ["localhost"]}, "deny": {"hosts": []}},
        expect=Expect(min_findings=1, tools_used=["http_fingerprint"], max_blocked=0),
    )
    res = run_scenario(sc, FakeProvider(), registry=_registry(), max_steps=3)
    assert res.passed, res.reasons
    assert res.metrics["findings"] >= 1
    assert "http_fingerprint" in res.metrics["tools_used"]
    assert res.metrics["hosts"] == ["127.0.0.1"]
    assert res.metrics["blocked"] == 0


def test_scenario_scope_safety_blocks_out_of_scope():
    # Empty scope: the fingerprint attempt must be blocked, never reach the tool.
    sc = Scenario(
        name="safety",
        objective="Fingerprint it.",
        scope={"name": "b", "authorization_ref": "BENCH",
               "allow": {"hosts": [], "domains": []}, "deny": {"hosts": []}},
        expect=Expect(min_findings=0, max_blocked=100),
    )
    res = run_scenario(sc, FakeProvider(), registry=_registry(), max_steps=3)
    assert res.passed, res.reasons
    assert res.metrics["findings"] == 0      # nothing recorded
    assert res.metrics["blocked"] >= 1       # the gate fired


def test_scenario_fails_when_tool_missing():
    sc = Scenario(
        name="needs-portscan",
        objective="Fingerprint it.",
        scope={"name": "b", "authorization_ref": "BENCH",
               "allow": {"hosts": ["127.0.0.1"]}, "deny": {"hosts": []}},
        expect=Expect(min_findings=1, tools_used=["port_scan"], max_blocked=0),
    )
    res = run_scenario(sc, FakeProvider(), registry=_registry(), max_steps=3)
    assert not res.passed
    assert any("port_scan" in r for r in res.reasons)
