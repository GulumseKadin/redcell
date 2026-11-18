"""CVSS 4.0 scoring (Faz 5).

Thin wrapper over the `cvss` library (optional dependency, lazy-imported, like
anthropic/mcp/neo4j). We don't reimplement the CVSS 4.0 MacroVector tables —
getting a severity score wrong in a security report is worse than needing one
small dependency. Install with: pip install redcell[cvss]

A finding becomes "scored" when its data carries a CVSS 4.0 vector string under
data["cvss"]; render.py calls score_cvss4() to turn that into a number + rating.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CvssScore:
    vector: str
    base_score: float
    severity: str   # None / Low / Medium / High / Critical


def score_cvss4(vector: str) -> CvssScore:
    """Parse and score a CVSS 4.0 vector. Raises ValueError on a bad vector."""
    try:
        from cvss import CVSS4
        from cvss.exceptions import CVSS4Error
    except ImportError as e:  # pragma: no cover - optional extra
        raise RuntimeError(
            "CVSS scoring needs the 'cvss' package. Install with: pip install redcell[cvss]"
        ) from e

    try:
        c = CVSS4(vector)
    except CVSS4Error as e:
        raise ValueError(f"invalid CVSS 4.0 vector: {e}") from e
    return CvssScore(vector=c.clean_vector(), base_score=c.base_score, severity=c.severity)


def try_score_cvss4(vector: str) -> CvssScore | None:
    """Score a vector, or return None if it is missing/invalid (never raises)."""
    if not vector or not isinstance(vector, str):
        return None
    try:
        return score_cvss4(vector)
    except (ValueError, RuntimeError):
        return None
