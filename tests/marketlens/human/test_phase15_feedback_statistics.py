import pytest

from marketlens.human.feedback import (
    AssessmentActionLink,
    EquityPoint,
    JudgementObservation,
    TradeObservation,
    build_feedback_statistics,
    calculate_executed_turnover,
    max_drawdown,
)


def sample_statistics(**overrides):

    values = {
        "start_period": 1,
        "end_period": 4,

        "market_price_start": 10.0,
        "market_price_end": 10.5,

        "judgements": (
            JudgementObservation(
                1,
                "HOLD",
                72,
            ),
            JudgementObservation(
                1,
                "SELL",
                51,
            ),
        ),

        "eligible_trading_periods": (
            1,
            2,
            3,
            4,
        ),

        "trades": (
            TradeObservation(
                1,
                "SELL",
            ),
        ),

        "behaviour_linked_assessments": (
            AssessmentActionLink(
                1,
                "SELL",
            ),
        ),

        "portfolio_start_value": 10000,
        "portfolio_end_value": 10080,

        "news_items_available": 8,
        "community_posts_available": 17,

        "source_label_counts": {
            "Individual Investor": 9,
            "Market Blogger": 5,
            "Influential Market Commentator": 3,
        },
    }

    values.update(overrides)

    return build_feedback_statistics(
        **values
    )


def test_core_feedback_statistics():

    result = sample_statistics()

    assert (
        result.statistics_version
        == "marketlens-feedback-statistics-v4"
    )

    assert (
        result.window[
            "periods_reviewed"
        ]
        == 4
    )

    assert (
        result.market_metrics[
            "price_change_pct"
        ]
        == pytest.approx(5.0)
    )

    assert (
        result.judgement_metrics[
            "revision_count"
        ]
        == 1
    )

    assert (
        result.confidence_metrics[
            "change_points"
        ]
        == -21
    )

    assert (
        result.trading_metrics[
            "trade_periods"
        ]
        == 1
    )

    assert (
        result.trading_metrics[
            "no_trade_periods"
        ]
        == 3
    )

    assert (
        result.trading_metrics[
            "transaction_count"
        ]
        == 1
    )

    assert (
        result.trading_metrics[
            "trading_activity_pct"
        ]
        == pytest.approx(25.0)
    )

    assert (
        result.judgement_action_metrics[
            "same_direction_actions"
        ]
        == 1
    )


def test_multiple_transactions_are_not_confused_with_trade_periods():

    result = sample_statistics(
        trades=(
            TradeObservation(
                1,
                "BUY",
            ),
            TradeObservation(
                1,
                "BUY",
            ),
            TradeObservation(
                3,
                "SELL",
            ),
        ),
        behaviour_linked_assessments=(),
    )

    assert (
        result.trading_metrics[
            "transaction_count"
        ]
        == 3
    )

    assert (
        result.trading_metrics[
            "trade_periods"
        ]
        == 2
    )

    assert (
        result.trading_metrics[
            "no_trade_periods"
        ]
        == 2
    )


def test_buy_and_sell_same_period_is_mixed():

    result = sample_statistics(
        trades=(
            TradeObservation(
                1,
                "BUY",
            ),
            TradeObservation(
                1,
                "SELL",
            ),
        ),
    )

    relation = (
        result.judgement_action_metrics
    )

    assert relation[
        "mixed_trading"
    ] == 1

    assert relation[
        "same_direction_actions"
    ] == 0

    assert relation[
        "opposite_direction_actions"
    ] == 0


def test_hold_with_trade_is_not_scored_same_or_opposite():

    result = sample_statistics(
        trades=(
            TradeObservation(
                1,
                "BUY",
            ),
        ),
        behaviour_linked_assessments=(
            AssessmentActionLink(
                1,
                "HOLD",
            ),
        ),
    )

    relation = (
        result.judgement_action_metrics
    )

    assert relation[
        "hold_with_trade"
    ] == 1

    assert relation[
        "same_direction_actions"
    ] == 0

    assert relation[
        "opposite_direction_actions"
    ] == 0


def test_no_trade_remains_descriptive():

    result = sample_statistics(
        trades=(),
        behaviour_linked_assessments=(
            AssessmentActionLink(
                1,
                "SELL",
            ),
        ),
    )

    assert (
        result.judgement_action_metrics[
            "no_trade"
        ]
        == 1
    )


def test_opposite_direction_is_descriptive():

    result = sample_statistics(
        trades=(
            TradeObservation(
                1,
                "BUY",
            ),
        ),
        behaviour_linked_assessments=(
            AssessmentActionLink(
                1,
                "SELL",
            ),
        ),
    )

    assert (
        result.judgement_action_metrics[
            "opposite_direction_actions"
        ]
        == 1
    )


def test_invalid_confidence_rejected():

    with pytest.raises(
        ValueError,
        match="confidence",
    ):
        sample_statistics(
            judgements=(
                JudgementObservation(
                    1,
                    "HOLD",
                    101,
                ),
            )
        )


def test_trade_must_belong_to_eligible_period():

    with pytest.raises(
        ValueError,
        match="trading-eligible",
    ):
        sample_statistics(
            eligible_trading_periods=(
                1,
                2,
            ),
            trades=(
                TradeObservation(
                    3,
                    "BUY",
                ),
            ),
            behaviour_linked_assessments=(),
        )


