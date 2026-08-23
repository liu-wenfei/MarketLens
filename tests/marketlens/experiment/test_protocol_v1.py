from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketlens.experiment.protocol import (
    ProtocolValidationError,
    formal_judgement_rows,
    load_protocol,
    participant_checkpoints,
    validate_protocol,
)


def test_protocol_v1_freezes_amended_time_mapping_and_decision_checkpoints():
    protocol = load_protocol()

    assert protocol["population"]["final_n"] == 20
    assert protocol["world"] == {
        "initialization_date": "2023-06-15",
        "participant_visible_start_date": "2023-06-19",
        "end_date": "2023-06-29",
        "pre_roll_calendar_days": 4,
        "participant_visible_calendar_days": 11,
        "formal_world_ticks": 15,
        "open_days": 9,
        "closed_days": 6,
    }

    checkpoints = participant_checkpoints(protocol)
    assert [(row["experiment_step"], row["world_tick"], row["agent_world_date"]) for row in checkpoints] == [
        (0, 4, "2023-06-19"),
        (1, 5, "2023-06-20"),
        (2, 6, "2023-06-21"),
        (3, 11, "2023-06-26"),
        (4, 12, "2023-06-27"),
        (5, 13, "2023-06-28"),
        (6, 14, "2023-06-29"),
    ]
    assert all(row["behaviour_decision_required"] for row in checkpoints)
    assert all(row["shadow_trade_enabled"] for row in checkpoints)


def test_formal_judgements_use_three_dates_and_same_state_pre_post_pairs():
    protocol = load_protocol()
    rows = formal_judgement_rows(protocol)
    assert [(row["agent_world_date"], row["formal_judgement_events"]) for row in rows] == [
        ("2023-06-19", ["J0", "J1"]),
        ("2023-06-26", ["J2", "J3"]),
        ("2023-06-29", ["J4"]),
    ]
    assert protocol["time"]["formal_judgement_events"] == 5
    assert protocol["time"]["formal_judgement_dates"] == 3
    assert protocol["time"]["participant_decision_days"] == 7


def test_protocol_freezes_open_transition_intervals_and_within_checkpoint_ordering():
    protocol = load_protocol()
    timing = protocol["timing_design"]
    assert timing["misinformation_to_persistence_open_transitions"] == 3
    assert timing["correction_to_later_j4_open_transitions"] == 3
    assert timing["baseline_to_misinformation_world_ticks"] == 0
    assert timing["correction_to_immediate_j3_world_ticks"] == 0
    assert timing["same_state_pairs"] == [["J0", "J1"], ["J2", "J3"]]
    assert timing["within_checkpoint_ordering"]["misinformation_checkpoint"][2:5] == [
        "J0_baseline_judgement_confidence",
        "misinformation_release",
        "J1_immediate_post_misinformation_judgement_confidence",
    ]
    assert timing["within_checkpoint_ordering"]["correction_checkpoint"][2:5] == [
        "J2_persistence_pre_correction_judgement_confidence",
        "authoritative_correction_release",
        "J3_immediate_post_correction_judgement_confidence",
    ]


def test_protocol_keeps_misinformation_and_correction_participant_only_and_persistent():
    exposure = load_protocol()["stimulus_exposure"]
    assert exposure["misinformation"] == "participant_only"
    assert exposure["correction"] == "participant_only"
    assert exposure["misinformation_release_policy"] == "single_release_no_redose"
    assert exposure["misinformation_persistence_policy"] == (
        "remains_available_through_persistence_and_remains_in_history_after_correction"
    )
    assert exposure["correction_persistence_policy"] == (
        "remains_available_from_release_through_experiment_end"
    )


def test_protocol_freezes_every_open_checkpoint_behavioural_decision_contract():
    behavior = load_protocol()["participant_behavior"]
    assert behavior["decision_required_on_every_participant_checkpoint"] is True
    assert behavior["participant_checkpoint_only_on_open_market_dates"] is True
    assert behavior["action_space"] == ["BUY", "SELL", "HOLD"]
    assert behavior["hold_is_valid_decision"] is True
    assert behavior["portfolio_state_recorded_automatically"] is True
    assert behavior["formal_judgement_not_required_on_every_decision_day"] is True


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


def test_protocol_rejects_checkpoint_without_behavioural_decision():
    protocol = load_protocol()
    protocol["timeline"][12]["behaviour_decision_required"] = False
    with pytest.raises(ProtocolValidationError):
        validate_protocol(protocol)


def test_protocol_rejects_shadow_trading_on_closed_day():
    protocol = load_protocol()
    protocol["timeline"][7]["experiment_step"] = 7
    protocol["timeline"][7]["participant_visible"] = True
    protocol["timeline"][7]["behaviour_decision_required"] = True
    protocol["timeline"][7]["shadow_trade_enabled"] = True
    with pytest.raises(ProtocolValidationError):
        validate_protocol(protocol)


def test_protocol_file_contains_no_tbd_placeholders():
    path = Path(__file__).resolve().parents[3] / "marketlens" / "experiment" / "protocol_v1.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    validate_protocol(raw)
