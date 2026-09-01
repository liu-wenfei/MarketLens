from marketlens.human.feedback.statistics import (
    JudgementObservation,
    TradeObservation,
    build_feedback_statistics,
)


def _build():
    return build_feedback_statistics(
        start_period=1,
        end_period=4,
        market_price_start=100.0,
        market_price_end=104.0,
        judgements=(
            JudgementObservation(
                period_number=1,
                action="HOLD",
                confidence=55.0,
                evidence_sources=("news-a",),
            ),
            JudgementObservation(
                period_number=1,
                action="BUY",
                confidence=65.0,
                evidence_sources=("news-a", "forum-b"),
            ),
        ),
        eligible_trading_periods=(1, 2, 3, 4),
        trades=(
            TradeObservation(
                period_number=2,
                action="BUY",
                executed_notional=125.0,
            ),
            TradeObservation(
                period_number=4,
                action="SELL",
                executed_notional=75.0,
            ),
        ),
        behaviour_linked_assessments=(),
        portfolio_start_value=1000.0,
        portfolio_end_value=1030.0,
        news_items_available=5,
        community_posts_available=9,
    )


def test_reported_evidence_metrics_are_descriptive():
    result = _build()
    evidence = result.information_metrics[
        "participant_reported_evidence"
    ]

    assert evidence == {
        "total_selections": 3,
        "assessments_with_evidence": 2,
        "unique_reported_sources": 2,
        "repeated_selections": 1,
        "evidence_set_changes": 1,
    }


def test_gross_executed_notional_uses_settled_trade_inputs():
    result = _build()

    assert (
        result.trading_metrics[
            "gross_executed_notional"
        ]
        == 200.0
    )


def test_empty_reported_evidence_is_zero_not_unavailable():
    result = build_feedback_statistics(
        start_period=5,
        end_period=11,
        market_price_start=100.0,
        market_price_end=101.0,
        judgements=(
            JudgementObservation(
                period_number=8,
                action="HOLD",
                confidence=50.0,
            ),
            JudgementObservation(
                period_number=8,
                action="HOLD",
                confidence=50.0,
            ),
        ),
        eligible_trading_periods=(),
        trades=(),
        behaviour_linked_assessments=(),
        portfolio_start_value=1000.0,
        portfolio_end_value=1000.0,
        news_items_available=0,
        community_posts_available=0,
    )

    assert result.information_metrics[
        "participant_reported_evidence"
    ] == {
        "total_selections": 0,
        "assessments_with_evidence": 0,
        "unique_reported_sources": 0,
        "repeated_selections": 0,
        "evidence_set_changes": 0,
    }
