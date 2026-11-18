"""Tests for the opening banner (ui/banner.py).

The banner is pure presentation, so we only assert what it draws and that it
degrades safely: animation is skipped on a non-TTY, and time.sleep never
actually blocks the suite.
"""
from __future__ import annotations

import io

from rich.console import Console

from redcell.ui import banner, show_banner


def _console(*, force_terminal: bool) -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    con = Console(file=buf, force_terminal=force_terminal, color_system="truecolor" if force_terminal else None, width=100)
    return con, buf


def test_static_mode_prints_name_and_version():
    con, buf = _console(force_terminal=False)
    show_banner(con, "9.9.9", animate=False)
    out = buf.getvalue()
    assert "REDCELL" in out
    assert "9.9.9" in out


def test_non_tty_skips_animation(monkeypatch):
    # If animation were attempted, Live would run and time.sleep would be called.
    calls = {"sleep": 0}
    monkeypatch.setattr(banner.time, "sleep", lambda s: calls.__setitem__("sleep", calls["sleep"] + 1))

    con, buf = _console(force_terminal=False)
    # animate=True requested, but a non-TTY console must force the static path.
    show_banner(con, "1.2.3", animate=True)

    assert calls["sleep"] == 0
    assert "REDCELL" in buf.getvalue()
    assert "1.2.3" in buf.getvalue()


def test_no_color_env_skips_animation(monkeypatch):
    calls = {"sleep": 0}
    monkeypatch.setattr(banner.time, "sleep", lambda s: calls.__setitem__("sleep", calls["sleep"] + 1))
    monkeypatch.setenv("NO_COLOR", "1")

    con, buf = _console(force_terminal=True)
    show_banner(con, "4.5.6", animate=True)

    assert calls["sleep"] == 0
    assert "REDCELL" in buf.getvalue()


def test_animation_runs_on_terminal_but_is_bounded(monkeypatch):
    # Force the animated path on a fake terminal; stub sleep so it's instant.
    monkeypatch.setattr(banner.time, "sleep", lambda s: None)
    monkeypatch.delenv("NO_COLOR", raising=False)

    con, buf = _console(force_terminal=True)
    show_banner(con, "0.0.1", animate=True)

    # After the sweep, the static logo + version still land on screen.
    out = buf.getvalue()
    assert "REDCELL" in out
    assert "0.0.1" in out
