"""Tests for the scope gate — the module that must never fail silently."""
from __future__ import annotations

import pytest

from redcell.safety.scope import Scope, ScopeError, ScopeGuard


def _scope() -> Scope:
    return Scope(
        name="test",
        authorization_ref="TICKET-1",
        allow_hosts=["10.0.5.0/24", "app.test.example"],
        allow_domains=["test.example"],
        deny_hosts=["10.0.5.1"],
    )


def test_permits_host_in_cidr():
    assert _scope().permits("10.0.5.42")


def test_denies_host_outside_cidr():
    assert not _scope().permits("10.0.9.9")


def test_deny_overrides_allow():
    assert not _scope().permits("10.0.5.1")


def test_domain_and_subdomain():
    s = _scope()
    assert s.permits("test.example")
    assert s.permits("api.test.example")
    assert not s.permits("evil.example")


def test_guard_blocks_out_of_scope():
    guard = ScopeGuard(_scope(), require_approval=False, dry_run=False)
    with pytest.raises(ScopeError):
        guard.check(target="8.8.8.8", action="port_scan")


def test_guard_dry_run_blocks_execution():
    guard = ScopeGuard(_scope(), require_approval=False, dry_run=True)
    with pytest.raises(ScopeError):
        guard.check(target="10.0.5.42", action="port_scan")


def test_permits_strips_scheme_and_port():
    s = _scope()
    assert s.permits("http://app.test.example:8443/login")
    assert s.permits("10.0.5.42:11434")
    assert s.permits("https://10.0.5.42")


def test_denied_host_blocked_even_with_url():
    s = _scope()
    assert not s.permits("http://10.0.5.1:8080")  # denied gateway
