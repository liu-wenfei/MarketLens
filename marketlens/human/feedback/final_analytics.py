"""Deterministic FINAL-only portfolio analytics for MarketLens feedback.

This module consumes already-authoritative participant Journey output plus
authoritative daily turnover denominators and final risky-asset market values.

It performs no database/network access and creates no new source of truth.
It reuses the bounded portfolio metric primitives already audited for
MarketLens.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from marketlens.human.feedback.journey import (
    ParticipantDecisionJourney,
)
from marketlens.human.feedback.portfolio_metrics import (
    EquityPoint,
    calculate_executed_turnover,
    max_drawdown,
)


FINAL_ANALYTICS_VERSION = "marketlens-final-analytics-v1"
_FORMAL_FINAL_PERIODS = tuple(range(1, 16))
_EPSILON = 1e-8


class FinalAnalyticsError(ValueError):
    """FINAL analytics inputs are incomplete or inconsistent."""


def _finite(
    name: str,
    value: object,
    *,
    minimum: float | None = None,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise FinalAnalyticsError(
            f"{name} must be a finite number"
        )

    number = float(value)

    if not math.isfinite(number):
        raise FinalAnalyticsError(
            f"{name} must be finite"
        )

    if minimum is not None and number < minimum:
        raise FinalAnalyticsError(
            f"{name} must be >= {minimum}"
        )

    return number


def _available(value: float) -> dict[str, object]:
    return {
        "available": True,
        "value": value,
        "reason": None,
    }


def _unavailable(reason: str) -> dict[str, object]:
    return {
        "available": False,
        "value": None,
        "reason": reason,
    }


def build_final_analytics(
    *,
    journey: ParticipantDecisionJourney,
    trades_by_day: Mapping[str, Sequence[float]],
    previous_portfolio_values: Mapping[str, float | None],
    final_risky_asset_values: Mapping[str, float],
) -> dict[str, object]:
    """Build participant-safe FINAL-only descriptive portfolio analytics.

    Semantics:
    - equity curve uses authoritative end-of-period Journey values;
    - turnover reuses actual settled gross notional and authoritative
      pre-settlement portfolio denominators;
    - cash weight is a share of total final portfolio value;
    - largest risky holding weight is a share of total final portfolio value;
    - HHI/effective holdings normalize only across risky assets, excluding cash;
    - no risky holdings is unavailable for concentration/effective-holdings
      rather than being represented as zero or one.
    """

    periods = tuple(journey.periods)

    if tuple(
        period.period_number
        for period in periods
    ) != _FORMAL_FINAL_PERIODS:
        raise FinalAnalyticsError(
            "FINAL analytics require the complete formal P1-P15 Journey"
        )

    equity_curve: list[EquityPoint] = []

    for period in periods:
        total_value = _finite(
            "Journey period portfolio value",
            period.portfolio_end.portfolio_value,
            minimum=0.0,
        )

        equity_curve.append(
            EquityPoint(
                date=period.agent_world_date,
                total_value=total_value,
            )
        )

    final_snapshot = periods[-1].portfolio_end
    final_total_value = _finite(
        "final portfolio value",
        final_snapshot.portfolio_value,
        minimum=0.0,
    )
    final_cash = _finite(
        "final cash",
        final_snapshot.cash,
        minimum=0.0,
    )

    risky_values: dict[str, float] = {}

    for stock_id, raw_value in final_risky_asset_values.items():
        if not isinstance(stock_id, str) or not stock_id.strip():
            raise FinalAnalyticsError(
                "final risky asset identifiers must be non-empty strings"
            )

        value = _finite(
            f"final risky asset value {stock_id!r}",
            raw_value,
            minimum=0.0,
        )

        if value > 0:
            risky_values[stock_id.strip()] = value

    risky_total = sum(risky_values.values())

    if not math.isclose(
        final_cash + risky_total,
        final_total_value,
        rel_tol=_EPSILON,
        abs_tol=_EPSILON,
    ):
        raise FinalAnalyticsError(
            "final cash plus risky asset values disagree "
            "with authoritative final portfolio value"
        )

    equity_drawdown = max_drawdown(
        tuple(equity_curve)
    )

    if equity_drawdown is None:
        drawdown_payload: dict[str, object] = {
            "available": False,
            "value_pct": None,
            "peak_date": None,
            "trough_date": None,
            "reason": "valid_positive_equity_curve_unavailable",
        }
    else:
        drawdown_payload = {
            "available": True,
            "value_pct": equity_drawdown.max_drawdown_pct,
            "peak_date": equity_drawdown.peak_date,
            "trough_date": equity_drawdown.trough_date,
            "reason": None,
        }

    turnover = calculate_executed_turnover(
        trades_by_day=trades_by_day,
        previous_portfolio_values=(
            previous_portfolio_values
        ),
    )

    if turnover is None:
        turnover_payload: dict[str, object] = {
            "available": False,
            "total_turnover_pct": None,
            "average_daily_turnover_pct": None,
            "daily_turnover_pct": None,
            "reason": "valid_turnover_denominators_unavailable",
        }
    else:
        turnover_payload = {
            "available": True,
            "total_turnover_pct": (
                turnover.total_turnover_pct
            ),
            "average_daily_turnover_pct": (
                turnover.average_daily_turnover_pct
            ),
            "daily_turnover_pct": list(
                turnover.daily_turnover_pct
            ),
            "reason": None,
        }

    if final_total_value > 0:
        cash_weight = _available(
            final_cash
            / final_total_value
            * 100.0
        )
    else:
        cash_weight = _unavailable(
            "non_positive_final_portfolio_value"
        )

    risky_holding_count = len(risky_values)

    if not risky_values:
        largest_risky_weight = _unavailable(
            "no_risky_holdings"
        )
        risky_hhi = _unavailable(
            "no_risky_holdings"
        )
        effective_risky_holdings = _unavailable(
            "no_risky_holdings"
        )
    else:
        if final_total_value > 0:
            largest_risky_weight = _available(
                max(risky_values.values())
                / final_total_value
                * 100.0
            )
        else:
            largest_risky_weight = _unavailable(
                "non_positive_final_portfolio_value"
            )

        risky_weights = [
            value / risky_total
            for value in risky_values.values()
        ]

        hhi = sum(
            weight * weight
            for weight in risky_weights
        )

        risky_hhi = _available(hhi)
        effective_risky_holdings = _available(
            1.0 / hhi
        )

    return {
        "final_analytics_version": (
            FINAL_ANALYTICS_VERSION
        ),
        "equity_curve": [
            {
                "date": point.date,
                "portfolio_value": (
                    point.total_value
                ),
            }
            for point in equity_curve
        ],
        "maximum_drawdown": drawdown_payload,
        "executed_turnover": turnover_payload,
        "portfolio_construction": {
            "cash_weight_pct": cash_weight,
            "risky_holding_count": (
                risky_holding_count
            ),
            "largest_risky_holding_weight_pct": (
                largest_risky_weight
            ),
            "risky_hhi": risky_hhi,
            "effective_risky_holdings": (
                effective_risky_holdings
            ),
        },
    }
