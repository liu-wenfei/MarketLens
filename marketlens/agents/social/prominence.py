"""Deterministic MarketLens wrapper for TwinMarket's degree prominence concept."""

from __future__ import annotations

from math import floor
from typing import Any

import networkx as nx

from .graph import BuiltSocialGraph


DEFAULT_TOP_FRACTION = 0.10
RANKING_ALGORITHM = "unweighted_degree_desc_user_id_asc/1.0"


def _uid(value: Any) -> str:
    return str(value)


def deterministic_degree_ranking(graph: nx.Graph) -> list[tuple[str, int]]:
    """Return inherited unweighted degree ranking with an explicit tie-break."""
    rows = [(_uid(node), int(degree)) for node, degree in graph.degree()]
    rows.sort(key=lambda row: (-row[1], row[0]))
    return rows


def make_prominence_snapshot(
    built: BuiltSocialGraph,
    *,
    top_fraction: float = DEFAULT_TOP_FRACTION,
) -> dict[str, Any]:
    """Create an audit snapshot without feeding prominence into Agent reasoning."""
    fraction = float(top_fraction)
    if not (0.0 <= fraction <= 1.0):
        raise ValueError("top_fraction must be within [0, 1]")

    ranking = deterministic_degree_ranking(built.graph)
    actual_n = built.graph.number_of_nodes()
    top_n = floor(actual_n * fraction)
    top_rows = ranking[:top_n]
    top_ids = [uid for uid, _degree in top_rows]

    cutoff_degree = top_rows[-1][1] if top_rows else None
    tied_at_cutoff = (
        [uid for uid, degree in ranking if degree == cutoff_degree]
        if cutoff_degree is not None
        else []
    )

    degree_distribution: dict[str, int] = {}
    for _uid_value, degree in ranking:
        key = str(degree)
        degree_distribution[key] = degree_distribution.get(key, 0) + 1

    return {
        "phase": "6B",
        "status": "DEVELOPMENT / GRAPH-PROMINENCE SNAPSHOT / NOT FORMAL EVIDENCE",
        "graph": built.to_audit_dict(),
        "prominence": {
            "definition": "dynamic graph prominence; not credibility or correctness",
            "metric": "unweighted_degree",
            "ranking_algorithm": RANKING_ALGORITHM,
            "derived_from_user_type": False,
            "stable_user_type_kept_separate": True,
            "used_as_activation_input": False,
            "passed_into_agent_reasoning": False,
            "top_fraction": fraction,
            "actual_graph_n": actual_n,
            "top_n": top_n,
            "top_user_ids": top_ids,
            "cutoff_degree": cutoff_degree,
            "cutoff_tie_count": len(tied_at_cutoff),
            "cutoff_tied_user_ids": tied_at_cutoff,
            "degree_distribution": degree_distribution,
            "degree_ranking": [
                {"user_id": uid, "degree": degree} for uid, degree in ranking
            ],
        },
        "scope": {
            "news_processing_enabled": False,
            "forum_propagation_enabled": False,
            "participant_data_used": False,
            "llm_backend_used": False,
        },
    }
