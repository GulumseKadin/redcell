"""Finding-recording tool (Faz 7).

Faz 5 built the scoring and report side (`report/scoring.py`, `report/render.py`),
but nothing *produced* a scored finding — the recon/exploit/verify tools emit raw
observations, so every report entry fell back to "not scored". This tool closes
that loop: an agent calls `record_finding` to write an evidence-backed conclusion
(title + optional CVSS 4.0 vector, PoC, remediation) into the shared store.

It reuses the existing persistence path: the agent loop already writes any tool
result's `data` into the store as a Finding, and `report/render.py` reads
`data["cvss"|"poc"|"remediation"]`. So this tool only has to shape and validate
that data — no store wiring, no schema change.

It touches no target (pure bookkeeping), so it is NOT scope-gated: `target_arg`
is None. The optional `target` field is recorded only so graph stores can link
the finding to the host it is about.
"""
from __future__ import annotations

from typing import Any

from ..report.scoring import try_score_cvss4
from .base import Tool, ToolResult


class RecordFindingTool(Tool):
    """Persist a confirmed, evidence-backed finding into the assessment report."""

    name = "record_finding"
    description = (
        "Record a CONFIRMED, evidence-backed finding so it appears, scored, in the "
        "report. Provide a CVSS 4.0 vector, a reproducible PoC, and remediation "
        "whenever you can. Use this only for findings you have substantiated — not "
        "for speculation. Local bookkeeping: it touches no target."
    )
    target_arg = None  # pure bookkeeping; never scope-gated

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short finding title, e.g. 'Exposed Ollama API with no auth'.",
            },
            "cvss": {
                "type": "string",
                "description": (
                    "CVSS 4.0 vector string, e.g. "
                    "'CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N'. "
                    "Omit if you cannot justify one."
                ),
            },
            "poc": {
                "type": "string",
                "description": "Reproduction evidence: the command/request and the observed output.",
            },
            "remediation": {
                "type": "string",
                "description": "Concrete fix recommendation.",
            },
            "target": {
                "type": "string",
                "description": "The in-scope host/URL this finding is about.",
            },
        },
        "required": ["title"],
    }

    def run(self, arguments: dict[str, Any]) -> ToolResult:
        title = str(arguments.get("title", "")).strip()
        if not title:
            return ToolResult(ok=False, summary="record_finding: 'title' is required.")

        # Only keep fields the agent actually provided, so render.py's "optional"
        # convention holds (missing -> "not scored" / "none provided").
        data: dict[str, Any] = {"title": title}
        for key in ("cvss", "poc", "remediation", "target"):
            val = arguments.get(key)
            if isinstance(val, str) and val.strip():
                data[key] = val.strip()

        # Validate the CVSS vector up front so the agent gets immediate feedback,
        # but never hard-fail: an unscored finding is still worth recording.
        note = ""
        if "cvss" in data:
            score = try_score_cvss4(data["cvss"])
            if score is None:
                note = " (CVSS vector could not be scored — recorded unscored)"
            else:
                note = f" [CVSS {score.base_score} {score.severity}]"

        return ToolResult(ok=True, summary=f"Recorded finding: {title}{note}", data=data)
