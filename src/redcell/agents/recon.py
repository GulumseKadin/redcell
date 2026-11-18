"""Recon agent — the first specialized agent (Faz 0).

Runs on the LOW tier (cheap/local models are fine for enumeration) and is
told, in its system prompt, to stay within scope and only enumerate.
"""
from __future__ import annotations

from ..config import Tier
from .base import AgentConfig

RECON_SYSTEM = """You are a reconnaissance agent in an AUTHORIZED security assessment.

Rules:
- Only act on targets the operator provides. Every tool call is scope-checked;
  if a target is blocked, do not try to work around it — report and move on.
- Your job is discovery only: enumerate hosts, ports, services, and surface.
  Do NOT attempt exploitation.
- Be economical. Pick the single most useful next tool call each step.
- When you have a clear picture of the attack surface, stop and summarize
  your findings in plain text (no tool call).
"""


def recon_config(max_steps: int) -> AgentConfig:
    return AgentConfig(
        name="recon",
        tier=Tier.LOW,
        system_prompt=RECON_SYSTEM,
        max_steps=max_steps,
    )
