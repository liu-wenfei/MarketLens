"""Pure portfolio metrics for MarketLens feedback.

The metric semantics are adapted from the audited legacy TwinMarket
``util/PortfolioMetrics.py`` implementation.

Only the bounded primitives relevant to the current MarketLens feedback
contract are retained here.

This module:
- performs no database access;
- performs no network/API access;
- performs no experiment-state mutation;
- never substitutes guessed values for missing observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class EquityPoint:
    date: str
    total_value: float


@dataclass(frozen=True, slots=True)
class MaxDrawdown:
    max_drawdown_pct: float
    peak_date: str
    trough_date: str


@dataclass(frozen=True, slots=True)
class ExecutedTurnover:
    total_turnover_pct: float
    average_daily_turnover_pct: float
    daily_turnover_pct: tuple[float, ...]


def _finite(value: object) -> float | None:
    """Return a finite numeric primitive without string/bool coercion."""

    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        return None

    number = float(value)

    if not math.isfinite(number):
        return None

    return number


def max_drawdown(
    equity_curve: Sequence[EquityPoint],
) -> MaxDrawdown | None:
    """Return maximum peak-to-trough loss magnitude.

    The percentage is descriptive and non-annualised.

    Invalid/non-positive values make the metric unavailable rather than
    introducing a financial assumption.
    """

    if len(equity_curve) < 2:
        return None

    parsed: list[tuple[date, float]] = []

    for point in equity_curve:
        try:
            parsed_date = date.fromisoformat(point.date)
        except (TypeError, ValueError):
            return None

        value = _finite(point.total_value)

        if value is None or value <= 0:
            return None

        parsed.append((parsed_date, value))

    parsed.sort(key=lambda item: item[0])

    running_peak_value = parsed[0][1]
    running_peak_date = parsed[0][0]

    worst_loss = 0.0
    worst_peak_date = running_peak_date
    worst_trough_date = running_peak_date

    for current_date, current_value in parsed:

        if current_value > running_peak_value:
            running_peak_value = current_value
            running_peak_date = current_date

        loss = (
            1.0
            - current_value / running_peak_value
        ) * 100.0

        if loss > worst_loss:
            worst_loss = loss
            worst_peak_date = running_peak_date
            worst_trough_date = current_date

    return MaxDrawdown(
        max_drawdown_pct=worst_loss,
        peak_date=worst_peak_date.isoformat(),
        trough_date=worst_trough_date.isoformat(),
    )


def calculate_executed_turnover(
    *,
    trades_by_day: Mapping[str, Sequence[float]],
    previous_portfolio_values: Mapping[str, float | None],
) -> ExecutedTurnover | None:
    """Calculate turnover from actual settled gross traded notional.

    For each eligible date:

        gross executed notional
        ----------------------- × 100
        portfolio value before that day's settlement

    A valid day containing zero participant trades contributes exactly 0%.

    A missing/non-positive denominator is not guessed and that date is not
    scored. If any trade notional for a date is invalid, that date is also
    excluded rather than silently under-counted.
    """

    daily: list[float] = []

    for day in sorted(previous_portfolio_values):

        try:
            date.fromisoformat(day)
        except (TypeError, ValueError):
            continue

        denominator = _finite(
            previous_portfolio_values[day]
        )

        if denominator is None or denominator <= 0:
            continue

        notionals = trades_by_day.get(day, ())

        gross_notional = 0.0
        valid_day = True

        for raw_notional in notionals:
            notional = _finite(raw_notional)

            if notional is None or notional < 0:
                valid_day = False
                break

            gross_notional += notional

        if not valid_day:
            continue

        daily.append(
            gross_notional
            / denominator
            * 100.0
        )

    if not daily:
        return None

    return ExecutedTurnover(
        total_turnover_pct=sum(daily),
        average_daily_turnover_pct=(
            sum(daily) / len(daily)
        ),
        daily_turnover_pct=tuple(daily),
    )
