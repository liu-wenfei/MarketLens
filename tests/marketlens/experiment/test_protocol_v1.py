from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketlens.experiment.protocol import (
    ProtocolValidationError,
    load_protocol,
    participant_checkpoints,
    validate_protocol,
)


def test_protocol_v1_freezes_exact_time_mapping_and_participant_checkpoints():
    protocol = load_protocol()

    assert protocol["population"]["final_n"] == 20
    assert protocol["world"] == {
        "initialization_date": "2023-06-15",
        "participant_visible_start_date": "2023-06-19",
        "end_date": "2023-06-28",
        "pre_roll_calendar_days": 4,
        "participant_visible_calendar_days": 10,
        "formal_world_ticks": 14,
        "open_days": 8,
        "closed_days": 6,
    }

    checkpoints = participant_checkpoints(protocol)
    assert [(row["experiment_step"], row["world_tick"], row["agent_world_date"]) for row in checkpoints] == [
        (0, 4, "2023-06-19"),
        (1, 5, "2023-06-20"),
        (2, 6, "2023-06-21"),
        (3, 11, "2023-06-26"),
        (4, 13, "2023-06-28"),
    ]


def test_protocol_keeps_misinformation_and_correction_participant_only():
    protocol = load_protocol()
    assert protocol["stimulus_exposure"]["misinformation"] == "participant_only"
    assert protocol["stimulus_exposure"]["correction"] == "participant_only"
    assert protocol["stimulus_exposure"]["persistence_policy"] == (
        "misinformation_remains_available_without_new_dose"
    )


def test_protocol_freezes_canonical_shadow_price_source():
    source = load_protocol()["participant_market_role"]["shadow_trade_price_source"]
    assert source == {
        "source_kind": "sealed_canonical_agent_world_sqlite",
        "table": "StockData",
        "field": "close_price",
        "stock_key": "stock_id",
        "date_key": "date",
        "lookup": "exact_stock_id_and_agent_world_date",
        "frontend_override_allowed": False,
        "forward_fill_allowed": False,
        "nearest_date_fallback_allowed": False,
        "missing_price_policy": "fail_closed_no_participant_execution",
    }


def test_protocol_rejects_round_like_tick_date_drift():
    protocol = load_protocol()
    protocol["timeline"][11]["agent_world_date"] = "2023-06-22"
    with pytest.raises(ProtocolValidationError):
        validate_protocol(protocol)


def test_protocol_rejects_shadow_trading_on_closed_day():
    protocol = load_protocol()
    protocol["timeline"][7]["shadow_trade_enabled"] = True
    with pytest.raises(ProtocolValidationError):
        validate_protocol(protocol)


def test_protocol_file_contains_no_tbd_placeholders():
    path = Path(__file__).resolve().parents[3] / "marketlens" / "experiment" / "protocol_v1.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    validate_protocol(raw)
