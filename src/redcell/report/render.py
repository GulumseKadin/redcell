"""Reporting (Faz 5).

Turns the findings store into a Markdown report with CVSS 4.0 scoring, a PoC
block, and remediation — the Pensar-Apex pattern. These are read from each
finding's structured `data`, so any agent/tool that fills them gets a scored,
evidence-backed report entry; findings without them fall back to "not scored".

Convention (all optional, inside Finding.data):
    data["cvss"]        -> a CVSS 4.0 vector string, scored via report.scoring
    data["poc"]         -> str, or dict with request/response/command/output
    data["remediation"] -> str
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..state import Store
from .scoring import try_score_cvss4

# Order used to summarize severity counts at the top of the report.
_SEV_ORDER = ["Critical", "High", "Medium", "Low", "None"]


def _poc_block(poc: Any) -> list[str]:
    if not poc:
        return []
    out = ["- PoC:"]
    if isinstance(poc, dict):
        for key in ("command", "request", "response", "output"):
            if poc.get(key):
                out += [f"  - {key}:", "", "    ```", *[f"    {ln}" for ln in str(poc[key]).splitlines()], "    ```"]
    else:
        out += ["", "  ```", *[f"  {ln}" for ln in str(poc).splitlines()], "  ```"]
    return out


def render_markdown(store: Store, scope_name: str, authorization_ref: str) -> str:
    findings = store.list_findings()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Pre-score so we can show a severity summary up top.
    scores = {f.id: try_score_cvss4(f.data.get("cvss", "")) for f in findings}
    sev_counts: dict[str, int] = {}
    for sc in scores.values():
        if sc:
            sev_counts[sc.severity] = sev_counts.get(sc.severity, 0) + 1

    lines = [
        f"# Assessment report — {scope_name}",
        "",
        f"Authorization: {authorization_ref}  ",
        f"Generated: {now}  ",
        f"Findings recorded: {len(findings)}",
    ]
    if sev_counts:
        summary = ", ".join(f"{s}: {sev_counts[s]}" for s in _SEV_ORDER if s in sev_counts)
        lines.append(f"Severity summary: {summary}")
    lines += ["", "## Findings", ""]

    if not findings:
        lines.append("_No findings recorded yet._")

    for f in findings:
        lines += [
            f"### #{f.id} — {f.tool} (via {f.agent})",
            "",
            "```",
            f.summary.strip(),
            "```",
            "",
        ]
        sc = scores[f.id]
        if sc:
            lines.append(f"- CVSS 4.0: **{sc.base_score} ({sc.severity})** — `{sc.vector}`")
        else:
            lines.append("- CVSS 4.0: _not scored_")
        remediation = f.data.get("remediation")
        lines.append(f"- Remediation: {remediation}" if remediation else "- Remediation: _none provided_")
        lines += _poc_block(f.data.get("poc"))
        lines.append("")

    return "\n".join(lines)
