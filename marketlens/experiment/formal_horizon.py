"""Zero-LLM Phase 10 timing/population adequacy over the frozen horizon."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
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
class WarmUpAdequacy:
    calendar_days: int
    visible_date: str
    sufficient: bool
    open_ticks_before_entry: int
    closed_ticks_before_entry: int
    visible_date_open: bool
    news_coverage_complete: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "calendar_days": self.calendar_days,
            "visible_date": self.visible_date,
            "sufficient": self.sufficient,
            "open_ticks_before_entry": self.open_ticks_before_entry,
            "closed_ticks_before_entry": self.closed_ticks_before_entry,
            "visible_date_open": self.visible_date_open,
            "news_coverage_complete": self.news_coverage_complete,
        }


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


def evaluate_warm_up_candidates(
    *,
    protocol: Mapping[str, Any] | None = None,
    trading_open_dates: Iterable[str],
    news_dates: Iterable[str],
) -> tuple[WarmUpAdequacy, ...]:
    data = validate_protocol(protocol) if protocol is not None else load_protocol()
    init_date = date.fromisoformat(data["world"]["initialization_date"])
    rule = data["warm_up"]["selection_rule"]
    open_set = set(trading_open_dates)
    news_set = set(news_dates)
    results: list[WarmUpAdequacy] = []

    for days in rule["candidate_calendar_days"]:
        visible_date = init_date + timedelta(days=int(days))
        pre_roll_dates = [init_date + timedelta(days=index) for index in range(int(days))]
        open_count = sum(value.isoformat() in open_set for value in pre_roll_dates)
        closed_count = len(pre_roll_dates) - open_count
        visible_open = visible_date.isoformat() in open_set
        news_complete = all(value.isoformat() in news_set for value in pre_roll_dates + [visible_date])
        sufficient = (
            open_count >= int(rule["minimum_episode_local_open_ticks_before_entry"])
            and closed_count >= int(rule["minimum_episode_local_closed_ticks_before_entry"])
            and (visible_open if rule["participant_visible_start_must_be_open"] else True)
            and (news_complete if rule["background_news_must_cover_all_pre_roll_dates"] else True)
        )
        results.append(
            WarmUpAdequacy(
                calendar_days=int(days),
                visible_date=visible_date.isoformat(),
                sufficient=sufficient,
                open_ticks_before_entry=open_count,
                closed_ticks_before_entry=closed_count,
                visible_date_open=visible_open,
                news_coverage_complete=news_complete,
            )
        )
    return tuple(results)


def select_warm_up(results: Iterable[WarmUpAdequacy], protocol: Mapping[str, Any] | None = None) -> WarmUpAdequacy:
    data = validate_protocol(protocol) if protocol is not None else load_protocol()
    candidates = tuple(results)
    sufficient = tuple(value for value in candidates if value.sufficient)
    if not sufficient:
        raise FormalHorizonError("no warm-up candidate satisfies the predeclared structural gate")
    selected = min(sufficient, key=lambda value: value.calendar_days)
    if data["warm_up"]["selection_rule"]["choose_smallest_sufficient_candidate"] is not True:
        raise FormalHorizonError("warm-up selection rule drifted")
    if selected.calendar_days != int(data["warm_up"]["selected_calendar_days"]):
        raise FormalHorizonError(
            f"protocol freezes W{data['warm_up']['selected_calendar_days']} but structural gate selects W{selected.calendar_days}"
        )
    if selected.visible_date != data["world"]["participant_visible_start_date"]:
        raise FormalHorizonError("selected warm-up visible date does not match T_visible")
    return selected


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
        raise FormalHorizonError(f"N{population_size} runtime fixture contains {len(profiles)} activation profiles")

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
            batch = sample_activation(profiles, policy=policy, state=state, seed=seed, step=tick)
            count = len(batch.active_agent_ids)
            counts_by_tick.append(count)
            all_counts.append(count)
            state = batch.next_state

        critical_values = [counts_by_tick[critical_ticks[value]] for value in critical_dates]
        if any(value == 0 for value in critical_values):
            trajectories_with_critical_zero += 1
        for current_date, value in zip(critical_dates, critical_values):
            critical_counts[current_date].append(value)

    means = {current_date: statistics.fmean(values) for current_date, values in critical_counts.items()}
    min_mean = min(means.values())
    rule = data["population"]["selection_rule"]
    max_zero = int(rule["critical_date_any_zero_max_trajectories"])
    min_required_mean = float(rule["critical_date_min_mean_active_agents"])
    sufficient = trajectories_with_critical_zero <= max_zero and min_mean >= min_required_mean

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


def decide_population(
    n20: CandidateAdequacy,
    n30: CandidateAdequacy,
    *,
    n30_real_backend_validated: bool = False,
) -> dict[str, Any]:
    """Apply the predeclared N20/N30 rule without reopening population selection.

    Protocol v1.1 records that the one permitted bounded N30 real-backend
    validation has already PASSed.  The exact-horizon zero-LLM rerun therefore
    selects N30 only when N20 fails, N30 passes, and that prior engineering gate
    is explicitly supplied as validated.
    """
    if n20.population_size != 20 or n30.population_size != 30:
        raise FormalHorizonError("decision requires N20 and N30 results")
    if n20.sufficient:
        return {
            "decision": "SELECT_N20",
            "final_n": 20,
            "requires_n30_real_validation": False,
            "reason": "N20 satisfies the predeclared formal-horizon adequacy gates; parsimony applies.",
        }
    if n30.sufficient and n30_real_backend_validated:
        return {
            "decision": "SELECT_N30",
            "final_n": 30,
            "requires_n30_real_validation": False,
            "reason": "N20 fails the unchanged exact-horizon adequacy gate, N30 passes, and the single predeclared bounded N30 real-backend validation has already PASSed.",
        }
    if n30.sufficient:
        return {
            "decision": "N30_REQUIRES_NARROW_REAL_VALIDATION",
            "final_n": None,
            "requires_n30_real_validation": True,
            "recommended_validation_dates": ["2023-06-15", "2023-06-16", "2023-06-17"],
            "reason": "N20 fails a predeclared adequacy gate while N30 passes; the single bounded real-backend N30 validation is required before freeze.",
        }
    return {
        "decision": "NO_CANDIDATE_SUFFICIENT",
        "final_n": None,
        "requires_n30_real_validation": False,
        "reason": "Neither N20 nor N30 satisfies the predeclared formal-horizon adequacy gates.",
    }
