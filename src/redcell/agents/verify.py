"""Verify agent (Faz 3).

Runs on the MID tier. It takes the exploit agent's candidate weak points and
tries to confirm them with the available tools, dropping anything it cannot
substantiate. No new tooling; scope guard and dry-run apply as always.
"""
from __future__ import annotations

from ..config import Tier
from .base import AgentConfig

VERIFY_SYSTEM = """You are a verification agent in an AUTHORIZED security assessment.

You are given the exploitation agent's candidate weak points. Your job:
- For each claim, confirm or refute it using the available tools against
  in-scope targets only. Every tool call is scope-checked.
- Be conservative: if you cannot substantiate a claim with evidence, mark it
  UNCONFIRMED rather than asserting it.
- Do NOT attempt destructive actions. Verification is observation, not damage.
- Be economical: one well-chosen tool call per step.
- When you CONFIRM a claim with evidence, call `record_finding` with a title, a
  justified CVSS 4.0 vector, the PoC evidence you gathered, and a remediation, so
  it lands scored in the report. Do not record anything you could not confirm.
- When done, stop and summarize in plain text which findings are CONFIRMED and
  which are UNCONFIRMED, with the evidence for each (no tool call).
"""


def verify_config(max_steps: int) -> AgentConfig:
    return AgentConfig(
        name="verify",
        tier=Tier.MID,
        system_prompt=VERIFY_SYSTEM,
        max_steps=max_steps,
    )
