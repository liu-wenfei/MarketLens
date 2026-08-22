"""Thin safety wrapper around TwinMarket's inherited social-graph builder."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

import networkx as nx

import simulation


DEFAULT_GRAPH_START_DATE = "2023-01-01"
DEFAULT_SIMILARITY_THRESHOLD = 0.1
DEFAULT_TIME_DECAY_FACTOR = 0.05
GRAPH_DIGEST_ALGORITHM = "marketlens_graph_topology_weight_sha256/1.0"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalise_user_id(value: Any) -> str:
    return str(value)


def _validate_iso_date(value: str, *, field: str) -> str:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an ISO date YYYY-MM-DD: {value!r}") from exc
    return value


def _read_profile_ids(runtime_db: Path) -> tuple[str, ...]:
    with sqlite3.connect(str(runtime_db)) as conn:
        rows = conn.execute("SELECT DISTINCT user_id FROM Profiles").fetchall()
    ids = tuple(sorted({_normalise_user_id(row[0]) for row in rows}))
    if not ids:
        raise ValueError("bounded runtime database contains no Profiles user IDs")
    return ids


def _stable_weight(value: Any) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), 12)
    except (TypeError, ValueError):
        return str(value)


def graph_digest(graph: nx.Graph) -> str:
    """Digest graph membership, topology and inherited edge weights deterministically."""
    nodes = sorted(_normalise_user_id(node) for node in graph.nodes())
    edges = []
    for left, right, attrs in graph.edges(data=True):
        a, b = sorted((_normalise_user_id(left), _normalise_user_id(right)))
        edges.append(
            {
                "u": a,
                "v": b,
                "weight": _stable_weight(attrs.get("weight")),
            }
        )
    edges.sort(key=lambda row: (row["u"], row["v"], repr(row["weight"])))
    payload = {
        "algorithm": GRAPH_DIGEST_ALGORITHM,
        "nodes": nodes,
        "edges": edges,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class BuiltSocialGraph:
    """Graph plus the audit metadata required by the Phase 6 contract."""

    graph: nx.Graph
    runtime_db: str
    runtime_db_sha256_before: str
    runtime_db_sha256_after: str
    population_ids: tuple[str, ...]
    population_ids_sha256: str
    graph_start_date: str
    history_cutoff: str
    similarity_threshold: float
    time_decay_factor: float
    n_nodes: int
    n_edges: int
    graph_sha256: str
    inherited_builder: str = "simulation.build_graph_new"
    inherited_graph_save_enabled: bool = False
    participant_data_used: bool = False
    llm_backend_used: bool = False

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "runtime_db": self.runtime_db,
            "runtime_db_sha256_before": self.runtime_db_sha256_before,
            "runtime_db_sha256_after": self.runtime_db_sha256_after,
            "runtime_db_unchanged": (
                self.runtime_db_sha256_before == self.runtime_db_sha256_after
            ),
            "population_size": len(self.population_ids),
            "population_ids_sha256": self.population_ids_sha256,
            "graph_start_date": self.graph_start_date,
            "history_cutoff": self.history_cutoff,
            "similarity_threshold": self.similarity_threshold,
            "time_decay_factor": self.time_decay_factor,
            "n_nodes": self.n_nodes,
            "n_edges": self.n_edges,
            "graph_sha256": self.graph_sha256,
            "inherited_builder": self.inherited_builder,
            "inherited_graph_save_enabled": self.inherited_graph_save_enabled,
            "participant_data_used": self.participant_data_used,
            "llm_backend_used": self.llm_backend_used,
        }


def _ids_digest(ids: tuple[str, ...]) -> str:
    raw = "\n".join(ids).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_bounded_social_graph(
    *,
    runtime_db: str | Path,
    history_cutoff: str,
    graph_start_date: str = DEFAULT_GRAPH_START_DATE,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    time_decay_factor: float = DEFAULT_TIME_DECAY_FACTOR,
) -> BuiltSocialGraph:
    """Build TwinMarket's graph under MarketLens' bounded Phase 6 controls.

    This function intentionally does not call `simulation.init_simulation()` because
    that would also activate unrelated market/news/forum/reasoning behaviour.
    """
    db = Path(runtime_db).expanduser().resolve()
    if not db.is_file():
        raise FileNotFoundError(f"bounded runtime database not found: {db}")

    start = _validate_iso_date(graph_start_date, field="graph_start_date")
    cutoff = _validate_iso_date(history_cutoff, field="history_cutoff")
    if date.fromisoformat(cutoff) < date.fromisoformat(start):
        raise ValueError("history_cutoff must be on or after graph_start_date")
    if not (0.0 <= float(similarity_threshold) <= 1.0):
        raise ValueError("similarity_threshold must be within [0, 1]")
    if float(time_decay_factor) < 0.0:
        raise ValueError("time_decay_factor must be >= 0")

    population_ids = _read_profile_ids(db)
    before = _sha256_file(db)

    # Reuse inherited TwinMarket behaviour. `save=False` is a deliberate MarketLens
    # boundary so a graph audit does not write inherited `data/graph/*.pkl` artifacts.
    graph = simulation.build_graph_new(
        similarity_threshold=float(similarity_threshold),
        time_decay_factor=float(time_decay_factor),
        db_path=str(db),
        start_date=start,
        end_date=cutoff,
        save_name="marketlens_phase06_unsaved",
        save=False,
    )
    if not isinstance(graph, nx.Graph):
        raise TypeError(
            "simulation.build_graph_new must return a networkx.Graph-compatible object"
        )

    after = _sha256_file(db)
    if after != before:
        raise RuntimeError(
            "bounded runtime database changed while constructing the social graph"
        )

    graph_ids = tuple(sorted({_normalise_user_id(node) for node in graph.nodes()}))
    if graph_ids != population_ids:
        missing = sorted(set(population_ids) - set(graph_ids))
        unexpected = sorted(set(graph_ids) - set(population_ids))
        raise ValueError(
            "graph membership does not exactly match bounded Profiles population; "
            f"missing={missing}, unexpected={unexpected}"
        )

    return BuiltSocialGraph(
        graph=graph,
        runtime_db=str(db),
        runtime_db_sha256_before=before,
        runtime_db_sha256_after=after,
        population_ids=population_ids,
        population_ids_sha256=_ids_digest(population_ids),
        graph_start_date=start,
        history_cutoff=cutoff,
        similarity_threshold=float(similarity_threshold),
        time_decay_factor=float(time_decay_factor),
        n_nodes=graph.number_of_nodes(),
        n_edges=graph.number_of_edges(),
        graph_sha256=graph_digest(graph),
    )
