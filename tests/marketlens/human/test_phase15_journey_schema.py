from __future__ import annotations

import pytest
from pydantic import ValidationError

from marketlens.human.schemas import (
    ParticipantDecisionJourneyRead,
)


def _payload() -> dict[str, object]:
    return {
        "journey_version": "marketlens-participant-decision-journey-v1",
        "target_stock_id": "TEST",
        "initial_cash": 10000.0,
        "initial_holdings": {},
        "initial_portfolio_value": 10000.0,
        "periods": [
            {
                "period_number": 1,
                "agent_world_date": "2023-06-01",
                "market_open": True,
                "participant_trading_enabled": True,
                "judgements": [
                    {
                        "sequence_within_period": 1,
                        "stock_id": "TEST",
                        "action": "BUY",
                        "confidence": 0.8,
                        "evidence_sources": ["market_information"],
                        "rationale": "example rationale",
                        "submitted_at": "2026-08-30T12:00:00+00:00",
                    }
                ],
                "transactions": [],
                "behaviour_summary": "NO_TRADE",
                "holding_changes": {},
                "portfolio_end": {
                    "cash": 10000.0,
                    "holdings": {},
                    "portfolio_value": 10000.0,
                },
                "period_pnl": 0.0,
                "cumulative_pnl": 0.0,
                "pnl_direction": "FLAT",
                "feedback_boundary": "NONE",
            }
        ],
    }


def test_participant_journey_schema_accepts_safe_projection() -> None:
    result = ParticipantDecisionJourneyRead.model_validate(_payload())

    assert result.journey_version == (
        "marketlens-participant-decision-journey-v1"
    )
    assert result.periods[0].period_number == 1
    assert result.periods[0].behaviour_summary == "NO_TRADE"


@pytest.mark.parametrize(
    "field,value",
    [
        ("episode_id", "episode-e01"),
        ("provider_path", "/private/agent_world.db"),
        ("manifest_sha256", "secret-hash"),
        ("provenance", {"source": "formal-runtime"}),
    ],
)
def test_participant_journey_schema_rejects_internal_top_level_fields(
    field: str,
    value: object,
) -> None:
    payload = _payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        ParticipantDecisionJourneyRead.model_validate(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("round_locked", True),
        ("canonical_close_prices", {"TEST": 101.5}),
    ],
)
def test_participant_journey_schema_rejects_internal_period_inputs(
    field: str,
    value: object,
) -> None:
    payload = _payload()
    period = payload["periods"][0]
    assert isinstance(period, dict)
    period[field] = value

    with pytest.raises(ValidationError):
        ParticipantDecisionJourneyRead.model_validate(payload)
