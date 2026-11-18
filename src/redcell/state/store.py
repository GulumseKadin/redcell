"""Shared state: the findings store.

Start with SQLite (zero setup, one file). When you reach Faz 4 and want
relationships between hosts/services/findings, this is the seam where you
swap in a Neo4j-backed store behind the same interface — agents only ever
call add_finding / list_findings, so they won't notice the change.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .base import Finding  # re-exported for backward compatibility

__all__ = ["Finding", "FindingStore"]


class FindingStore:
    def __init__(self, path: str | Path = ".redcell/findings.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent TEXT NOT NULL,
                tool TEXT NOT NULL,
                summary TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def add_finding(self, agent: str, tool: str, data: dict[str, Any], summary: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO findings (agent, tool, summary, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (agent, tool, summary, json.dumps(data), time.time()),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def list_findings(self, agent: str | None = None) -> list[Finding]:
        if agent is None:
            rows = self._conn.execute(
                "SELECT id, agent, tool, summary, data, created_at FROM findings ORDER BY id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, agent, tool, summary, data, created_at FROM findings "
                "WHERE agent = ? ORDER BY id",
                (agent,),
            ).fetchall()
        return [
            Finding(id=r[0], agent=r[1], tool=r[2], summary=r[3], data=json.loads(r[4]), created_at=r[5])
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()
