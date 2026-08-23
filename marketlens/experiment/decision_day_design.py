"""Zero-LLM decision-day design impact analysis for MarketLens Phase 10.

This module does not alter the frozen protocol. It compares behavioural-decision
sampling designs using deterministic calendar mapping and the inherited Phase 4
activation process only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import statistics
from pathlib import Path
from typing import Any, Iterable, Sequence

from marketlens.agents.activation.policy import ActivationPolicy
from marketlens.agents.activation.profiles import load_activation_profiles
from marketlens.agents.activation.sampler import sample_activation
from marketlens.agents.activation.state import ActivationState


DECISION_DAY_CANDIDATES: tuple[int, ...] = (0, 2, 4, 7, 9, 11)
SYMMETRIC_DYNAMIC_CANDIDATES: tuple[int, ...] = (7, 9, 11)
FORMAL_JUDGEMENT_EVENTS = 5
FORMAL_JUDGEMENT_DATES = 3


class DecisionDayDesignError(RuntimeError):
    pass


def calendar_dates(start: str, end: str) -> tuple[str, ...]:
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    if last < first:
        raise DecisionDayDesignError("end date precedes start date")
    return tuple((first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1))


def first_open_dates(open_dates: Iterable[str], *, start: str, count: int) -> tuple[str, ...]:
    if count <= 0:
        return tuple()
    values = tuple(sorted(value for value in set(open_dates) if value >= start))
    if len(values) < count:
        raise DecisionDayDesignError(f"need {count} OPEN dates from {start}, found {len(values)}")
    return values[:count]


def evenly_spaced_indices(total_open_dates: int, decision_days: int) -> tuple[int, ...]:
    """Endpoint-preserving, approximately even, outcome-agnostic sampling."""
    if decision_days == 0:
        return tuple()
    if decision_days < 0 or decision_days > total_open_dates:
        raise DecisionDayDesignError("decision_days must be between 0 and total_open_dates")
    if decision_days == 1:
        return (0,)
    last = total_open_dates - 1
    indices = tuple(round(i * last / (decision_days - 1)) for i in range(decision_days))
    if len(set(indices)) != decision_days:
        raise DecisionDayDesignError("even-spacing rule produced duplicate indices")
    return indices


@dataclass(frozen=True)
class CadenceCandidate:
    decision_days: int
    selected_indices: tuple[int, ...]
    selected_dates: tuple[str, ...]
    formal_anchor_indices: tuple[int, int, int]
    formal_anchor_dates: tuple[str, str, str]
    formal_anchor_coverage: int
    correction_anchor_included: bool
    phase1_intermediate_points: int
    phase2_intermediate_points: int
    symmetric_intermediate_coverage: bool
    max_gap_open_transitions: int | None
    mean_gap_open_transitions: float | None
    unobserved_open_states: int
    decision_fraction: float
    participant_response_events: int
    resolution_class: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_days": self.decision_days,
            "selected_indices": list(self.selected_indices),
            "selected_dates": list(self.selected_dates),
            "formal_anchor_indices": list(self.formal_anchor_indices),
            "formal_anchor_dates": list(self.formal_anchor_dates),
            "formal_anchor_coverage": self.formal_anchor_coverage,
            "correction_anchor_included": self.correction_anchor_included,
            "phase1_intermediate_points": self.phase1_intermediate_points,
            "phase2_intermediate_points": self.phase2_intermediate_points,
            "symmetric_intermediate_coverage": self.symmetric_intermediate_coverage,
            "max_gap_open_transitions": self.max_gap_open_transitions,
            "mean_gap_open_transitions": self.mean_gap_open_transitions,
            "unobserved_open_states": self.unobserved_open_states,
            "decision_fraction": self.decision_fraction,
            "participant_response_events": self.participant_response_events,
            "resolution_class": self.resolution_class,
        }


def _resolution_class(decision_days: int, correction_anchor: bool, p1: int, p2: int) -> str:
    if decision_days == 0:
        return "judgement_only_no_behaviour"
    if decision_days == 2:
        return "endpoint_only_behaviour"
    if not correction_anchor:
        return "sparse_behaviour_missing_correction_anchor"
    if p1 >= 4 and p2 >= 4:
        return "complete_open_state_behaviour"
    if p1 >= 3 and p2 >= 3:
        return "high_resolution_dynamic_behaviour"
    if p1 >= 2 and p2 >= 2:
        return "minimum_symmetric_dynamic_behaviour"
    return "limited_dynamic_behaviour"


def build_cadence_candidates(common_open_dates: Sequence[str]) -> tuple[CadenceCandidate, ...]:
    dates = tuple(common_open_dates)
    if len(dates) != 11:
        raise DecisionDayDesignError("cadence comparison requires exactly 11 common OPEN dates")
    anchors = (0, 5, 10)
    anchor_dates = (dates[0], dates[5], dates[10])
    results: list[CadenceCandidate] = []

    for count in DECISION_DAY_CANDIDATES:
        indices = evenly_spaced_indices(len(dates), count)
        selected = tuple(dates[i] for i in indices)
        gaps = tuple(b - a for a, b in zip(indices, indices[1:]))
        anchor_coverage = sum(index in indices for index in anchors)
        correction_anchor = anchors[1] in indices
        p1 = sum(anchors[0] < index < anchors[1] for index in indices)
        p2 = sum(anchors[1] < index < anchors[2] for index in indices)
        results.append(
            CadenceCandidate(
                decision_days=count,
                selected_indices=indices,
                selected_dates=selected,
                formal_anchor_indices=anchors,
                formal_anchor_dates=anchor_dates,
                formal_anchor_coverage=anchor_coverage,
                correction_anchor_included=correction_anchor,
                phase1_intermediate_points=p1,
                phase2_intermediate_points=p2,
                symmetric_intermediate_coverage=p1 == p2,
                max_gap_open_transitions=max(gaps) if gaps else None,
                mean_gap_open_transitions=statistics.fmean(gaps) if gaps else None,
                unobserved_open_states=len(dates) - count,
                decision_fraction=count / len(dates),
                participant_response_events=count + FORMAL_JUDGEMENT_EVENTS,
                resolution_class=_resolution_class(count, correction_anchor, p1, p2),
            )
        )
    return tuple(results)


@dataclass(frozen=True)
class DynamicHorizonCandidate:
    decision_days: int
    open_transitions_per_phase: int
    intermediate_points_per_phase: int
    decision_dates: tuple[str, ...]
    misinformation_date: str
    correction_date: str
    later_measurement_date: str
    end_date: str
    world_ticks: int
    visible_calendar_days: int
    visible_closed_ticks: int
    news_coverage_complete: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision_days": self.decision_days,
            "open_transitions_per_phase": self.open_transitions_per_phase,
            "intermediate_points_per_phase": self.intermediate_points_per_phase,
            "decision_dates": list(self.decision_dates),
            "misinformation_date": self.misinformation_date,
            "correction_date": self.correction_date,
            "later_measurement_date": self.later_measurement_date,
            "end_date": self.end_date,
            "world_ticks": self.world_ticks,
            "visible_calendar_days": self.visible_calendar_days,
            "visible_closed_ticks": self.visible_closed_ticks,
            "news_coverage_complete": self.news_coverage_complete,
        }


def build_dynamic_horizon_candidates(
    *,
    initialization_date: str,
    visible_start_date: str,
    open_dates: Iterable[str],
    news_dates: Iterable[str],
) -> tuple[DynamicHorizonCandidate, ...]:
    open_values = tuple(sorted(value for value in set(open_dates) if value >= visible_start_date))
    news_set = set(news_dates)
    init = date.fromisoformat(initialization_date)
    visible = date.fromisoformat(visible_start_date)
    results: list[DynamicHorizonCandidate] = []

    for decision_days in SYMMETRIC_DYNAMIC_CANDIDATES:
        transitions = (decision_days - 1) // 2
        if 1 + 2 * transitions != decision_days:
            raise DecisionDayDesignError("symmetric dynamic candidate must have odd decision-day count")
        decision_dates = open_values[:decision_days]
        if len(decision_dates) != decision_days:
            raise DecisionDayDesignError(f"not enough OPEN dates for {decision_days}-day candidate")
        correction = decision_dates[transitions]
        later = decision_dates[-1]
        end = date.fromisoformat(later)
        world_dates = tuple((init + timedelta(days=i)).isoformat() for i in range((end - init).days + 1))
        visible_dates = tuple((visible + timedelta(days=i)).isoformat() for i in range((end - visible).days + 1))
        visible_open = sum(value in set(open_values) for value in visible_dates)
        results.append(
            DynamicHorizonCandidate(
                decision_days=decision_days,
                open_transitions_per_phase=transitions,
                intermediate_points_per_phase=transitions - 1,
                decision_dates=decision_dates,
                misinformation_date=decision_dates[0],
                correction_date=correction,
                later_measurement_date=later,
                end_date=later,
                world_ticks=len(world_dates),
                visible_calendar_days=len(visible_dates),
                visible_closed_ticks=len(visible_dates) - visible_open,
                news_coverage_complete=all(value in news_set for value in world_dates),
            )
        )
    return tuple(results)


@dataclass(frozen=True)
class ActivationDescription:
    population_size: int
    n_seeds: int
    n_world_ticks: int
    decision_date_count: int
    any_zero_on_decision_dates_trajectories: int | None
    any_zero_on_decision_dates_frequency: float | None
    minimum_decision_date_mean_active: float | None
    mean_active_on_decision_dates: float | None
    overall_mean_active: float
    overall_zero_active_frequency: float
    expected_active_agent_calls_per_episode: float
    sufficient_under_phase10_gate: bool | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "population_size": self.population_size,
            "n_seeds": self.n_seeds,
            "n_world_ticks": self.n_world_ticks,
            "decision_date_count": self.decision_date_count,
            "any_zero_on_decision_dates_trajectories": self.any_zero_on_decision_dates_trajectories,
            "any_zero_on_decision_dates_frequency": self.any_zero_on_decision_dates_frequency,
            "minimum_decision_date_mean_active": self.minimum_decision_date_mean_active,
            "mean_active_on_decision_dates": self.mean_active_on_decision_dates,
            "overall_mean_active": self.overall_mean_active,
            "overall_zero_active_frequency": self.overall_zero_active_frequency,
            "expected_active_agent_calls_per_episode": self.expected_active_agent_calls_per_episode,
            "sufficient_under_phase10_gate": self.sufficient_under_phase10_gate,
        }


def evaluate_activation_design(
    *,
    runtime_db: str | Path,
    population_size: int,
    world_dates: Sequence[str],
    decision_dates: Sequence[str],
    seeds: Sequence[str],
    max_zero_trajectories: int = 5,
    minimum_mean_active: float = 3.0,
) -> ActivationDescription:
    profiles = tuple(load_activation_profiles(runtime_db))
    if len(profiles) != population_size:
        raise DecisionDayDesignError(
            f"N{population_size} runtime fixture contains {len(profiles)} activation profiles"
        )
    if not seeds or len(set(seeds)) != len(seeds):
        raise DecisionDayDesignError("activation seeds must be non-empty and unique")

    date_to_tick = {value: index for index, value in enumerate(world_dates)}
    if any(value not in date_to_tick for value in decision_dates):
        raise DecisionDayDesignError("decision date lies outside world horizon")

    policy = ActivationPolicy()
    all_counts: list[int] = []
    decision_counts: dict[str, list[int]] = {value: [] for value in decision_dates}
    any_zero = 0

    for seed in seeds:
        state: ActivationState | None = None
        counts: list[int] = []
        for tick, _current_date in enumerate(world_dates):
            batch = sample_activation(profiles, policy=policy, state=state, seed=seed, step=tick)
            count = len(batch.active_agent_ids)
            counts.append(count)
            all_counts.append(count)
            state = batch.next_state
        if decision_dates:
            selected = [counts[date_to_tick[value]] for value in decision_dates]
            if any(value == 0 for value in selected):
                any_zero += 1
            for current_date, value in zip(decision_dates, selected):
                decision_counts[current_date].append(value)

    overall_mean = statistics.fmean(all_counts)
    if decision_dates:
        means = [statistics.fmean(values) for values in decision_counts.values()]
        min_mean = min(means)
        mean_decision = statistics.fmean(means)
        sufficient: bool | None = any_zero <= max_zero_trajectories and min_mean >= minimum_mean_active
        any_zero_frequency: float | None = any_zero / len(seeds)
    else:
        min_mean = None
        mean_decision = None
        sufficient = None
        any_zero_frequency = None

    return ActivationDescription(
        population_size=population_size,
        n_seeds=len(seeds),
        n_world_ticks=len(world_dates),
        decision_date_count=len(decision_dates),
        any_zero_on_decision_dates_trajectories=any_zero if decision_dates else None,
        any_zero_on_decision_dates_frequency=any_zero_frequency,
        minimum_decision_date_mean_active=min_mean,
        mean_active_on_decision_dates=mean_decision,
        overall_mean_active=overall_mean,
        overall_zero_active_frequency=sum(value == 0 for value in all_counts) / len(all_counts),
        expected_active_agent_calls_per_episode=overall_mean * len(world_dates),
        sufficient_under_phase10_gate=sufficient,
    )
