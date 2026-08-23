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


def test_protocol_v1_1_freezes_long_horizon_time_mapping_and_decision_checkpoints():
    protocol = load_protocol()

    assert protocol["protocol_version"] == "1.1"
    assert protocol["population"]["final_n"] == 30
    assert protocol["world"] == {
        "initialization_date": "2023-06-15",
        "participant_visible_start_date": "2023-06-19",
        "end_date": "2023-07-11",
        "pre_roll_calendar_days": 4,
        "participant_visible_calendar_days": 23,
        "formal_world_ticks": 27,
        "open_days": 17,
        "closed_days": 10,
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
        (7, 15, "2023-06-30"),
        (8, 18, "2023-07-03"),
        (9, 19, "2023-07-04"),
        (10, 20, "2023-07-05"),
        (11, 21, "2023-07-06"),
        (12, 22, "2023-07-07"),
        (13, 25, "2023-07-10"),
        (14, 26, "2023-07-11"),
    ]
    assert all(row["behaviour_decision_required"] for row in checkpoints)
    assert all(row["shadow_trade_enabled"] for row in checkpoints)
    assert protocol["participant_critical_dates"] == [row["agent_world_date"] for row in checkpoints]


def test_formal_judgements_use_three_dates_and_same_state_pre_post_pairs():
    protocol = load_protocol()
    rows = formal_judgement_rows(protocol)
    assert [(row["agent_world_date"], row["formal_judgement_events"]) for row in rows] == [
        ("2023-06-19", ["J0", "J1"]),
        ("2023-06-30", ["J2", "J3"]),
        ("2023-07-11", ["J4"]),
    ]
    assert protocol["time"]["formal_judgement_events"] == 5
    assert protocol["time"]["formal_judgement_dates"] == 3
    assert protocol["time"]["participant_decision_days"] == 15


def test_protocol_freezes_seven_open_transition_intervals_and_within_checkpoint_ordering():
    protocol = load_protocol()
    timing = protocol["timing_design"]
    assert timing["misinformation_to_persistence_open_transitions"] == 7
    assert timing["correction_to_later_j4_open_transitions"] == 7
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


def test_protocol_freezes_n30_after_exact_horizon_fail_pass_and_real_backend_pass():
    population = load_protocol()["population"]
    evidence = population["selection_evidence"]
    assert population["final_n"] == 30
    assert evidence["n_world_ticks"] == 27
    assert evidence["participant_critical_date_count"] == 15
    assert evidence["n20"]["sufficient"] is False
    assert evidence["n20"]["critical_any_zero_trajectories"] == 9
    assert evidence["n30"]["sufficient"] is True
    assert evidence["n30"]["critical_any_zero_trajectories"] == 0
    assert evidence["n30"]["minimum_critical_date_mean_active_agents"] == 6.26
    real = evidence["n30_real_backend_validation"]
    assert real["status"] == "PASS"
    assert real["git_commit"] == "8b4704b"
    assert real["active_agents"] == [10, 7, 3]
    assert real["posts_created_total"] == 20
    assert real["forum_belief_agents_observed"] == 25
    assert real["later_day_forum_action_calls"] == 10
    assert real["continuity_pass"] is True


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
    protocol["timeline"][15]["agent_world_date"] = "2023-06-29"
    with pytest.raises(ProtocolValidationError):
        validate_protocol(protocol)


def test_protocol_rejects_checkpoint_without_behavioural_decision():
    protocol = load_protocol()
    protocol["timeline"][20]["behaviour_decision_required"] = False
    with pytest.raises(ProtocolValidationError):
        validate_protocol(protocol)


def test_protocol_rejects_shadow_trading_on_closed_day():
    protocol = load_protocol()
    protocol["timeline"][16]["experiment_step"] = 15
    protocol["timeline"][16]["participant_visible"] = True
    protocol["timeline"][16]["behaviour_decision_required"] = True
    protocol["timeline"][16]["shadow_trade_enabled"] = True
    with pytest.raises(ProtocolValidationError):
        validate_protocol(protocol)


def test_protocol_rejects_n30_freeze_without_real_backend_pass():
    protocol = load_protocol()
    protocol["population"]["selection_evidence"]["n30_real_backend_validation"]["status"] = "FAIL"
    with pytest.raises(ProtocolValidationError):
        validate_protocol(protocol)


def test_protocol_file_contains_no_tbd_placeholders():
    path = Path(__file__).resolve().parents[3] / "marketlens" / "experiment" / "protocol_v1.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    validate_protocol(raw)
