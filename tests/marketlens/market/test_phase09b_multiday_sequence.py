from pathlib import Path

import pytest

from marketlens.agents.activation.policy import ActivationPolicy
from marketlens.agents.activation.profiles import AgentActivationProfile
from marketlens.market.multiday import (
    MultiDayOrchestrationError,
    build_calendar_day_plan,
    dispatch_market_action,
    sample_activation_sequence,
)


def _plan():
    return build_calendar_day_plan(
        start_date="2023-06-15",
        end_date="2023-06-17",
        trading_days={"2023-06-15", "2023-06-16"},
    )


def test_calendar_plan_is_open_open_closed_and_contiguous():
    plan = _plan()

    assert [day.current_date for day in plan] == [
        "2023-06-15",
        "2023-06-16",
        "2023-06-17",
    ]
    assert [day.history_cutoff for day in plan] == [
        "2023-06-14",
        "2023-06-15",
        "2023-06-16",
    ]
    assert [day.market_open for day in plan] == [True, True, False]
    assert [day.expected_market_action for day in plan] == [
        "advance_trading_day",
        "advance_trading_day",
        "advance_non_trading_day",
    ]


def test_participant_trading_gate_depends_only_on_calendar():
    plan = _plan()

    assert [day.participant_trading_enabled for day in plan] == [
        True,
        True,
        False,
    ]


def test_belief_and_forum_stage_follow_inherited_day_sequence():
    plan = _plan()

    assert [day.belief_source for day in plan] == [
        "initial",
        "forum_with_initial_fallback",
        "forum_with_initial_fallback",
    ]
    assert [day.forum_actions_enabled for day in plan] == [
        False,
        True,
        True,
    ]
    assert [day.day_1st for day in plan] == [True, False, False]


def test_phase4_activation_state_is_carried_across_calendar_days():
    policy = ActivationPolicy()
    categories = tuple(policy.config.activity_baselines.keys())
    assert categories

    profiles = tuple(
        AgentActivationProfile(
            user_id=str(index + 1),
            activity_category=categories[index % len(categories)],
        )
        for index in range(3)
    )

    runs = sample_activation_sequence(
        profiles,
        plan=_plan(),
        seed="phase09b-test",
        policy=policy,
    )

    assert [item.batch.step for item in runs] == [0, 1, 2]

    # The frozen Phase 4 sampler updates all profile recency values each step.
    state0 = runs[0].batch.next_state.steps_since_last_activation
    state1 = runs[1].batch.next_state.steps_since_last_activation
    state2 = runs[2].batch.next_state.steps_since_last_activation
    assert set(state0) == {"1", "2", "3"}
    assert set(state1) == {"1", "2", "3"}
    assert set(state2) == {"1", "2", "3"}

    # Re-running with the same seed and step sequence is deterministic.
    repeat = sample_activation_sequence(
        profiles,
        plan=_plan(),
        seed="phase09b-test",
        policy=ActivationPolicy(),
    )
    assert [
        item.batch.active_agent_ids for item in runs
    ] == [
        item.batch.active_agent_ids for item in repeat
    ]
    assert [
        dict(item.batch.next_state.steps_since_last_activation) for item in runs
    ] == [
        dict(item.batch.next_state.steps_since_last_activation) for item in repeat
    ]


def test_open_day_dispatches_only_to_frozen_trading_wrapper(tmp_path):
    calls = []

    def trading(**kwargs):
        calls.append(("trading", kwargs))
        return "open-result"

    def closed(**kwargs):
        calls.append(("closed", kwargs))
        return "closed-result"

    day = _plan()[0]
    result = dispatch_market_action(
        day,
        runtime_db=tmp_path / "runtime.db",
        decision_json=tmp_path / "decisions.json",
        log_dir=tmp_path / "logs",
        advance_trading_day_fn=trading,
        advance_non_trading_day_fn=closed,
    )

    assert result == "open-result"
    assert [kind for kind, _ in calls] == ["trading"]
    assert calls[0][1]["current_date"] == "2023-06-15"


def test_closed_day_dispatches_only_to_frozen_non_trading_wrapper(tmp_path):
    calls = []

    def trading(**kwargs):
        calls.append(("trading", kwargs))
        return "open-result"

    def closed(**kwargs):
        calls.append(("closed", kwargs))
        return "closed-result"

    day = _plan()[2]
    result = dispatch_market_action(
        day,
        runtime_db=tmp_path / "runtime.db",
        advance_trading_day_fn=trading,
        advance_non_trading_day_fn=closed,
    )

    assert result == "closed-result"
    assert [kind for kind, _ in calls] == ["closed"]
    assert calls[0][1]["current_date"] == "2023-06-17"


def test_open_day_requires_existing_decision_boundary_inputs(tmp_path):
    with pytest.raises(MultiDayOrchestrationError, match="decision_json"):
        dispatch_market_action(
            _plan()[0],
            runtime_db=tmp_path / "runtime.db",
            advance_trading_day_fn=lambda **_: None,
            advance_non_trading_day_fn=lambda **_: None,
        )


def test_invalid_date_range_fails_closed():
    with pytest.raises(MultiDayOrchestrationError, match="end_date"):
        build_calendar_day_plan(
            start_date="2023-06-18",
            end_date="2023-06-15",
            trading_days=set(),
        )


def test_market_plan_has_no_agent_activity_input():
    # The constructor derives the gate from dates/calendar only.  No active-ID,
    # order-count, or matched-trade argument exists that could close the market.
    plan = build_calendar_day_plan(
        start_date="2023-06-15",
        end_date="2023-06-15",
        trading_days={"2023-06-15"},
    )
    assert plan[0].market_open is True
    assert plan[0].participant_trading_enabled is True


def test_phase9_module_does_not_call_whole_inherited_init_simulation():
    source = Path("marketlens/market/multiday.py").read_text(encoding="utf-8")
    assert "init_simulation(" not in source
    assert "test_matching_system(" not in source
    assert "update_profiles_table_holiday(" not in source
