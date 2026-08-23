"""Zero-LLM Phase 10 N20/N30 activation adequacy over the frozen horizon."""

from __future__ import annotations

from dataclasses import dataclass
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping

from marketlens.agents.activation.policy import ActivationPolicy
from marketlens.agents.activation.profiles import load_activation_profiles
from marketlens.agents.activation.sampler import sample_activation
from marketlens.agents.activation.state import ActivationState
from marketlens.experiment.protocol import load_protocol, validate_protocol


class FormalHorizonError(RuntimeError):
    pass


@dataclass(frozen=True)
class CandidateAdequacy:
    population_size: int
    sufficient: bool
    critical_any_zero_trajectories: int
    critical_any_zero_frequency: float
    critical_date_mean_active: Mapping[str, float]
    overall_mean_active: float
    overall_zero_active_frequency: float
    minimum_critical_mean_active: float
    n_seeds: int
    n_world_ticks: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "population_size": self.population_size,
            "sufficient": self.sufficient,
            "critical_any_zero_trajectories": self.critical_any_zero_trajectories,
            "critical_any_zero_frequency": self.critical_any_zero_frequency,
            "critical_date_mean_active": dict(self.critical_date_mean_active),
            "overall_mean_active": self.overall_mean_active,
            "overall_zero_active_frequency": self.overall_zero_active_frequency,
            "minimum_critical_mean_active": self.minimum_critical_mean_active,
            "n_seeds": self.n_seeds,
            "n_world_ticks": self.n_world_ticks,
        }


def formal_horizon_seeds(protocol: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    data = validate_protocol(protocol) if protocol is not None else load_protocol()
    rule = data["population"]["selection_rule"]
    count = int(rule["activation_seed_count"])
    prefix = str(rule["activation_seed_prefix"])
    return tuple(f"{prefix}{index:03d}" for index in range(count))


def evaluate_candidate(
    *,
    runtime_db: str | Path,
    population_size: int,
    protocol: Mapping[str, Any] | None = None,
    seeds: Iterable[str] | None = None,
) -> CandidateAdequacy:
    data = validate_protocol(protocol) if protocol is not None else load_protocol()
    if population_size not in data["population"]["candidates"]:
        raise FormalHorizonError(f"unsupported Phase 10 population candidate N{population_size}")

    profiles = tuple(load_activation_profiles(runtime_db))
    if len(profiles) != population_size:
        raise FormalHorizonError(
            f"N{population_size} runtime fixture contains {len(profiles)} activation profiles"
        )

    seed_values = tuple(seeds) if seeds is not None else formal_horizon_seeds(data)
    if len(seed_values) != int(data["population"]["selection_rule"]["activation_seed_count"]):
        raise FormalHorizonError("formal-horizon gate must retain the full predeclared seed set")
    if len(set(seed_values)) != len(seed_values):
        raise FormalHorizonError("activation seeds must be unique")

    timeline = data["timeline"]
    critical_dates = tuple(data["participant_critical_dates"])
    critical_ticks = {
        row["agent_world_date"]: int(row["world_tick"])
        for row in timeline
        if row["agent_world_date"] in critical_dates
    }
    if tuple(critical_ticks) != critical_dates:
        raise FormalHorizonError("critical-date mapping drifted")

    policy = ActivationPolicy()
    all_counts: list[int] = []
    critical_counts: dict[str, list[int]] = {value: [] for value in critical_dates}
    trajectories_with_critical_zero = 0

    for seed in seed_values:
        state: ActivationState | None = None
        counts_by_tick: list[int] = []
        for row in timeline:
            tick = int(row["world_tick"])
            batch = sample_activation(
                profiles,
                policy=policy,
                state=state,
                seed=seed,
                step=tick,
            )
            count = len(batch.active_agent_ids)
            counts_by_tick.append(count)
            all_counts.append(count)
            state = batch.next_state

        critical_values = [counts_by_tick[critical_ticks[value]] for value in critical_dates]
        if any(value == 0 for value in critical_values):
            trajectories_with_critical_zero += 1
        for current_date, value in zip(critical_dates, critical_values):
            critical_counts[current_date].append(value)

    means = {
        current_date: statistics.fmean(values)
        for current_date, values in critical_counts.items()
    }
    min_mean = min(means.values())
    rule = data["population"]["selection_rule"]
    max_zero = int(rule["critical_date_any_zero_max_trajectories"])
    min_required_mean = float(rule["critical_date_min_mean_active_agents"])
    sufficient = (
        trajectories_with_critical_zero <= max_zero
        and min_mean >= min_required_mean
    )

    return CandidateAdequacy(
        population_size=population_size,
        sufficient=sufficient,
        critical_any_zero_trajectories=trajectories_with_critical_zero,
        critical_any_zero_frequency=trajectories_with_critical_zero / len(seed_values),
        critical_date_mean_active=means,
        overall_mean_active=statistics.fmean(all_counts),
        overall_zero_active_frequency=sum(value == 0 for value in all_counts) / len(all_counts),
        minimum_critical_mean_active=min_mean,
        n_seeds=len(seed_values),
        n_world_ticks=len(timeline),
    )


def decide_population(n20: CandidateAdequacy, n30: CandidateAdequacy) -> dict[str, Any]:
    if n20.population_size != 20 or n30.population_size != 30:
        raise FormalHorizonError("decision requires N20 and N30 results")
    if n20.sufficient:
        return {
            "decision": "SELECT_N20",
            "final_n": 20,
            "requires_n30_real_validation": False,
            "reason": "N20 satisfies the predeclared formal-horizon adequacy gates; parsimony applies.",
        }
    if n30.sufficient:
        return {
            "decision": "N30_REQUIRES_NARROW_REAL_VALIDATION",
            "final_n": None,
            "requires_n30_real_validation": True,
            "recommended_validation_date": "2023-06-20",
            "reason": "N20 fails a predeclared adequacy gate while N30 passes; one narrow real-backend N30 validation is required before freeze.",
        }
    return {
        "decision": "NO_CANDIDATE_SUFFICIENT",
        "final_n": None,
        "requires_n30_real_validation": False,
        "reason": "Neither N20 nor N30 satisfies the predeclared formal-horizon adequacy gates.",
    }
