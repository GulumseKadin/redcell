"""Neo4j-backed findings store (Faz 4).

Same add_finding / list_findings surface as the SQLite FindingStore, so agents
are unchanged. The win is relationships: each finding becomes a graph node
linked to the Agent that found it and the Host it is about, so later you can ask
graph questions ("every finding about host X", "which agents touched which
hosts") that are awkward in flat SQL.

Graph model:
    (:Agent {name})-[:FOUND]->(:Finding {id, tool, summary, data, created_at})
    (:Finding)-[:ABOUT]->(:Host {name})         # when a target can be derived

The `neo4j` driver is an optional dependency, lazy-imported. Install with:
    pip install redcell[neo4j]
"""
from __future__ import annotations

import json
import time
from typing import Any

from .base import Finding, host_from_data


class Neo4jStore:
    def __init__(self, uri: str, user: str, password: str, database: str | None = None):
        try:
            from neo4j import GraphDatabase  # lazy import
        except ImportError as e:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "Neo4j support needs the 'neo4j' package. Install with: pip install redcell[neo4j]"
            ) from e
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database
        self._init_schema()

    def _session(self):
        return self._driver.session(database=self._database) if self._database else self._driver.session()

    def _init_schema(self) -> None:
        with self._session() as s:
            s.run("CREATE CONSTRAINT redcell_finding_id IF NOT EXISTS "
                  "FOR (f:Finding) REQUIRE f.id IS UNIQUE")
            s.run("MERGE (c:Counter {name:'finding'}) ON CREATE SET c.value = 0")

    def add_finding(self, agent: str, tool: str, data: dict[str, Any], summary: str) -> int:
        payload = json.dumps(data)
        created = time.time()
        host = host_from_data(data)
        with self._session() as s:
            return int(s.execute_write(self._create_finding, agent, tool, summary, payload, created, host))

    @staticmethod
    def _create_finding(tx, agent, tool, summary, payload, created, host) -> int:
        row = tx.run("MATCH (c:Counter {name:'finding'}) "
                     "SET c.value = c.value + 1 RETURN c.value AS id").single()
        fid = int(row["id"])
        tx.run(
            """
            MERGE (a:Agent {name: $agent})
            CREATE (f:Finding {id: $id, tool: $tool, summary: $summary,
                               data: $data, created_at: $created})
            MERGE (a)-[:FOUND]->(f)
            """,
            agent=agent, id=fid, tool=tool, summary=summary, data=payload, created=created,
        )
        if host:
            tx.run(
                """
                MATCH (f:Finding {id: $id})
                MERGE (h:Host {name: $host})
                MERGE (f)-[:ABOUT]->(h)
                """,
                id=fid, host=host,
            )
        return fid

    def list_findings(self, agent: str | None = None) -> list[Finding]:
        cypher = (
            "MATCH (a:Agent)-[:FOUND]->(f:Finding) "
            + ("WHERE a.name = $agent " if agent else "")
            + "RETURN f.id AS id, a.name AS agent, f.tool AS tool, f.summary AS summary, "
              "f.data AS data, f.created_at AS created_at ORDER BY f.id"
        )
        with self._session() as s:
            rows = s.run(cypher, agent=agent).data()
        return [
            Finding(
                id=int(r["id"]), agent=r["agent"], tool=r["tool"], summary=r["summary"],
                data=json.loads(r["data"]), created_at=r["created_at"],
            )
            for r in rows
        ]

    def hosts(self) -> list[str]:
        """Graph extra: all hosts any finding is about (not on the base Store)."""
        with self._session() as s:
            rows = s.run("MATCH (:Finding)-[:ABOUT]->(h:Host) RETURN DISTINCT h.name AS name "
                         "ORDER BY name").data()
        return [r["name"] for r in rows]

    def close(self) -> None:
        self._driver.close()
