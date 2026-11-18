"""redcell command-line interface.

Commands (Decepticon-style):
    redcell onboard        interactive-ish setup, writes .env
    redcell scope init     create a starter scope.yaml
    redcell tools          list registered tools
    redcell run OBJECTIVE  run the orchestrator against the current scope
    redcell report         render the findings store to Markdown
    redcell version
"""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import get_settings
from .report.render import render_markdown
from .safety.scope import Scope, ScopeError, ScopeGuard
from .state import build_store
from .tools.builtins import default_registry

app = typer.Typer(add_completion=False, help="Authorized autonomous red-team agent (skeleton).")
console = Console()

SCOPE_TEMPLATE = """# redcell scope — ONLY list systems you are authorized to test.
name: "Example engagement"
authorization_ref: "REPLACE-WITH-YOUR-SOW-OR-TICKET"
allow:
  hosts: []          # e.g. ["10.0.5.0/24", "app.test.example"]
  domains: []        # e.g. ["test.example"]
deny:
  hosts: []          # anything in-range you must NOT touch
"""

ENV_TEMPLATE = """# redcell configuration
REDCELL_PROVIDER=anthropic
ANTHROPIC_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
REDCELL_SCOPE_FILE=scope.yaml
REDCELL_REQUIRE_APPROVAL=true
REDCELL_DRY_RUN=false
REDCELL_MAX_STEPS=25

# Shared state backend: sqlite (default) or neo4j
REDCELL_STORE=sqlite
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=
"""


@app.command()
def version() -> None:
    console.print(f"redcell {__version__}")


@app.command()
def onboard() -> None:
    """Write a starter .env if one doesn't exist."""
    env = Path(".env")
    if env.exists():
        console.print("[yellow].env already exists — leaving it untouched.[/]")
    else:
        env.write_text(ENV_TEMPLATE)
        console.print("[green]Wrote .env[/] — fill in your provider key, then run `redcell scope init`.")


@app.command("scope")
def scope_cmd(action: str = typer.Argument(..., help="only 'init' for now")) -> None:
    if action != "init":
        raise typer.BadParameter("only 'init' is supported")
    path = Path(get_settings().scope_file)
    if path.exists():
        console.print(f"[yellow]{path} already exists — not overwriting.[/]")
        raise typer.Exit(1)
    path.write_text(SCOPE_TEMPLATE)
    console.print(f"[green]Wrote {path}[/] — edit it before running anything.")


@app.command()
def tools() -> None:
    reg = default_registry()
    table = Table(title="Registered tools")
    table.add_column("name", style="bold")
    table.add_column("target-gated")
    table.add_column("description")
    for name in reg.names():
        t = reg.get(name)
        table.add_row(name, "yes" if t.target_arg else "no", t.description)
    console.print(table)


def _load_guard(settings, approval=None) -> ScopeGuard:
    scope = Scope.load(settings.scope_file)
    return ScopeGuard(
        scope,
        require_approval=settings.require_approval,
        dry_run=settings.dry_run,
        approval=approval,
    )


