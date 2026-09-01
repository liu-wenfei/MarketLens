from marketlens.human.routers.feedback import (
    _participant_statistics_projection,
)


def _statistics():
    return {
        "window": {
            "start_period": 1,
            "end_period": 4,
            "periods_reviewed": 4,
        },
        "market_metrics": {"price_change_pct": 9.0},
        "judgement_metrics": {
            "first_assessment": "HOLD",
            "latest_assessment": "BUY",
            "revision_count": 1,
        },
        "confidence_metrics": {
            "first": 50.0,
            "latest": 70.0,
            "change_points": 20.0,
            "mean": 60.0,
            "minimum": 50.0,
            "maximum": 70.0,
        },
        "trading_metrics": {
            "eligible_periods": 4,
            "trade_periods": 1,
            "no_trade_periods": 3,
            "transaction_count": 1,
            "buy_actions": 1,
            "sell_actions": 0,
            "trading_activity_pct": 25.0,
        },
        "judgement_action_metrics": {
            "same_direction_actions": 1
        },
        "portfolio_metrics": {
            "starting_value": 1000.0,
            "ending_value": 1020.0,
            "absolute_change": 20.0,
            "change_pct": 2.0,
        },
        "information_metrics": {
            "news_items_available": 10
        },
    }


def test_early_projection_is_low_intervention():
    result = _participant_statistics_projection(
        reflection_stage="early",
        statistics=_statistics(),
    )

    assert set(result) == {
        "window",
        "judgement_metrics",
        "confidence_metrics",
        "trading_metrics",
    }
    assert set(result["confidence_metrics"]) == {
        "first",
        "latest",
        "change_points",
    }
    assert set(result["trading_metrics"]) == {
        "trade_periods",
        "no_trade_periods",
        "transaction_count",
    }
    assert "portfolio_metrics" not in result
    assert "market_metrics" not in result
    assert "information_metrics" not in result


def test_mid_session_projection_adds_longitudinal_metrics():
    stats = _statistics()
    stats["information_metrics"]["participant_reported_evidence"] = {
        "total_selections": 3,
        "assessments_with_evidence": 2,
        "unique_reported_sources": 2,
        "repeated_selections": 1,
        "evidence_set_changes": 1,
    }
    stats["window"] = {
        "start_period": 5,
        "end_period": 11,
        "periods_reviewed": 7,
    }

    result = _participant_statistics_projection(
        reflection_stage="mid_session",
        statistics=stats,
    )

    assert result["confidence_metrics"]["mean"] == 60.0
    assert result["confidence_metrics"]["minimum"] == 50.0
    assert result["confidence_metrics"]["maximum"] == 70.0
    assert result["portfolio_metrics"]["absolute_change"] == 20.0
    assert result["portfolio_metrics"]["change_pct"] == 2.0
    assert "market_metrics" not in result
    assert "information_metrics" not in result


def test_final_projection_accepts_future_final_only_group():
    stats = _statistics()
    stats["information_metrics"]["participant_reported_evidence"] = {
        "total_selections": 3,
        "assessments_with_evidence": 2,
        "unique_reported_sources": 2,
        "repeated_selections": 1,
        "evidence_set_changes": 1,
    }
    stats["trading_metrics"]["gross_executed_notional"] = 200.0
    stats["window"] = {
        "start_period": 1,
        "end_period": 15,
        "periods_reviewed": 15,
    }
    stats["final_only_metrics"] = {
        "maximum_drawdown": {
            "available": True,
            "value_pct": 3.0,
            "reason": None,
        }
    }

    result = _participant_statistics_projection(
        reflection_stage="final",
        statistics=stats,
    )

    assert "final_only_metrics" in result
    assert "market_metrics" not in result
    assert "information_metrics" not in result
