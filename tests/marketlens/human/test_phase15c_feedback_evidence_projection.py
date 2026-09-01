from marketlens.human.routers.feedback import (
    _participant_statistics_projection,
)


def _statistics():
    return {
        "window": {
            "start_period": 5,
            "end_period": 11,
            "periods_reviewed": 7,
        },
        "judgement_metrics": {
            "first_assessment": "BUY",
            "latest_assessment": "HOLD",
            "revision_count": 1,
        },
        "confidence_metrics": {
            "first": 60.0,
            "latest": 55.0,
            "change_points": -5.0,
            "mean": 57.5,
            "minimum": 55.0,
            "maximum": 60.0,
        },
        "trading_metrics": {
            "eligible_periods": 7,
            "trade_periods": 2,
            "no_trade_periods": 5,
            "transaction_count": 3,
            "buy_actions": 2,
            "sell_actions": 1,
            "trading_activity_pct": 28.57,
            "gross_executed_notional": 250.0,
        },
        "portfolio_metrics": {
            "starting_value": 1000.0,
            "ending_value": 1025.0,
            "absolute_change": 25.0,
            "change_pct": 2.5,
        },
        "information_metrics": {
            "news_items_available": 99,
            "community_posts_available": 88,
            "source_label_counts": {"forum": 88},
            "participant_reported_evidence": {
                "total_selections": 4,
                "assessments_with_evidence": 2,
                "unique_reported_sources": 3,
                "repeated_selections": 1,
                "evidence_set_changes": 1,
            },
        },
    }


def test_mid_session_exposes_reported_evidence_but_not_availability_or_notional():
    payload = _participant_statistics_projection(
        reflection_stage="mid_session",
        statistics=_statistics(),
    )

    assert payload["reported_evidence_metrics"] == {
        "total_selections": 4,
        "assessments_with_evidence": 2,
        "unique_reported_sources": 3,
        "repeated_selections": 1,
        "evidence_set_changes": 1,
    }
    assert "information_metrics" not in payload
    assert (
        "gross_executed_notional"
        not in payload["trading_metrics"]
    )


def test_final_exposes_gross_notional_and_reported_evidence():
    statistics = _statistics()
    statistics["window"] = {
        "start_period": 1,
        "end_period": 15,
        "periods_reviewed": 15,
    }

    payload = _participant_statistics_projection(
        reflection_stage="final",
        statistics=statistics,
    )

    assert payload["trading_metrics"][
        "gross_executed_notional"
    ] == 250.0
    assert payload["reported_evidence_metrics"][
        "unique_reported_sources"
    ] == 3
    assert "information_metrics" not in payload


def test_early_hides_reported_evidence_and_gross_notional():
    statistics = _statistics()
    statistics["window"] = {
        "start_period": 1,
        "end_period": 4,
        "periods_reviewed": 4,
    }

    payload = _participant_statistics_projection(
        reflection_stage="early",
        statistics=statistics,
    )

    assert "reported_evidence_metrics" not in payload
    assert "portfolio_metrics" not in payload
    assert "gross_executed_notional" not in payload[
        "trading_metrics"
    ]
    assert "information_metrics" not in payload
