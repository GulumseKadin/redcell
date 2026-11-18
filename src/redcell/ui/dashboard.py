"""Live multi-agent dashboard over the orchestrator's on_event stream.

The orchestrator already emits events (stage / think / act / blocked / final)
synchronously as it runs. This module turns that stream into a live,
multi-panel terminal view using rich.Live — no new dependency, no threads.

Usage (see cli.py):
    dash = Dashboard(scope_name, auth_ref, provider_name, objective)
    with dash.live():
        orchestrator.run(objective)   # pass dash.on_event as on_event
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from rich.console import Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

PIPELINE = ["recon", "exploit", "verify", "report"]
_STATUS_ICON = {"pending": "·", "running": "▶", "done": "✓"}
_STATUS_STYLE = {"pending": "dim", "running": "bold yellow", "done": "green"}


class Dashboard:
    def __init__(self, scope_name: str, auth_ref: str, provider: str, objective: str):
        self.scope_name = scope_name
        self.auth_ref = auth_ref
        self.provider = provider
        self.objective = objective
        self.stage_status: dict[str, str] = {s: "pending" for s in PIPELINE}
        self.current_stage: str | None = None
        self.findings = 0
        self.blocked = 0
        self.log: list[tuple[str, str]] = []  # (style, text)
        self._live: Live | None = None

    # -- event sink ----------------------------------------------------------
    def on_event(self, event: str, payload: dict) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        if event == "stage":
            stage = payload["stage"]
            self.current_stage = stage
            if stage in self.stage_status:
                self.stage_status[stage] = "running"
            self._add("bold magenta", f"{ts} ▶ stage: {stage}")
        elif event == "route":
            dest = payload.get("stage") or "done"
            tag = payload.get("source", "")
            self._add("blue", f"{ts} ⇢ route [{tag}] → {dest}: {payload.get('reason', '')}")
        elif event == "think":
            self._add("dim", f"{ts} · {payload['agent']} thinking (step {payload['step']})")
        elif event == "act":
            self._add("cyan", f"{ts} → {payload['tool']} {payload.get('args', {})}")
        elif event == "blocked":
            self.blocked += 1
            self._add("red", f"{ts} ✖ blocked: {payload['reason']}")
        elif event == "final":
            agent = payload.get("agent", "")
            if agent in self.stage_status:
                self.stage_status[agent] = "done"
            self._add("green", f"{ts} ✓ {agent} done")
        self._refresh()

    def note_findings(self, n: int) -> None:
        self.findings = n
        self._refresh()

    # -- rendering -----------------------------------------------------------
    def _add(self, style: str, text: str) -> None:
        self.log.append((style, text))
        self.log = self.log[-200:]

    def _pipeline_panel(self) -> Panel:
        t = Table.grid(padding=(0, 1))
        t.add_column()
        t.add_column()
        for s in PIPELINE:
            status = self.stage_status[s]
            icon = _STATUS_ICON[status]
            t.add_row(Text(icon, style=_STATUS_STYLE[status]), Text(s, style=_STATUS_STYLE[status]))
        return Panel(t, title="pipeline", border_style="blue")

    def _stats_panel(self) -> Panel:
        body = Text()
        body.append(f"provider: {self.provider}\n")
        body.append(f"stage:    {self.current_stage or '-'}\n")
        body.append(f"findings: {self.findings}\n", style="green")
        body.append(f"blocked:  {self.blocked}", style="red" if self.blocked else "dim")
        return Panel(body, title="status", border_style="blue")

    def _log_panel(self) -> Panel:
        tail = self.log[-18:]
        group = Group(*[Text(txt, style=style) for style, txt in tail]) if tail else Text("…", style="dim")
        return Panel(group, title="live events", border_style="blue")

    def _render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(Panel(
                Text(f"redcell — {self.scope_name} ({self.auth_ref})\nobjective: {self.objective}",
                     style="bold"),
                border_style="magenta"), size=4, name="head"),
            Layout(name="body"),
        )
        layout["body"].split_row(Layout(name="left", size=22), Layout(name="right"))
        layout["left"].split_column(self._pipeline_panel(), self._stats_panel())
        layout["right"].update(self._log_panel())
        return layout

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render())

    @contextmanager
    def live(self):
        with Live(self._render(), refresh_per_second=8, screen=False) as live:
            self._live = live
            try:
                yield self
            finally:
                self._live = None
