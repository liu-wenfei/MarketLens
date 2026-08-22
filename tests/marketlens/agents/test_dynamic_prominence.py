from __future__ import annotations

import networkx as nx

from marketlens.agents.social.graph import BuiltSocialGraph
from marketlens.agents.social.prominence import (
    deterministic_degree_ranking,
    make_prominence_snapshot,
)


def _built(graph: nx.Graph) -> BuiltSocialGraph:
    ids = tuple(sorted(str(x) for x in graph.nodes()))
    return BuiltSocialGraph(
        graph=graph,
        runtime_db="/tmp/dev.db",
        runtime_db_sha256_before="same",
        runtime_db_sha256_after="same",
        population_ids=ids,
        population_ids_sha256="ids",
        graph_start_date="2023-01-01",
        history_cutoff="2023-06-14",
        similarity_threshold=0.1,
        time_decay_factor=0.05,
        n_nodes=graph.number_of_nodes(),
        n_edges=graph.number_of_edges(),
        graph_sha256="graph",
    )


def test_degree_ties_are_user_id_ascending():
    g = nx.Graph()
    # 1, 2 and 3 all degree 2; insertion order is deliberately reversed.
    g.add_nodes_from(["3", "2", "1", "9"])
    g.add_edges_from([("1", "9"), ("1", "2"), ("2", "3"), ("3", "9")])

    ranking = deterministic_degree_ranking(g)

    assert ranking[:3] == [("1", 2), ("2", 2), ("3", 2)]


def test_top_n_comes_from_actual_graph_size_floor_rule():
    g = nx.Graph()
    g.add_nodes_from(str(i) for i in range(20))
    snapshot = make_prominence_snapshot(_built(g), top_fraction=0.10)

    assert snapshot["prominence"]["actual_graph_n"] == 20
    assert snapshot["prominence"]["top_n"] == 2
    assert len(snapshot["prominence"]["top_user_ids"]) == 2


def test_prominence_is_not_user_type_or_activation_state():
    g = nx.star_graph(["center", "a", "b", "c"])
    snapshot = make_prominence_snapshot(_built(g), top_fraction=0.25)
    p = snapshot["prominence"]

    assert p["derived_from_user_type"] is False
    assert p["stable_user_type_kept_separate"] is True
    assert p["used_as_activation_input"] is False
    assert p["passed_into_agent_reasoning"] is False


def test_prominence_can_change_when_graph_changes():
    day_a = nx.Graph()
    day_a.add_nodes_from(["1", "2", "3", "4"])
    day_a.add_edges_from([("1", "2"), ("1", "3"), ("1", "4")])

    day_b = nx.Graph()
    day_b.add_nodes_from(["1", "2", "3", "4"])
    day_b.add_edges_from([("4", "1"), ("4", "2"), ("4", "3")])

    a = make_prominence_snapshot(_built(day_a), top_fraction=0.25)
    b = make_prominence_snapshot(_built(day_b), top_fraction=0.25)

    assert a["prominence"]["top_user_ids"] == ["1"]
    assert b["prominence"]["top_user_ids"] == ["4"]


def test_cutoff_tie_is_logged():
    g = nx.Graph()
    g.add_nodes_from(["1", "2", "3", "4"])
    g.add_edges_from([("1", "4"), ("2", "4"), ("3", "4")])

    # Top 50% => two users. User 4 is degree 3; users 1/2/3 tie at degree 1.
    snapshot = make_prominence_snapshot(_built(g), top_fraction=0.50)
    p = snapshot["prominence"]

    assert p["top_user_ids"] == ["4", "1"]
    assert p["cutoff_degree"] == 1
    assert p["cutoff_tie_count"] == 3
    assert p["cutoff_tied_user_ids"] == ["1", "2", "3"]
