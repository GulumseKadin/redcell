"""Tests for the Faz 4 shared-state layer: factory, protocol, graph modeling.

The Neo4j store is exercised with a fake driver that records Cypher, so no
Neo4j server (or the optional driver package) is needed.
"""
from __future__ import annotations

import pytest

from redcell.config import Settings, StoreBackend
from redcell.state import FindingStore, Store, build_store, host_from_data
from redcell.state.neo4j_store import Neo4jStore


# -- factory + protocol ------------------------------------------------------

def test_factory_defaults_to_sqlite(tmp_path):
    s = build_store(Settings(workdir=str(tmp_path)))
    assert isinstance(s, FindingStore)
    assert isinstance(s, Store)  # runtime_checkable protocol
    s.close()


def test_neo4j_backend_requires_password():
    with pytest.raises(RuntimeError):
        build_store(Settings(store=StoreBackend.NEO4J, neo4j_password=None))


# -- target extraction for graph edges --------------------------------------

def test_host_from_data_variants():
    assert host_from_data({"target": "http://10.0.5.42:8080/x"}) == "10.0.5.42"
    assert host_from_data({"arguments": {"url": "https://app.test.example/a"}}) == "app.test.example"
    assert host_from_data({"status": 200}) is None
    assert host_from_data("nope") is None


# -- Neo4j graph modeling via a fake driver ----------------------------------

class FakeResult:
    def __init__(self, single=None, data=None):
        self._single = single
        self._data = data or []

    def single(self):
        return self._single

    def data(self):
        return self._data


class FakeSession:
    """Acts as both session and write-transaction; records every query."""

    def __init__(self, recorder, counter, rows):
        self.recorder = recorder
        self.counter = counter
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, cypher, **params):
        self.recorder.append((cypher, params))
        if "c.value + 1" in cypher and "RETURN" in cypher:
            self.counter[0] += 1
            return FakeResult(single={"id": self.counter[0]})
        if cypher.strip().startswith("MATCH (a:Agent)-[:FOUND]"):
            return FakeResult(data=self.rows)
        return FakeResult()

    def execute_write(self, fn, *args):
        return fn(self, *args)


class FakeDriver:
    def __init__(self):
        self.recorder = []
        self.counter = [0]
        self.rows = []

    def session(self, **kw):
        return FakeSession(self.recorder, self.counter, self.rows)

    def close(self):
        pass


def _store_with_fake():
    store = Neo4jStore.__new__(Neo4jStore)   # bypass real driver connection
    store._driver = FakeDriver()
    store._database = None
    return store


def test_add_finding_increments_id_and_links_host():
    store = _store_with_fake()
    fid1 = store.add_finding("recon", "http_fingerprint", {"target": "10.0.5.42"}, "ok")
    fid2 = store.add_finding("recon", "http_fingerprint", {"status": 200}, "no host")
    assert (fid1, fid2) == (1, 2)

    queries = " ".join(c for c, _ in store._driver.recorder)
    assert "MERGE (a:Agent {name: $agent})" in queries
    assert "CREATE (f:Finding" in queries
    assert "MERGE (a)-[:FOUND]->(f)" in queries
    # host linked for the first finding only (second had no derivable target)
    about = [p for c, p in store._driver.recorder if "ABOUT" in c]
    assert len(about) == 1 and about[0]["host"] == "10.0.5.42"


def test_list_findings_filters_and_parses():
    store = _store_with_fake()
    store._driver.rows = [
        {"id": 1, "agent": "recon", "tool": "http_fingerprint",
         "summary": "ok", "data": "{\"target\": \"10.0.5.42\"}", "created_at": 1.0},
    ]
    out = store.list_findings(agent="recon")
    assert len(out) == 1 and out[0].agent == "recon" and out[0].data["target"] == "10.0.5.42"
    # the WHERE clause is present only when an agent filter is passed
    list_cypher = [c for c, _ in store._driver.recorder if "RETURN f.id" in c][0]
    assert "WHERE a.name = $agent" in list_cypher
