"""Tests for the Faz 8 approval policies and the guard's audit trail."""
from __future__ import annotations

import pytest

from redcell.safety.approval import AutoApproval, CallbackApproval, CliApproval
from redcell.safety.scope import Scope, ScopeError, ScopeGuard


def _scope() -> Scope:
    return Scope(name="t", authorization_ref="A-1", allow_hosts=["10.0.5.0/24"])


# --- policies ----------------------------------------------------------------

def test_auto_approval_allow_and_deny():
    assert AutoApproval(True).decide("h", "a") is True
    assert AutoApproval(False).decide("h", "a") is False


def test_callback_approval_delegates():
    seen = []
    pol = CallbackApproval(lambda t, a: seen.append((t, a)) or t == "ok")
    assert pol.decide("ok", "scan") is True
    assert pol.decide("no", "scan") is False
    assert seen == [("ok", "scan"), ("no", "scan")]


@pytest.mark.parametrize("reply,expected", [("y", True), ("yes", True), ("", False), ("n", False)])
def test_cli_approval_reads_prompt(reply, expected):
    pol = CliApproval(prompt=lambda _msg: reply)
    assert pol.decide("10.0.5.5", "port_scan") is expected


# --- guard integration + audit ----------------------------------------------

def test_guard_uses_policy_and_allows():
    guard = ScopeGuard(_scope(), require_approval=True, dry_run=False, approval=AutoApproval(True))
    guard.check("10.0.5.5", "port_scan")  # no raise
    assert guard.audit[-1].allowed is True
    assert guard.audit[-1].reason == "allowed"


def test_guard_declined_blocks_and_audits():
    guard = ScopeGuard(_scope(), require_approval=True, dry_run=False, approval=AutoApproval(False))
    with pytest.raises(ScopeError):
        guard.check("10.0.5.5", "port_scan")
    assert guard.audit[-1].reason == "blocked:declined"
    assert guard.audit[-1].allowed is False


def test_guard_out_of_scope_audited():
    guard = ScopeGuard(_scope(), require_approval=False, dry_run=False)
    with pytest.raises(ScopeError):
        guard.check("8.8.8.8", "port_scan")
    assert guard.audit[-1].reason == "blocked:out-of-scope"


def test_guard_dry_run_audited():
    guard = ScopeGuard(_scope(), require_approval=False, dry_run=True)
    with pytest.raises(ScopeError):
        guard.check("10.0.5.5", "port_scan")
    assert guard.audit[-1].reason == "blocked:dry-run"


def test_audit_summary_counts():
    guard = ScopeGuard(_scope(), require_approval=False, dry_run=False)
    guard.check("10.0.5.5", "a")
    guard.check("10.0.5.6", "b")
    with pytest.raises(ScopeError):
        guard.check("8.8.8.8", "c")
    summary = guard.audit_summary()
    assert summary["allowed"] == 2
    assert summary["blocked:out-of-scope"] == 1


def test_backward_compatible_constructor():
    # The original 3-arg positional form still works; approval defaults to None.
    guard = ScopeGuard(_scope(), False, False)
    assert guard.approval is None
    guard.check("10.0.5.5", "a")  # require_approval False -> no prompt, allowed
    assert guard.audit[-1].allowed is True
