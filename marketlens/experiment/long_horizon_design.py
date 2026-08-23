"""Long-horizon zero-LLM interval comparison for MarketLens Phase 10.

This module does not mutate the frozen protocol.  It extends the previously
introduced decision-day design analysis to longer symmetric trajectories:
11/13/15/17 participant decision days, corresponding to 5/6/7/8 OPEN-state
transitions per phase.

Only structural/calendar properties are derived here.  Activation adequacy is
computed by the preflight script using the existing Phase 4 activation process;
no participant outcome or LLM-generated content is used for protocol selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable

from marketlens.experiment.decision_day_design import DecisionDayDesignError


LONG_HORIZON_DECISION_DAY_CANDIDATES: tuple[int, ...] = (11, 13, 15, 17)
FORMAL_JUDGEMENT_EVENTS = 5
FORMAL_JUDGEMENT_DATES = 3


def _elapsed_calendar_days(start: str, end: str) -> int:
    """Elapsed simulated calendar days; same-day interval is zero."""
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _inclusive_calendar_dates(start: str, end: str) -> tuple[str, ...]:
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    if last < first:
        raise DecisionDayDesignError("end date precedes start date")
    return tuple(
        (first + timedelta(days=offset)).isoformat()
        for offset in range((last - first).days + 1)
    )


@dataclass(frozen=True)
class LongHorizonCandidate:
    decision_days: int
    open_transitions_per_phase: int
    intermediate_points_per_phase: int
    decision_dates: tuple[str, ...]
    misinformation_date: str
    correction_date: str
    later_measurement_date: str
    end_date: str
    misinformation_to_correction_calendar_days: int
    correction_to_later_calendar_days: int
    visible_calendar_days_inclusive: int
    phase1_closed_ticks: int
    phase2_closed_ticks: int
    visible_closed_ticks: int
    world_ticks: int
    participant_response_events: int
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
            "misinformation_to_correction_calendar_days": self.misinformation_to_correction_calendar_days,
            "correction_to_later_calendar_days": self.correction_to_later_calendar_days,
            "visible_calendar_days_inclusive": self.visible_calendar_days_inclusive,
            "phase1_closed_ticks": self.phase1_closed_ticks,
            "phase2_closed_ticks": self.phase2_closed_ticks,
            "visible_closed_ticks": self.visible_closed_ticks,
            "world_ticks": self.world_ticks,
            "participant_response_events": self.participant_response_events,
            "news_coverage_complete": self.news_coverage_complete,
        }


def build_long_horizon_candidates(
    *,
    initialization_date: str,
    visible_start_date: str,
    open_dates: Iterable[str],
    news_dates: Iterable[str],
) -> tuple[LongHorizonCandidate, ...]:
    """Build 11/13/15/17-day symmetric dynamic candidates.

    Participant decisions occur on every participant-visible OPEN state.  The
    correction checkpoint is the central decision date; the first and last
    decision dates anchor J0/J1 and J4 respectively.
    """
    open_set = set(open_dates)
    open_values = tuple(sorted(value for value in open_set if value >= visible_start_date))
    news_set = set(news_dates)
    init = date.fromisoformat(initialization_date)
    visible = date.fromisoformat(visible_start_date)

    results: list[LongHorizonCandidate] = []
    for decision_days in LONG_HORIZON_DECISION_DAY_CANDIDATES:
        if decision_days % 2 != 1:
            raise DecisionDayDesignError("symmetric candidate requires an odd decision-day count")
        transitions = (decision_days - 1) // 2
        decision_dates = open_values[:decision_days]
        if len(decision_dates) != decision_days:
            raise DecisionDayDesignError(
                f"need {decision_days} OPEN dates from {visible_start_date}, found {len(decision_dates)}"
            )

        misinformation = decision_dates[0]
        correction = decision_dates[transitions]
        later = decision_dates[-1]
        if misinformation != visible_start_date:
            raise DecisionDayDesignError(
                "visible_start_date must be the first participant-visible OPEN decision date"
            )

        phase1_calendar = _inclusive_calendar_dates(misinformation, correction)
        phase2_calendar = _inclusive_calendar_dates(correction, later)
        visible_calendar = _inclusive_calendar_dates(misinformation, later)
        world_calendar = _inclusive_calendar_dates(initialization_date, later)

        phase1_open = sum(value in open_set for value in phase1_calendar)
        phase2_open = sum(value in open_set for value in phase2_calendar)
        visible_open = sum(value in open_set for value in visible_calendar)

        expected_open_per_phase = transitions + 1
        if phase1_open != expected_open_per_phase or phase2_open != expected_open_per_phase:
            raise DecisionDayDesignError(
                "OPEN-state count is inconsistent with the symmetric-transition contract"
            )
        if visible_open != decision_days:
            raise DecisionDayDesignError(
                "participant decision dates must cover every OPEN state in the candidate visible horizon"
            )

        results.append(
            LongHorizonCandidate(
                decision_days=decision_days,
                open_transitions_per_phase=transitions,
                intermediate_points_per_phase=transitions - 1,
                decision_dates=decision_dates,
                misinformation_date=misinformation,
                correction_date=correction,
                later_measurement_date=later,
                end_date=later,
                misinformation_to_correction_calendar_days=_elapsed_calendar_days(
                    misinformation, correction
                ),
                correction_to_later_calendar_days=_elapsed_calendar_days(correction, later),
                visible_calendar_days_inclusive=len(visible_calendar),
                phase1_closed_ticks=len(phase1_calendar) - phase1_open,
                phase2_closed_ticks=len(phase2_calendar) - phase2_open,
                visible_closed_ticks=len(visible_calendar) - visible_open,
                world_ticks=(date.fromisoformat(later) - init).days + 1,
                participant_response_events=decision_days + FORMAL_JUDGEMENT_EVENTS,
                news_coverage_complete=all(value in news_set for value in world_calendar),
            )
        )

    return tuple(results)
