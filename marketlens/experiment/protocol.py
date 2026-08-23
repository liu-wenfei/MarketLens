"""Phase 10 machine-readable experiment protocol contract.

This module validates timing/state semantics only. It does not run Agents,
inject stimuli, form prices, clone participant worlds, or implement Phase 11.
"""

from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any, Mapping


class ProtocolValidationError(ValueError):
    """Raised when the frozen Phase 10 protocol contract is internally invalid."""


def default_protocol_path() -> Path:
    return Path(__file__).with_name("protocol_v1.json")


def _iso(value: object, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ProtocolValidationError(f"{field} must be ISO YYYY-MM-DD") from exc


def _scan_unresolved(value: object, path: str = "protocol") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _scan_unresolved(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_unresolved(child, f"{path}[{index}]")
    elif isinstance(value, str):
        upper = value.upper()
        if "<FROZEN" in upper or "TBD" in upper or "PLACEHOLDER" in upper:
            raise ProtocolValidationError(f"unresolved protocol value at {path}: {value!r}")


def validate_protocol(protocol: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a plain mutable copy of Protocol v1."""

    data = json.loads(json.dumps(protocol))
    _scan_unresolved(data)

    if data.get("protocol_version") != "1.1":
        raise ProtocolValidationError("protocol_version must be 1.1")

    world = data.get("world")
    time = data.get("time")
    timing = data.get("timing_design")
    timeline = data.get("timeline")
    if not all(isinstance(value, dict) for value in (world, time, timing)) or not isinstance(timeline, list):
        raise ProtocolValidationError("world, time, timing_design and timeline are required")

    t_init = _iso(world.get("initialization_date"), "world.initialization_date")
    t_visible = _iso(world.get("participant_visible_start_date"), "world.participant_visible_start_date")
    t_end = _iso(world.get("end_date"), "world.end_date")
    if not t_init < t_visible < t_end:
        raise ProtocolValidationError("require T_init < T_visible < T_end")

    expected_ticks = (t_end - t_init).days + 1
    if world.get("formal_world_ticks") != expected_ticks:
        raise ProtocolValidationError("formal_world_ticks must equal inclusive calendar horizon")
    if len(timeline) != expected_ticks:
        raise ProtocolValidationError("timeline length must equal formal_world_ticks")
    if world.get("pre_roll_calendar_days") != (t_visible - t_init).days:
        raise ProtocolValidationError("pre_roll_calendar_days does not match T_visible")
    if world.get("participant_visible_calendar_days") != (t_end - t_visible).days + 1:
        raise ProtocolValidationError("participant_visible_calendar_days does not match dates")

    if time.get("world_tick_is_calendar_day") is not True:
        raise ProtocolValidationError("world_tick must be a calendar day")
    if time.get("experiment_step_definition") != "participant_checkpoint":
        raise ProtocolValidationError("experiment_step must mean participant_checkpoint")
    if time.get("experiment_step_separate_from_world_tick") is not True:
        raise ProtocolValidationError("experiment_step must remain separate from world_tick")
    if time.get("experiment_step_separate_from_agent_world_date") is not True:
        raise ProtocolValidationError("experiment_step must remain separate from agent_world_date")
    if time.get("experimental_delay_unit") != "open_state_transition":
        raise ProtocolValidationError("experimental delay must be expressed in OPEN-state transitions")
    if time.get("closed_days_advance_world_tick_but_not_open_transition_delay") is not True:
        raise ProtocolValidationError("CLOSED days must advance world_tick without counting as OPEN delays")

    expected_timing = {
        "baseline_to_misinformation_world_ticks": 0,
        "misinformation_to_immediate_j1_world_ticks": 0,
        "misinformation_to_persistence_open_transitions": 7,
        "persistence_to_correction_world_ticks": 0,
        "correction_to_immediate_j3_world_ticks": 0,
        "correction_to_later_j4_open_transitions": 7,
    }
    for key, value in expected_timing.items():
        if timing.get(key) != value:
            raise ProtocolValidationError(f"timing contract drifted: {key}")
    if timing.get("same_state_pairs") != [["J0", "J1"], ["J2", "J3"]]:
        raise ProtocolValidationError("same-state judgement pairs drifted")

    experiment_steps: list[int] = []
    checkpoint_dates: list[str] = []
    judgement_locations: dict[str, tuple[int, str]] = {}
    judgement_event_count = 0
    judgement_dates: set[str] = set()
    open_days = 0
    closed_days = 0

    for tick, row in enumerate(timeline):
        if not isinstance(row, dict):
            raise ProtocolValidationError(f"timeline[{tick}] must be an object")
        if row.get("world_tick") != tick:
            raise ProtocolValidationError("world_tick sequence must be contiguous from zero")
        expected_date = (t_init + timedelta(days=tick)).isoformat()
        if row.get("agent_world_date") != expected_date:
            raise ProtocolValidationError(f"timeline[{tick}] agent_world_date must be {expected_date}")

        status = row.get("market_status")
        if status == "OPEN":
            open_days += 1
        elif status == "CLOSED":
            closed_days += 1
        else:
            raise ProtocolValidationError(f"invalid market_status at world_tick {tick}")

        step = row.get("experiment_step")
        visible = row.get("participant_visible")
        judgements = row.get("formal_judgement_events")
        decision = row.get("behaviour_decision_required")
        shadow = row.get("shadow_trade_enabled")
        if not isinstance(judgements, list):
            raise ProtocolValidationError("formal_judgement_events must be a list")

        if step is None:
            if visible is True or decision is True or shadow is True or judgements:
                raise ProtocolValidationError("world-only tick cannot contain participant checkpoint activity")
        else:
            if not isinstance(step, int) or step < 0:
                raise ProtocolValidationError("experiment_step must be non-negative integer or null")
            if status != "OPEN":
                raise ProtocolValidationError("participant checkpoints must occur on OPEN market dates")
            if visible is not True or decision is not True or shadow is not True:
                raise ProtocolValidationError("every participant checkpoint must be visible and record one shadow decision")
            experiment_steps.append(step)
            checkpoint_dates.append(expected_date)

        for event in judgements:
            if event in judgement_locations:
                raise ProtocolValidationError(f"duplicate formal judgement event: {event}")
            judgement_locations[event] = (tick, expected_date)
            judgement_event_count += 1
            judgement_dates.add(expected_date)

        if shadow is True and status != "OPEN":
            raise ProtocolValidationError("shadow trading cannot be enabled on CLOSED days")

        if tick < world["pre_roll_calendar_days"]:
            if row.get("stage") != "warm_up":
                raise ProtocolValidationError("all pre-roll ticks must be warm_up")
            if step is not None or visible is True or decision is True or shadow is True or judgements:
                raise ProtocolValidationError("warm-up cannot contain participant activity")
            if row.get("stimulus_release") != "none":
                raise ProtocolValidationError("warm-up cannot contain controlled stimulus")

    if experiment_steps != list(range(len(experiment_steps))):
        raise ProtocolValidationError("experiment_step values must be contiguous from zero")
    if open_days != world.get("open_days") or closed_days != world.get("closed_days"):
        raise ProtocolValidationError("OPEN/CLOSED counts do not match world summary")
    if len(experiment_steps) != int(time.get("participant_decision_days", -1)):
        raise ProtocolValidationError("participant_decision_days must equal participant checkpoint count")
    if judgement_event_count != int(time.get("formal_judgement_events", -1)):
        raise ProtocolValidationError("formal_judgement_events count drifted")
    if len(judgement_dates) != int(time.get("formal_judgement_dates", -1)):
        raise ProtocolValidationError("formal_judgement_dates count drifted")
    if set(judgement_locations) != {"J0", "J1", "J2", "J3", "J4"}:
        raise ProtocolValidationError("formal judgement event set must be J0..J4")
    if judgement_locations["J0"] != judgement_locations["J1"]:
        raise ProtocolValidationError("J0/J1 must share one canonical state")
    if judgement_locations["J2"] != judgement_locations["J3"]:
        raise ProtocolValidationError("J2/J3 must share one canonical state")

    checkpoint_step_by_date = {current_date: step for step, current_date in zip(experiment_steps, checkpoint_dates)}
    j01_date = judgement_locations["J0"][1]
    j23_date = judgement_locations["J2"][1]
    j4_date = judgement_locations["J4"][1]
    try:
        misinformation_to_persistence = checkpoint_step_by_date[j23_date] - checkpoint_step_by_date[j01_date]
        correction_to_later = checkpoint_step_by_date[j4_date] - checkpoint_step_by_date[j23_date]
    except KeyError as exc:
        raise ProtocolValidationError("formal judgement dates must also be participant checkpoints") from exc
    if misinformation_to_persistence != timing["misinformation_to_persistence_open_transitions"]:
        raise ProtocolValidationError("timeline does not realize the frozen misinformation-to-persistence OPEN delay")
    if correction_to_later != timing["correction_to_later_j4_open_transitions"]:
        raise ProtocolValidationError("timeline does not realize the frozen correction-to-J4 OPEN delay")

    critical_dates = data.get("participant_critical_dates")
    if critical_dates != checkpoint_dates:
        raise ProtocolValidationError("participant_critical_dates must equal all participant decision dates")

    behavior = data.get("participant_behavior", {})
    expected_behavior = {
        "decision_required_on_every_participant_checkpoint": True,
        "participant_checkpoint_only_on_open_market_dates": True,
        "action_space": ["BUY", "SELL", "HOLD"],
        "hold_is_valid_decision": True,
        "quantity_required_for_buy_sell": True,
        "portfolio_state_recorded_automatically": True,
        "formal_judgement_not_required_on_every_decision_day": True,
    }
    if behavior != expected_behavior:
        raise ProtocolValidationError("participant behavioural-observation contract drifted")

    role = data.get("participant_market_role", {})
    if role.get("price_taker") is not True or role.get("orders_enter_agent_matching_engine") is not False:
        raise ProtocolValidationError("participant must remain a price taker outside Agent matching")
    price_source = role.get("shadow_trade_price_source", {})
    expected_price_contract = {
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
    if price_source != expected_price_contract:
        raise ProtocolValidationError("shadow-trade price source contract drifted")

    exposure = data.get("stimulus_exposure", {})
    if exposure.get("misinformation") != "participant_only" or exposure.get("correction") != "participant_only":
        raise ProtocolValidationError("misinformation/correction must remain participant_only")
    if exposure.get("misinformation_release_policy") != "single_release_no_redose":
        raise ProtocolValidationError("misinformation must be released once")
    if exposure.get("correction_persistence_policy") != "remains_available_from_release_through_experiment_end":
        raise ProtocolValidationError("correction persistence contract drifted")

    warm_up = data.get("warm_up", {})
    warm_rule = warm_up.get("selection_rule", {})
    if warm_rule.get("candidate_calendar_days") != [2, 3, 4, 5, 6]:
        raise ProtocolValidationError("warm-up candidate set drifted")
    if warm_rule.get("minimum_episode_local_open_ticks_before_entry") != 2:
        raise ProtocolValidationError("warm-up OPEN-tick minimum drifted")
    if warm_rule.get("minimum_episode_local_closed_ticks_before_entry") != 1:
        raise ProtocolValidationError("warm-up CLOSED-tick minimum drifted")
    if warm_rule.get("participant_visible_start_must_be_open") is not True:
        raise ProtocolValidationError("T_visible must be OPEN")
    if warm_rule.get("choose_smallest_sufficient_candidate") is not True:
        raise ProtocolValidationError("warm-up selection must use smallest sufficient candidate")
    if warm_up.get("selected_calendar_days") != world.get("pre_roll_calendar_days"):
        raise ProtocolValidationError("selected warm-up length must equal pre-roll length")

    canonical = data.get("canonical_world", {})
    required_true = (
        "generated_once",
        "generated_before_participant_exposure",
        "shared_across_participants",
        "immutable_during_formal_collection",
        "participant_observes_completed_state",
        "snapshot_is_storage_not_market_generator",
    )
    if any(canonical.get(key) is not True for key in required_true):
        raise ProtocolValidationError("canonical-world invariants drifted")

    population = data.get("population", {})
    if population.get("candidates") != [20, 30]:
        raise ProtocolValidationError("Phase 10 population candidates must be N20/N30")
    if population.get("final_n") != 30:
        raise ProtocolValidationError("Phase 10 Protocol v1.1 freezes final Agent population at N30")
    rule = population.get("selection_rule", {})
    if rule.get("activation_seed_count") != 100:
        raise ProtocolValidationError("formal-horizon comparison must use all 100 seeds")
    if rule.get("critical_date_any_zero_max_trajectories") != 5:
        raise ProtocolValidationError("critical zero-active threshold drifted")
    if float(rule.get("critical_date_min_mean_active_agents", -1)) != 3.0:
        raise ProtocolValidationError("critical-date minimum mean active threshold drifted")

    evidence = population.get("selection_evidence", {})
    if evidence.get("n_world_ticks") != 27 or evidence.get("participant_critical_date_count") != 15:
        raise ProtocolValidationError("v1.1 population evidence must describe the exact 27-tick / 15-decision horizon")
    if evidence.get("n20", {}).get("sufficient") is not False:
        raise ProtocolValidationError("v1.1 must preserve the N20 exact-horizon FAIL result")
    if evidence.get("n30", {}).get("sufficient") is not True:
        raise ProtocolValidationError("v1.1 must preserve the N30 exact-horizon PASS result")
    real = evidence.get("n30_real_backend_validation", {})
    if real.get("status") != "PASS":
        raise ProtocolValidationError("N30 final freeze requires the completed real-backend PASS")
    if real.get("population_size") != 30:
        raise ProtocolValidationError("N30 real-backend evidence population size drifted")
    if real.get("selected_agent_ids_sha256") != "60d846b21c15e2213f6f897a17a7ea98039fbf461abe54ee89e1b6779d24b2d4":
        raise ProtocolValidationError("N30 frozen membership digest drifted")
    if real.get("activation_seed") != "marketlens-phase09b-activation-01":
        raise ProtocolValidationError("N30 real-backend activation reference seed drifted")
    if real.get("active_agents") != [10, 7, 3]:
        raise ProtocolValidationError("N30 real-backend activation sequence drifted")
    if real.get("continuity_pass") is not True:
        raise ProtocolValidationError("N30 real-backend continuity PASS is required")

    return data


def load_protocol(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path is not None else default_protocol_path()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtocolValidationError(f"cannot load protocol: {source}") from exc
    if not isinstance(raw, dict):
        raise ProtocolValidationError("protocol root must be an object")
    return validate_protocol(raw)


def participant_checkpoints(protocol: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], ...]:
    data = validate_protocol(protocol) if protocol is not None else load_protocol()
    return tuple(row for row in data["timeline"] if row["experiment_step"] is not None)


def formal_judgement_rows(protocol: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], ...]:
    data = validate_protocol(protocol) if protocol is not None else load_protocol()
    return tuple(row for row in data["timeline"] if row["formal_judgement_events"])
