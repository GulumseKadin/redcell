"""Tests for the Faz 7 record_finding tool and its scored report path."""
from __future__ import annotations

import pytest

from redcell.report.render import render_markdown
from redcell.state.store import FindingStore
from redcell.tools.builtins import default_registry
from redcell.tools.findings import RecordFindingTool

GOOD_VECTOR = "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"


class _ExplodingGuard:
    """A guard whose check must never be called (record_finding is local)."""

    def check(self, target, action):  # pragma: no cover - asserts if reached
        raise AssertionError("record_finding must not be scope-gated")


def test_requires_title():
    res = RecordFindingTool().run({"poc": "x"})
    assert not res.ok
    assert "title" in res.summary


def test_keeps_only_provided_fields():
    res = RecordFindingTool().run({"title": "Open port", "remediation": "close it"})
    assert res.ok
    assert res.data == {"title": "Open port", "remediation": "close it"}
    assert "cvss" not in res.data and "poc" not in res.data


def test_valid_cvss_is_scored_in_summary():
    res = RecordFindingTool().run({"title": "Exposed API", "cvss": GOOD_VECTOR})
    assert res.ok
    assert res.data["cvss"] == GOOD_VECTOR
    assert "CVSS" in res.summary and "Critical" in res.summary


def test_invalid_cvss_still_records_unscored():
    res = RecordFindingTool().run({"title": "Maybe bad", "cvss": "not-a-vector"})
    assert res.ok
    assert res.data["cvss"] == "not-a-vector"  # kept; render will show "not scored"
    assert "could not be scored" in res.summary


def test_not_scope_gated():
    # target_arg is None, so Tool.invoke must skip the guard entirely.
    res = RecordFindingTool().invoke({"title": "local note"}, _ExplodingGuard())
    assert res.ok


def test_registered_in_default_registry():
    assert default_registry().get("record_finding") is not None


def test_end_to_end_scored_report(tmp_path):
    store = FindingStore(tmp_path / "f.db")
    res = RecordFindingTool().run(
        {
            "title": "Exposed Ollama API with no auth",
            "cvss": GOOD_VECTOR,
            "poc": "curl http://127.0.0.1:11434/api/tags -> 200 with model list",
            "remediation": "Bind to loopback only; add an auth proxy.",
            "target": "127.0.0.1",
        }
    )
    store.add_finding("verify", "record_finding", res.data, res.summary)
    md = render_markdown(store, "demo", "AUTH-1")
    store.close()

    assert "Exposed Ollama API with no auth" in md
    assert "CVSS 4.0: **" in md and "Critical" in md       # scored, not "_not scored_"
    assert "Severity summary: Critical: 1" in md
    assert "- PoC:" in md and "curl http://127.0.0.1:11434" in md
    assert "Bind to loopback only" in md


@pytest.mark.parametrize("field", ["poc", "remediation", "target"])
def test_blank_strings_are_dropped(field):
    res = RecordFindingTool().run({"title": "t", field: "   "})
    assert field not in res.data
