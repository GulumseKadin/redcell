"""Report agent (Faz 3).

Runs on the LOW tier. It reads the accumulated findings and writes a concise
narrative summary. It calls no tools — it only reasons over the shared state
and produces plain text. (The machine-readable Markdown report is still
produced separately by report/render.py.)
"""
from __future__ import annotations

from ..config import Tier
from .base import AgentConfig

REPORT_SYSTEM = """You are a reporting agent in an AUTHORIZED security assessment.

You are given all findings gathered by the recon, exploit, and verify agents.
Your job:
- Write a clear, honest narrative summary of the assessment: what surface was
  found, what weak points were assessed, and what was CONFIRMED vs UNCONFIRMED.
- Do NOT call any tools. Do NOT invent findings beyond what you were given.
- Distinguish clearly between confirmed issues and speculation.
- When done, stop and output the summary in plain text (no tool call).
"""


def report_config(max_steps: int) -> AgentConfig:
    return AgentConfig(
        name="report",
        tier=Tier.LOW,
        system_prompt=REPORT_SYSTEM,
        max_steps=max_steps,
    )
