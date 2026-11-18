"""Tests for Faz 5 CVSS 4.0 scoring and report rendering."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from redcell.report.render import render_markdown
from redcell.report.scoring import score_cvss4, try_score_cvss4
from redcell.state.store import FindingStore

_CRIT = "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"


def test_score_cvss4_critical():
    sc = score_cvss4(_CRIT)
    assert sc.base_score == 9.3
    assert sc.severity == "Critical"


def test_score_cvss4_invalid_raises():
    with pytest.raises(ValueError):
        score_cvss4("CVSS:4.0/AV:X")


def test_try_score_handles_missing_and_bad():
    assert try_score_cvss4("") is None
    assert try_score_cvss4("not-a-vector") is None
    assert try_score_cvss4(_CRIT).severity == "Critical"


def test_render_includes_score_poc_and_remediation():
    with tempfile.TemporaryDirectory() as tmp:
        store = FindingStore(Path(tmp) / "f.db")
        store.add_finding(
            "exploit", "http_fingerprint",
            {
                "target": "10.0.5.42",
                "cvss": _CRIT,
                "remediation": "Disable the exposed admin endpoint.",
                "poc": {"request": "GET /admin HTTP/1.1", "response": "200 OK"},
            },
            "exposed admin panel",
        )
        store.add_finding("recon", "port_scan", {"target": "10.0.5.42"}, "open ports")
        md = render_markdown(store, "eng", "REF-1")
        store.close()

    assert "9.3 (Critical)" in md
    assert "Severity summary: Critical: 1" in md
    assert "Disable the exposed admin endpoint." in md
    assert "GET /admin HTTP/1.1" in md
    assert "_not scored_" in md       # the second finding has no cvss
