from datetime import date, timedelta

import pytest

from marketlens.human.feedback.journey import (
    JourneyPeriod,
    JourneyPortfolioSnapshot,
    ParticipantDecisionJourney,
)
from marketlens.human.feedback.journey_source import (
    JourneyAuthoritativeSourceAdapter,
)
from marketlens.human.feedback.source import (
    FeedbackKind,
    FeedbackStatisticsSourceAdapter,
)
from marketlens.human.feedback.statistics import (
    JudgementObservation,
    build_feedback_statistics,
)


def _journey():
    start = date(2023, 6, 19)
    periods = []

    for number in range(1, 16):
        periods.append(
            JourneyPeriod(
                period_number=number,
                agent_world_date=(
                    start
                    + timedelta(days=number - 1)
                ).isoformat(),
                market_open=True,
                participant_trading_enabled=True,
                judgements=(),
                transactions=(),
                behaviour_summary="NO_TRADE",
                holding_changes={},
                portfolio_end=JourneyPortfolioSnapshot(
                    cash=800.0,
                    holdings={
                        "AAA": 10,
                        "BBB": 10,
                    },
                    portfolio_value=1100.0,
                ),
                period_pnl=0.0,
                cumulative_pnl=0.0,
                pnl_direction="FLAT",
                feedback_boundary="NONE",
            )
        )

    return ParticipantDecisionJourney(
        journey_version=(
            "marketlens-participant-decision-journey-v1"
        ),
        target_stock_id="AAA",
        initial_cash=800.0,
        initial_holdings={
            "AAA": 10,
            "BBB": 10,
        },
        initial_portfolio_value=1100.0,
        periods=tuple(periods),
    )


def test_statistics_omit_final_group_before_final():
    result = build_feedback_statistics(
        start_period=1,
        end_period=4,
        market_price_start=10.0,
        market_price_end=10.0,
        judgements=(
            JudgementObservation(
                period_number=1,
                action="HOLD",
                confidence=50.0,
            ),
        ),
        eligible_trading_periods=(),
        trades=(),
        behaviour_linked_assessments=(),
        portfolio_start_value=1100.0,
        portfolio_end_value=1100.0,
        news_items_available=0,
        community_posts_available=0,
    ).to_dict()

    assert result["statistics_version"] == (
        "marketlens-feedback-statistics-v4"
    )
    assert "final_only_metrics" not in result


def test_statistics_reject_final_group_outside_exact_final_window():
    with pytest.raises(
        ValueError,
        match="P1-P15 FINAL window",
    ):
        build_feedback_statistics(
            start_period=5,
            end_period=11,
            market_price_start=10.0,
            market_price_end=10.0,
            judgements=(
                JudgementObservation(
                    period_number=8,
                    action="HOLD",
                    confidence=50.0,
                ),
            ),
            eligible_trading_periods=(),
            trades=(),
            behaviour_linked_assessments=(),
            portfolio_start_value=1100.0,
            portfolio_end_value=1100.0,
            news_items_available=0,
            community_posts_available=0,
            final_only_metrics={"unexpected": True},
        )


class _StubSource(FeedbackStatisticsSourceAdapter):
    def __init__(self):
        self.target_stock_id = "AAA"
        self.final_calls = 0

    def _resolve_episode_projection(self, session_id):
        return "episode-test", object()

    def _require_round_lock(self, session_id, window):
        return None

    def _require_background_exposures(
        self,
        *,
        session_id,
        episode_id,
        projection,
        window,
    ):
        return None

    def _judgement_inputs(self, *, session_id, window):
        return (
            (
                JudgementObservation(
                    period_number=window.start_period,
                    action="HOLD",
                    confidence=50.0,
                ),
            ),
            (),
        )

    def _portfolio_inputs(self, *, session_id, window):
        return 1100.0, 1100.0, ()

    def _eligible_trading_periods(self, window):
        return ()

    def _target_price(self, period_number):
        return 10.0

    def _information_inputs(self, *, projection, window):
        return 0, 0, {}

    def _final_only_metrics(self, session_id):
        self.final_calls += 1
        return {"marker": "FINAL_ONLY"}


def test_source_adapter_calls_final_analytics_only_for_final():
    source = _StubSource()

    f1 = source.build("session-test", FeedbackKind.F1).to_dict()
    f2 = source.build("session-test", FeedbackKind.F2).to_dict()
    final = source.build(
        "session-test",
        FeedbackKind.FINAL,
    ).to_dict()

    assert "final_only_metrics" not in f1
    assert "final_only_metrics" not in f2
    assert final["final_only_metrics"] == {
        "marker": "FINAL_ONLY"
    }
    assert source.final_calls == 1


def test_authoritative_final_helper_reuses_journey_and_exact_prices(
    monkeypatch,
):
    journey = _journey()

    monkeypatch.setattr(
        JourneyAuthoritativeSourceAdapter,
        "build",
        lambda self, session_id: journey,
    )

    source = FeedbackStatisticsSourceAdapter(
        assignments=object(),
        projections={},
        judgements=object(),
        portfolios=object(),
        rounds=object(),
        events=object(),
        price_provider=object(),
        calendar=object(),
        contract=object(),
        target_stock_id="AAA",
    )

    prices = {
        "AAA": 10.0,
        "BBB": 20.0,
    }

    monkeypatch.setattr(
        source,
        "_price",
        lambda *, stock_id, period_number: prices[stock_id],
    )

    result = source._final_only_metrics(
        "session-test"
    )

    assert len(result["equity_curve"]) == 15

    turnover = result["executed_turnover"]
    assert turnover["available"] is True
    assert turnover["total_turnover_pct"] == pytest.approx(0.0)
    assert turnover[
        "average_daily_turnover_pct"
    ] == pytest.approx(0.0)
    assert len(turnover["daily_turnover_pct"]) == 15

    construction = result[
        "portfolio_construction"
    ]
    assert construction[
        "cash_weight_pct"
    ]["value"] == pytest.approx(
        800.0 / 1100.0 * 100.0
    )
    assert construction[
        "risky_holding_count"
    ] == 2
    assert construction[
        "largest_risky_holding_weight_pct"
    ]["value"] == pytest.approx(
        200.0 / 1100.0 * 100.0
    )
    assert construction[
        "effective_risky_holdings"
    ]["value"] == pytest.approx(1.8)
