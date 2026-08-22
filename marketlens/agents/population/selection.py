"""Deterministic, outcome-blind selection of a bounded Agent population."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping

from .source import FUNDAMENTAL_LABEL, TECHNICAL_LABEL, SourcePopulation


SELECTION_ALGORITHM = "sha256_keyed_strategy_stratified_selection/1.0"
STRATUM_TOKEN = {
    FUNDAMENTAL_LABEL: "fundamental",
    TECHNICAL_LABEL: "technical",
}


class PopulationSelectionError(ValueError):
    """Raised for an invalid bounded-population selection request."""


@dataclass(frozen=True)
class PopulationSelection:
    population_size: int
    seed: str
    algorithm: str
    strategy_allocation: Mapping[str, int]
    selected_agent_ids: tuple[str, ...]
    selected_by_strategy: Mapping[str, tuple[str, ...]]
    selected_agent_ids_sha256: str


def _selection_key(seed: str, strategy: str, user_id: str) -> str:
    token = STRATUM_TOKEN.get(strategy, strategy)
    return hashlib.sha256(f"{seed}|{token}|{user_id}".encode("utf-8")).hexdigest()


def _largest_remainder_allocation(
    strategy_counts: Mapping[str, int], population_size: int
) -> dict[str, int]:
    total = sum(strategy_counts.values())
    if total <= 0:
        raise PopulationSelectionError("source strategy counts are empty")
    if population_size <= 0:
        raise PopulationSelectionError("population_size must be positive")
    if population_size > total:
        raise PopulationSelectionError(
            f"population_size={population_size} exceeds source population={total}"
        )

    exact = {
        strategy: population_size * count / total
        for strategy, count in strategy_counts.items()
    }
    allocation = {strategy: math.floor(value) for strategy, value in exact.items()}
    remaining = population_size - sum(allocation.values())

    # Largest-remainder apportionment preserves the source strategy ratio as
    # closely as possible for arbitrary N. Stable strategy-name tie-breaking
    # makes the result deterministic.
    order = sorted(
        strategy_counts,
        key=lambda strategy: (-(exact[strategy] - allocation[strategy]), strategy),
    )
    for strategy in order[:remaining]:
        allocation[strategy] += 1

    for strategy, count in allocation.items():
        if count > strategy_counts[strategy]:
            raise PopulationSelectionError(
                f"strategy {strategy!r} requires {count} Agent(s), but only "
                f"{strategy_counts[strategy]} are available"
            )
    return dict(sorted(allocation.items()))


def select_population(
    source: SourcePopulation,
    *,
    population_size: int,
    seed: str,
) -> PopulationSelection:
    """Select Agents using only ``user_id``, ``strategy`` and ``seed``.

    ``user_type`` is deliberately not a selection input. It is inherited from
    whichever source personas are selected and is reported later in the
    manifest as a descriptive property of the resulting population.
    """

    if not str(seed):
        raise PopulationSelectionError("seed must be a non-empty string")

    allocation = _largest_remainder_allocation(
        source.strategy_counts, population_size
    )
    selected_by_strategy: dict[str, tuple[str, ...]] = {}

    for strategy, required in allocation.items():
        candidates = sorted(
            uid for uid, agent in source.agents.items() if agent.strategy == strategy
        )
        ranked = sorted(
            candidates,
            key=lambda uid: (_selection_key(str(seed), strategy, uid), uid),
        )
        selected_by_strategy[strategy] = tuple(sorted(ranked[:required]))

    selected = tuple(
        sorted(uid for ids in selected_by_strategy.values() for uid in ids)
    )
    if len(selected) != population_size or len(set(selected)) != population_size:
        raise PopulationSelectionError(
            "selection did not produce the requested number of unique Agents"
        )

    selected_hash = hashlib.sha256(
        json.dumps(selected, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    return PopulationSelection(
        population_size=population_size,
        seed=str(seed),
        algorithm=SELECTION_ALGORITHM,
        strategy_allocation=allocation,
        selected_agent_ids=selected,
        selected_by_strategy={
            strategy: tuple(ids) for strategy, ids in sorted(selected_by_strategy.items())
        },
        selected_agent_ids_sha256=selected_hash,
    )
