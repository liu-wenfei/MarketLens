"""Phase 9 sequential Agent-world orchestration primitives.

This module is intentionally thin.  It does not implement Agent reasoning,
graph construction, news loading, forum propagation, market matching, price
formation, or portfolio updates.

It only provides:
- an authoritative calendar-day plan;
- Phase 4 activation-state carry-forward across that plan;
- a single open/closed market dispatcher that delegates to the already-frozen
  Phase 7 market wrappers.

The real multi-day backend preflight is a later Phase 9 gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Sequence

from marketlens.agents.activation.policy import ActivationPolicy
from marketlens.agents.activation.sampler import ActivationBatch, sample_activation
from marketlens.agents.activation.state import ActivationState


class MultiDayOrchestrationError(RuntimeError):
    """Raised when the Phase 9 sequential contract cannot be satisfied."""


BeliefSource = Literal["initial", "forum_with_initial_fallback"]
MarketAction = Literal["advance_trading_day", "advance_non_trading_day"]


@dataclass(frozen=True)
class AgentWorldDayPlan:
    """One calendar day in the Agent-world engineering horizon."""

    step: int
    current_date: str
    history_cutoff: str
    day_1st: bool
    market_open: bool
    participant_trading_enabled: bool
    belief_source: BeliefSource
    forum_actions_enabled: bool
    expected_market_action: MarketAction


@dataclass(frozen=True)
class DayActivation:
    """Phase 4 activation result attached to one planned calendar day."""

    day: AgentWorldDayPlan
    batch: ActivationBatch


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise MultiDayOrchestrationError(
            f"date must be ISO YYYY-MM-DD, got {value!r}"
        ) from exc


def build_calendar_day_plan(
    *,
    start_date: str,
    end_date: str,
    trading_days: Iterable[str],
) -> tuple[AgentWorldDayPlan, ...]:
    """Build a contiguous *calendar-day* plan.

    Market availability comes only from ``trading_days``.  Agent activation,
    order count, and matched executions are deliberately not inputs.
    """

    start = _parse_iso_date(start_date)
    end = _parse_iso_date(end_date)
    if end < start:
        raise MultiDayOrchestrationError("end_date must be on or after start_date")

    trading_day_set = {str(value)[:10] for value in trading_days}
    plans: list[AgentWorldDayPlan] = []

    current = start
    step = 0
    while current <= end:
        current_text = current.isoformat()
        market_open = current_text in trading_day_set
        plans.append(
            AgentWorldDayPlan(
                step=step,
                current_date=current_text,
                history_cutoff=(current - timedelta(days=1)).isoformat(),
                day_1st=(step == 0),
                market_open=market_open,
                participant_trading_enabled=market_open,
                belief_source=(
                    "initial" if step == 0 else "forum_with_initial_fallback"
                ),
                forum_actions_enabled=(step > 0),
                expected_market_action=(
                    "advance_trading_day"
                    if market_open
                    else "advance_non_trading_day"
                ),
            )
        )
        current += timedelta(days=1)
        step += 1

    return tuple(plans)


def sample_activation_sequence(
    profiles: Iterable[Any],
    *,
    plan: Sequence[AgentWorldDayPlan],
    seed: str,
    policy: ActivationPolicy | None = None,
    initial_state: ActivationState | None = None,
    sampler: Callable[..., ActivationBatch] = sample_activation,
) -> tuple[DayActivation, ...]:
    """Run the frozen Phase 4 sampler sequentially with explicit state carry-forward."""

    activation_policy = policy or ActivationPolicy()
    profile_tuple = tuple(profiles)
    state = initial_state
    results: list[DayActivation] = []

    for day in plan:
        batch = sampler(
            profile_tuple,
            policy=activation_policy,
            state=state,
            seed=seed,
            step=day.step,
        )
        if batch.step != day.step:
            raise MultiDayOrchestrationError(
                f"activation batch step {batch.step} does not match day step {day.step}"
            )
        results.append(DayActivation(day=day, batch=batch))
        state = batch.next_state

    return tuple(results)


def dispatch_market_action(
    day: AgentWorldDayPlan,
    *,
    runtime_db: str | Path,
    decision_json: str | Path | None = None,
    log_dir: str | Path | None = None,
    protected_paths: Iterable[str | Path] = (),
    advance_trading_day_fn: Callable[..., Any] | None = None,
    advance_non_trading_day_fn: Callable[..., Any] | None = None,
) -> Any:
    """Delegate exactly one market-state transition to the frozen Phase 7 wrappers.

    This function is not called by the Phase 9B zero-LLM CLI.  It exists so the
    later real-backend gate has one tested branch point and cannot accidentally
    infer market closure from Agent activity.
    """

    if advance_trading_day_fn is None or advance_non_trading_day_fn is None:
        from marketlens.market.runtime.inherited_market import (
            advance_non_trading_day,
            advance_trading_day,
        )

        advance_trading_day_fn = advance_trading_day_fn or advance_trading_day
        advance_non_trading_day_fn = (
            advance_non_trading_day_fn or advance_non_trading_day
        )

    if day.market_open:
        if decision_json is None or log_dir is None:
            raise MultiDayOrchestrationError(
                "open trading day requires decision_json and log_dir"
            )
        return advance_trading_day_fn(
            current_date=day.current_date,
            runtime_db=runtime_db,
            decision_json=decision_json,
            log_dir=log_dir,
            protected_paths=protected_paths,
        )

    return advance_non_trading_day_fn(
        current_date=day.current_date,
        runtime_db=runtime_db,
        protected_paths=protected_paths,
    )