def test_max_drawdown_uses_peak_to_trough_loss():

    result = max_drawdown(
        (
            EquityPoint(
                "2023-06-19",
                10000,
            ),
            EquityPoint(
                "2023-06-20",
                11000,
            ),
            EquityPoint(
                "2023-06-21",
                8800,
            ),
            EquityPoint(
                "2023-06-22",
                9900,
            ),
        )
    )

    assert result is not None

    assert (
        result.max_drawdown_pct
        == pytest.approx(20.0)
    )

    assert (
        result.peak_date
        == "2023-06-20"
    )

    assert (
        result.trough_date
        == "2023-06-21"
    )


def test_max_drawdown_fails_closed_for_invalid_curve():

    assert (
        max_drawdown(
            (
                EquityPoint(
                    "2023-06-19",
                    10000,
                ),
                EquityPoint(
                    "2023-06-20",
                    0,
                ),
            )
        )
        is None
    )


def test_executed_turnover_uses_actual_trade_notional():

    result = calculate_executed_turnover(
        trades_by_day={
            "2023-06-19": (
                500.0,
                250.0,
            ),
            "2023-06-20": (),
        },
        previous_portfolio_values={
            "2023-06-19": 10000.0,
            "2023-06-20": 11000.0,
        },
    )

    assert result is not None

    assert (
        result.daily_turnover_pct[0]
        == pytest.approx(7.5)
    )

    assert (
        result.daily_turnover_pct[1]
        == pytest.approx(0.0)
    )

    assert (
        result.total_turnover_pct
        == pytest.approx(7.5)
    )

    assert (
        result.average_daily_turnover_pct
        == pytest.approx(3.75)
    )


def test_turnover_does_not_invent_missing_denominator():

    result = calculate_executed_turnover(
        trades_by_day={
            "2023-06-19": (
                500.0,
            ),
            "2023-06-20": (
                900.0,
            ),
        },
        previous_portfolio_values={
            "2023-06-19": 10000.0,
            "2023-06-20": None,
        },
    )

    assert result is not None

    assert (
        result.daily_turnover_pct
        == pytest.approx(
            (5.0,)
        )
    )


def test_feedback_statistics_serialise_to_plain_mapping():

    payload = (
        sample_statistics()
        .to_dict()
    )

    assert (
        payload[
            "statistics_version"
        ]
        == "marketlens-feedback-statistics-v4"
    )

    assert (
        payload[
            "information_metrics"
        ][
            "source_label_counts"
        ][
            "Market Blogger"
        ]
        == 5
    )


@pytest.mark.parametrize(
    "field,value",
    (
        ("market_price_start", float("nan")),
        ("market_price_end", float("inf")),
        ("portfolio_start_value", float("nan")),
        ("portfolio_end_value", float("-inf")),
    ),
)
def test_non_finite_core_numeric_values_are_rejected(
    field,
    value,
):
    with pytest.raises(
        ValueError,
        match="finite",
    ):
        sample_statistics(
            **{field: value}
        )


@pytest.mark.parametrize(
    "field,value",
    (
        ("start_period", 1.5),
        ("end_period", 4.0),
        ("news_items_available", 1.5),
        ("community_posts_available", True),
    ),
)
def test_integer_contract_fields_reject_silent_coercion(
    field,
    value,
):
    with pytest.raises(
        ValueError,
        match="integer",
    ):
        sample_statistics(
            **{field: value}
        )


def test_eligible_period_rejects_float_coercion():
    with pytest.raises(
        ValueError,
        match="integer",
    ):
        sample_statistics(
            eligible_trading_periods=(
                1,
                2.0,
                3,
                4,
            ),
        )


def test_source_label_count_requires_integer():
    with pytest.raises(
        ValueError,
        match="integer",
    ):
        sample_statistics(
            source_label_counts={
                "Individual Investor": 1.5,
            }
        )


def test_non_finite_confidence_is_rejected():
    with pytest.raises(
        ValueError,
        match="finite",
    ):
        sample_statistics(
            judgements=(
                JudgementObservation(
                    1,
                    "HOLD",
                    float("nan"),
                ),
            )
        )


def test_turnover_rejects_numeric_strings_instead_of_coercing():
    result = calculate_executed_turnover(
        trades_by_day={
            "2023-06-19": (
                "500.0",
            ),
        },
        previous_portfolio_values={
            "2023-06-19": 10000.0,
        },
    )

    assert result is None


def test_hold_trade_and_mixed_trade_are_distinct_categories():
    hold_trade = sample_statistics(
        trades=(
            TradeObservation(
                1,
                "BUY",
            ),
        ),
        behaviour_linked_assessments=(
            AssessmentActionLink(
                1,
                "HOLD",
            ),
        ),
    )

    mixed = sample_statistics(
        trades=(
            TradeObservation(
                1,
                "BUY",
            ),
            TradeObservation(
                1,
                "SELL",
            ),
        ),
        behaviour_linked_assessments=(
            AssessmentActionLink(
                1,
                "HOLD",
            ),
        ),
    )

    assert (
        hold_trade.judgement_action_metrics[
            "hold_with_trade"
        ]
        == 1
    )

    assert (
        hold_trade.judgement_action_metrics[
            "mixed_trading"
        ]
        == 0
    )

    assert (
        mixed.judgement_action_metrics[
            "mixed_trading"
        ]
        == 1
    )

    assert (
        mixed.judgement_action_metrics[
            "hold_with_trade"
        ]
        == 0
    )