@app.command()
def run(
    objective: str = typer.Argument(..., help="what you want the agent to accomplish"),
    router: str = typer.Option(
        "rule",
        "--router",
        help="which orchestration router to use: 'rule' (deterministic, default) or 'llm'",
    ),
    ui: bool = typer.Option(
        False,
        "--ui",
        help="show a live multi-agent dashboard instead of plain log lines",
    ),
    mcp: str = typer.Option(
        "",
        "--mcp",
        help="launch a stdio MCP server and register its tools, e.g. --mcp 'python -m my_server'",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="auto-approve every in-scope action (non-interactive). Scope is still enforced.",
    ),
    no_banner: bool = typer.Option(
        False,
        "--no-banner",
        help="skip the opening red-eye banner animation.",
    ),
) -> None:
    """Run the orchestrator against the authorized scope."""
    from . import __version__
    from .agents.orchestrator import Orchestrator
    from .agents.router import LLMRouter, RuleRouter
    from .llm.factory import build_provider
    from .ui import show_banner
    from .ui.dashboard import Dashboard

    # Opening banner. Animate only when it won't collide with the live dashboard
    # and we have a real terminal; otherwise show_banner falls back to a static line.
    show_banner(console, __version__, animate=not (no_banner or ui))

    settings = get_settings()

    # Faz 8: pick the approval policy. --yes (or --ui, where a stdin prompt would
    # collide with the live display) auto-approves; otherwise prompt interactively.
    approval = None
    if settings.require_approval and (yes or ui):
        from .safety.approval import AutoApproval

        approval = AutoApproval(True)
        if ui and not yes:
            console.print("[yellow]--ui implies --yes: in-scope actions auto-approved.[/]")

    try:
        guard = _load_guard(settings, approval=approval)
    except ScopeError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)

    console.print(f"[bold]Scope:[/] {guard.scope.name} ({guard.scope.authorization_ref})")
    if settings.dry_run:
        console.print("[yellow]DRY-RUN mode: no tool will actually execute.[/]")

    provider = build_provider(settings)
    console.print(f"[bold]Provider:[/] {provider.name}")
    try:
        store = build_store(settings)
    except RuntimeError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    console.print(f"[bold]Store:[/] {settings.store.value}")

    registry = default_registry()
    if mcp:
        from .tools.mcp import StdioMCPClient, register_mcp_tools

        parts = mcp.split()
        try:
            client = StdioMCPClient(command=parts[0], args=parts[1:])
            added = register_mcp_tools(registry, client)
            console.print(f"[bold]MCP:[/] registered {len(added)} tool(s): {', '.join(added)}")
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]MCP connection failed:[/] {e}")
            raise typer.Exit(1)

    def on_event(event: str, payload: dict) -> None:
        if event == "stage":
            console.print(f"\n[bold magenta]▶ stage: {payload['stage']}[/]")
        elif event == "route":
            dest = payload.get("stage") or "done"
            tag = payload.get("source", "")
            # parens, not [brackets] — console.print would read [llm] as rich markup.
            console.print(f"[blue]⇢ route[/] ({tag}) → {dest}: {payload.get('reason', '')}")
        elif event == "think":
            console.print(f"[dim]· {payload['agent']} thinking (step {payload['step']})[/]")
        elif event == "act":
            console.print(f"[cyan]→ {payload['tool']}[/] {payload.get('args', {})}")
        elif event == "blocked":
            console.print(f"[red]✖ blocked:[/] {payload['reason']}")
        elif event == "final":
            console.print(f"[green]✓ {payload['agent']} done[/]")

    if router not in ("llm", "rule"):
        raise typer.BadParameter("--router must be 'rule' or 'llm'")

    if ui:
        dash = Dashboard(guard.scope.name, guard.scope.authorization_ref, provider.name, objective)
        emit = dash.on_event
    else:
        dash = None
        emit = on_event

    # The LLM router shares the run's event sink, so its routing rationale shows
    # up in the same log/dashboard as everything else.
    router_impl = LLMRouter(provider, on_event=emit) if router == "llm" else RuleRouter()

    orch = Orchestrator(
        settings, provider, registry, guard, store, emit, router=router_impl
    )
    if dash is not None:
        with dash.live():
            orch.run(objective)
            dash.note_findings(len(store.list_findings()))
    else:
        orch.run(objective)

    summary = guard.audit_summary()
    if summary:
        allowed = summary.get("allowed", 0)
        blocked = sum(v for k, v in summary.items() if k.startswith("blocked"))
        console.print(f"[bold]Scope audit:[/] {allowed} allowed, {blocked} blocked {summary}")
    console.print("\nRun complete. Use `redcell report` to render findings.")


@app.command()
def bench(
    scenarios: str = typer.Argument(..., help="path to a YAML file of benchmark scenarios"),
    max_steps: int = typer.Option(6, help="per-agent step cap during the benchmark"),
) -> None:
    """Run benchmark scenarios and report pass/fail + metrics."""
    from .benchmark import load_scenarios, run_scenario
    from .llm.factory import build_provider

    settings = get_settings()
    try:
        provider = build_provider(settings)
    except RuntimeError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    console.print(f"[bold]Provider:[/] {provider.name}")

    cases = load_scenarios(scenarios)
    table = Table(title="Benchmark results")
    table.add_column("scenario", style="bold")
    table.add_column("result")
    table.add_column("findings")
    table.add_column("tools")
    table.add_column("blocked")
    table.add_column("notes")

    failures = 0
    for sc in cases:
        res = run_scenario(sc, provider, max_steps=max_steps)
        failures += 0 if res.passed else 1
        table.add_row(
            res.name,
            "[green]PASS[/]" if res.passed else "[red]FAIL[/]",
            str(res.metrics.get("findings", 0)),
            ", ".join(res.metrics.get("tools_used", [])) or "-",
            str(res.metrics.get("blocked", 0)),
            "; ".join(res.reasons) or "-",
        )
    console.print(table)
    if failures:
        console.print(f"[red]{failures} scenario(s) failed.[/]")
        raise typer.Exit(1)
    console.print("[green]All scenarios passed.[/]")


@app.command()
def report(out: str = typer.Option("report.md", help="output markdown path")) -> None:
    settings = get_settings()
    scope = Scope.load(settings.scope_file)
    try:
        store = build_store(settings)
    except RuntimeError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    md = render_markdown(store, scope.name, scope.authorization_ref)
    Path(out).write_text(md)
    console.print(f"[green]Wrote {out}[/]")


if __name__ == "__main__":
    app()
