"""Store selection: pick the shared-state backend from settings.

Default is SQLite (zero setup). Set REDCELL_STORE=neo4j (plus NEO4J_URI /
NEO4J_USER / NEO4J_PASSWORD) to put the graph behind the same interface.
Agents don't change either way.
"""
from __future__ import annotations

from pathlib import Path

from ..config import Settings, StoreBackend
from .base import Store
from .store import FindingStore


def build_store(settings: Settings) -> Store:
    if settings.store == StoreBackend.NEO4J:
        from .neo4j_store import Neo4jStore

        if not settings.neo4j_password:
            raise RuntimeError(
                "REDCELL_STORE=neo4j requires NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD."
            )
        return Neo4jStore(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            database=settings.neo4j_database or None,
        )
    return FindingStore(Path(settings.workdir) / "findings.db")
