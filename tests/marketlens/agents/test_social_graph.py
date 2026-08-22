from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

import networkx as nx
import pytest

from marketlens.agents.social import graph as graph_module
from marketlens.agents.social.graph import build_bounded_social_graph, graph_digest


def _db(tmp_path: Path, ids=("3", "1", "2")) -> Path:
    path = tmp_path / "population.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE Profiles (user_id TEXT PRIMARY KEY, user_type TEXT)")
        conn.executemany(
            "INSERT INTO Profiles(user_id, user_type) VALUES (?, ?)",
            [(uid, "ordinary") for uid in ids],
        )
        conn.commit()
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wrapper_reuses_inherited_builder_with_explicit_cutoff_and_no_save(
    monkeypatch, tmp_path
):
    db = _db(tmp_path)
    seen = {}

    def fake_build_graph_new(**kwargs):
        seen.update(kwargs)
        g = nx.Graph()
        g.add_nodes_from(["1", "2", "3"])
        g.add_edge("1", "2", weight=0.3)
        return g

    monkeypatch.setattr(graph_module.simulation, "build_graph_new", fake_build_graph_new)

    before = _sha(db)
    built = build_bounded_social_graph(
        runtime_db=db,
        history_cutoff="2023-06-14",
    )
    after = _sha(db)

    assert seen["db_path"] == str(db.resolve())
    assert seen["start_date"] == "2023-01-01"
    assert seen["end_date"] == "2023-06-14"
    assert seen["similarity_threshold"] == 0.1
    assert seen["time_decay_factor"] == 0.05
    assert seen["save"] is False
    assert before == after
    assert built.runtime_db_sha256_before == built.runtime_db_sha256_after
    assert built.population_ids == ("1", "2", "3")
    assert built.n_nodes == 3
    assert built.n_edges == 1
    assert built.participant_data_used is False
    assert built.llm_backend_used is False


def test_graph_membership_must_equal_bounded_profiles(monkeypatch, tmp_path):
    db = _db(tmp_path)

    def fake_build_graph_new(**_kwargs):
        g = nx.Graph()
        g.add_nodes_from(["1", "2", "999"])
        return g

    monkeypatch.setattr(graph_module.simulation, "build_graph_new", fake_build_graph_new)

    with pytest.raises(ValueError, match="graph membership"):
        build_bounded_social_graph(
            runtime_db=db,
            history_cutoff="2023-06-14",
        )


def test_invalid_cutoff_fails_before_builder(monkeypatch, tmp_path):
    db = _db(tmp_path)
    called = False

    def fake_build_graph_new(**_kwargs):
        nonlocal called
        called = True
        return nx.Graph()

    monkeypatch.setattr(graph_module.simulation, "build_graph_new", fake_build_graph_new)

    with pytest.raises(ValueError, match="history_cutoff"):
        build_bounded_social_graph(
            runtime_db=db,
            graph_start_date="2023-06-15",
            history_cutoff="2023-06-14",
        )
    assert called is False


def test_graph_digest_is_insertion_order_independent():
    a = nx.Graph()
    a.add_nodes_from(["1", "2", "3"])
    a.add_edge("1", "2", weight=0.25)
    a.add_edge("2", "3", weight=0.50)

    b = nx.Graph()
    b.add_nodes_from(["3", "2", "1"])
    b.add_edge("3", "2", weight=0.50)
    b.add_edge("2", "1", weight=0.25)

    assert graph_digest(a) == graph_digest(b)
