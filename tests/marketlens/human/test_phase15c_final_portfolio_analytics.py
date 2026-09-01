from datetime import date, timedelta

import pytest

from marketlens.human.feedback.final_analytics import (
    FinalAnalyticsError,
    build_final_analytics,
)
from marketlens.human.feedback.journey import (
    JourneyPeriod,
    JourneyPortfolioSnapshot,
    ParticipantDecisionJourney,
)


def _journey(
    *,
    values=None,
    final_cash=300.0,
    final_holdings=None,
):
    if values is None:
        values = [
            1000.0,
            1020.0,
            1100.0,
            1080.0,
            990.0,
            1010.0,
            1030.0,
            1060.0,
            1090.0,
            1120.0,
            1140.0,
            1160.0,
            1180.0,
            1190.0,
            1200.0,
        ]

    if final_holdings is None:
        final_holdings = {
            "AAA": 6,
            "BBB": 3,
        }

    start = date(2023, 6, 19)
    periods = []

    for index, value in enumerate(values, start=1):
        is_final = index == 15

        periods.append(
            JourneyPeriod(
                period_number=index,
                agent_world_date=(
                    start
                    + timedelta(days=index - 1)
                ).isoformat(),
                market_open=True,
                participant_trading_enabled=True,
                judgements=(),
                transactions=(),
                behaviour_summary="NO_TRADE",
                holding_changes={},
                portfolio_end=(
                    JourneyPortfolioSnapshot(
                        cash=(
                            final_cash
                            if is_final
                            else value
                        ),
                        holdings=(
                            final_holdings
                            if is_final
                            else {}
                        ),
                        portfolio_value=value,
                    )
                ),
                period_pnl=0.0,
                cumulative_pnl=(
                    value - values[0]
                ),
                pnl_direction="FLAT",
                feedback_boundary="NONE",
            )
        )

    return ParticipantDecisionJourney(
        journey_version=(
            "marketlens-participant-decision-journey-v1"
        ),
        target_stock_id="AAA",
        initial_cash=1000.0,
        initial_holdings={},
        initial_portfolio_value=1000.0,
        periods=tuple(periods),
    )


def _turnover_inputs():
    start = date(2023, 6, 19)

    previous = {
        (
            start
            + timedelta(days=index)
        ).isoformat(): 1000.0
        for index in range(15)
    }

    trades = {
        start.isoformat(): (100.0,),
        (
            start
            + timedelta(days=1)
        ).isoformat(): (200.0,),
    }

    return trades, previous


def test_final_analytics_uses_journey_equity_and_existing_metrics():
    trades, previous = _turnover_inputs()

    result = build_final_analytics(
        journey=_journey(),
        trades_by_day=trades,
        previous_portfolio_values=previous,
        final_risky_asset_values={
            "AAA": 600.0,
            "BBB": 300.0,
        },
    )

    assert result["final_analytics_version"] == (
        "marketlens-final-analytics-v1"
    )

    curve = result["equity_curve"]
    assert len(curve) == 15
    assert curve[0]["portfolio_value"] == 1000.0
    assert curve[-1]["portfolio_value"] == 1200.0

    drawdown = result["maximum_drawdown"]
    assert drawdown["available"] is True
    assert drawdown["value_pct"] == pytest.approx(
        10.0
    )

    turnover = result["executed_turnover"]
    assert turnover["available"] is True
    assert turnover["total_turnover_pct"] == pytest.approx(
        30.0
    )
    assert turnover[
        "average_daily_turnover_pct"
    ] == pytest.approx(2.0)


def test_final_portfolio_construction_has_explicit_semantics():
    trades, previous = _turnover_inputs()

    result = build_final_analytics(
        journey=_journey(),
        trades_by_day=trades,
        previous_portfolio_values=previous,
        final_risky_asset_values={
            "AAA": 600.0,
            "BBB": 300.0,
        },
    )

    construction = result[
        "portfolio_construction"
    ]

    assert construction[
        "cash_weight_pct"
    ]["value"] == pytest.approx(25.0)

    assert construction[
        "risky_holding_count"
    ] == 2

    assert construction[
        "largest_risky_holding_weight_pct"
    ]["value"] == pytest.approx(50.0)

    assert construction[
        "risky_hhi"
    ]["value"] == pytest.approx(5.0 / 9.0)

    assert construction[
        "effective_risky_holdings"
    ]["value"] == pytest.approx(1.8)


def test_cash_only_portfolio_uses_unavailable_not_zero():
    trades, previous = _turnover_inputs()

    result = build_final_analytics(
        journey=_journey(
            final_cash=1200.0,
            final_holdings={},
        ),
        trades_by_day=trades,
        previous_portfolio_values=previous,
        final_risky_asset_values={},
    )

    construction = result[
        "portfolio_construction"
    ]

    assert construction[
        "cash_weight_pct"
    ]["value"] == pytest.approx(100.0)

    assert construction[
        "risky_holding_count"
    ] == 0

    for key in (
        "largest_risky_holding_weight_pct",
        "risky_hhi",
        "effective_risky_holdings",
    ):
        assert construction[key] == {
            "available": False,
            "value": None,
            "reason": "no_risky_holdings",
        }


def test_final_asset_values_must_reconcile_to_journey():
    trades, previous = _turnover_inputs()

    with pytest.raises(
        FinalAnalyticsError,
        match="disagree",
    ):
        build_final_analytics(
            journey=_journey(),
            trades_by_day=trades,
            previous_portfolio_values=previous,
            final_risky_asset_values={
                "AAA": 500.0,
                "BBB": 300.0,
            },
        )


def test_final_analytics_requires_complete_p1_to_p15():
    trades, previous = _turnover_inputs()
    journey = _journey()

    incomplete = ParticipantDecisionJourney(
        journey_version=journey.journey_version,
        target_stock_id=journey.target_stock_id,
        initial_cash=journey.initial_cash,
        initial_holdings=journey.initial_holdings,
        initial_portfolio_value=(
            journey.initial_portfolio_value
        ),
        periods=journey.periods[:-1],
    )

    with pytest.raises(
        FinalAnalyticsError,
        match="P1-P15",
    ):
        build_final_analytics(
            journey=incomplete,
            trades_by_day=trades,
            previous_portfolio_values=previous,
            final_risky_asset_values={},
        )
