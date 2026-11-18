"""Tests for the Faz 9 Ollama provider hardening (offline, httpx monkeypatched)."""
from __future__ import annotations

import httpx
import pytest

from redcell.config import Settings, Tier
from redcell.llm.base import Message, ToolCall
from redcell.llm.providers import ollama as ollama_mod
from redcell.llm.providers.ollama import OllamaProvider


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(ollama_mod.time, "sleep", lambda s: None)


def _provider(**kw) -> OllamaProvider:
    kw.setdefault("request_timeout", 5.0)
    kw.setdefault("max_retries", 2)
    return OllamaProvider(Settings(**kw))


class FakeResp:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("POST", "http://x"),
                response=httpx.Response(self.status_code),
            )


# --- _coerce_args ------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ({"a": 1}, {"a": 1}),
    ('{"a": 1}', {"a": 1}),
    ("not json", {}),
    ("", {}),
    ("[1, 2]", {}),       # valid JSON but not a dict
    (None, {}),
    (123, {}),
])
def test_coerce_args(raw, expected):
    assert OllamaProvider._coerce_args(raw) == expected


# --- message serialization ---------------------------------------------------

def test_msg_echoes_assistant_tool_calls():
    m = Message(role="assistant", content="", tool_calls=[
        ToolCall(id="c0", name="port_scan", arguments={"target": "10.0.0.1"})])
    out = OllamaProvider._msg(m)
    assert out["tool_calls"][0]["function"]["name"] == "port_scan"
    assert out["tool_calls"][0]["function"]["arguments"] == {"target": "10.0.0.1"}


def test_msg_tool_role_is_plain():
    out = OllamaProvider._msg(Message(role="tool", content="result text"))
    assert out == {"role": "tool", "content": "result text"}


# --- chat: robust tool-call parsing ------------------------------------------

def test_chat_survives_malformed_tool_args(monkeypatch):
    body = {"message": {"content": "", "tool_calls": [
        {"function": {"name": "port_scan", "arguments": "}{ broken json"}}]}}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(body=body))
    resp = _provider().chat(Tier.LOW, [Message(role="user", content="go")])
    assert resp.stop_reason == "tool_use"
    assert resp.message.tool_calls[0].name == "port_scan"
    assert resp.message.tool_calls[0].arguments == {}  # degraded, not crashed


def test_chat_skips_nameless_tool_call(monkeypatch):
    body = {"message": {"content": "hi", "tool_calls": [{"function": {"arguments": {}}}]}}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(body=body))
    resp = _provider().chat(Tier.LOW, [Message(role="user", content="go")])
    assert resp.message.tool_calls == []
    assert resp.stop_reason == "end_turn"


# --- _post retries -----------------------------------------------------------

def test_post_retries_on_network_error_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return FakeResp(body={"ok": True})

    monkeypatch.setattr(httpx, "post", flaky)
    data = _provider(max_retries=2)._post("http://x", {})
    assert data == {"ok": True}
    assert calls["n"] == 3  # 1 initial + 2 retries


def test_post_retries_on_5xx_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        return FakeResp(status_code=503, text="busy") if calls["n"] == 1 else FakeResp(body={"ok": 1})

    monkeypatch.setattr(httpx, "post", flaky)
    assert _provider()._post("http://x", {}) == {"ok": 1}
    assert calls["n"] == 2


def test_post_does_not_retry_on_4xx(monkeypatch):
    calls = {"n": 0}

    def bad(*a, **k):
        calls["n"] += 1
        return FakeResp(status_code=400, text="bad request")

    monkeypatch.setattr(httpx, "post", bad)
    with pytest.raises(httpx.HTTPStatusError):
        _provider()._post("http://x", {})
    assert calls["n"] == 1  # no retry on client error


def test_post_gives_up_after_retries(monkeypatch):
    def always_down(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", always_down)
    with pytest.raises(RuntimeError, match="failed after 3 attempt"):
        _provider(max_retries=2)._post("http://x", {})
