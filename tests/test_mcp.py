"""Tests for the MCP tool adapter (Faz 3 upper layer).

No network/SDK needed: a FakeSession stands in for an MCP server, so we verify
discovery, scope-gating of remote tools, and result mapping in isolation.
"""
from __future__ import annotations

import pytest

from redcell.safety.scope import Scope, ScopeError, ScopeGuard
from redcell.tools.base import ToolRegistry
from redcell.tools.mcp import MCPTool, detect_target_arg, register_mcp_tools


class FakeSession:
    def __init__(self):
        self.calls = []

    def list_tools(self):
        return [
            {
                "name": "web_probe",
                "description": "probe a url",
                "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}},
            },
            {
                "name": "note",
                "description": "local note, no target",
                "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
            },
        ]

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return f"ran {name} with {arguments}"


def _guard(dry_run=False):
    scope = Scope(
        name="t", authorization_ref="TICKET-1",
        allow_hosts=["10.0.5.0/24"], allow_domains=["test.example"], deny_hosts=[],
    )
    return ScopeGuard(scope, require_approval=False, dry_run=dry_run)


def test_detect_target_arg_prefers_known_keys():
    assert detect_target_arg({"properties": {"url": {}}}) == "url"
    assert detect_target_arg({"properties": {"host": {}, "url": {}}}) == "host"
    assert detect_target_arg({"properties": {"text": {}}}) is None


def test_register_discovers_and_prefixes():
    reg = ToolRegistry()
    added = register_mcp_tools(reg, FakeSession())
    assert added == ["mcp.web_probe", "mcp.note"]
    assert reg.get("mcp.web_probe").target_arg == "url"   # gated
    assert reg.get("mcp.note").target_arg is None          # local/safe


def test_remote_tool_is_scope_gated_and_blocks_out_of_scope():
    sess = FakeSession()
    reg = ToolRegistry()
    register_mcp_tools(reg, sess)
    tool = reg.get("mcp.web_probe")
    with pytest.raises(ScopeError):
        tool.invoke({"url": "http://evil.example/x"}, _guard())
    assert sess.calls == []  # never reached the server


def test_remote_tool_runs_when_in_scope():
    sess = FakeSession()
    reg = ToolRegistry()
    register_mcp_tools(reg, sess)
    tool = reg.get("mcp.web_probe")
    res = tool.invoke({"url": "http://10.0.5.42:8080/health"}, _guard())
    assert res.ok
    assert "web_probe" in res.summary
    assert sess.calls == [("web_probe", {"url": "http://10.0.5.42:8080/health"})]


def test_local_tool_needs_no_target():
    sess = FakeSession()
    reg = ToolRegistry()
    register_mcp_tools(reg, sess)
    res = reg.get("mcp.note").invoke({"text": "hi"}, _guard())
    assert res.ok and sess.calls[-1][0] == "note"
