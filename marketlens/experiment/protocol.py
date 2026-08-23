"""Phase 10 machine-readable experiment protocol contract.

This module validates timing/state semantics only.  It does not run Agents,
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

    if data.get("protocol_version") != "1.0":
        raise ProtocolValidationError("protocol_version must be 1.0")

    world = data.get("world")
    time = data.get("time")
    timeline = data.get("timeline")
    if not isinstance(world, dict) or not isinstance(time, dict) or not isinstance(timeline, list):
        raise ProtocolValidationError("world, time and timeline are required")

    t_init = _iso(world.get("initialization_date"), "world.initialization_date")
    t_visible = _iso(
        world.get("participant_visible_start_date"),
        "world.participant_visible_start_date",
    )
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

    experiment_steps: list[int] = []
    checkpoint_dates: list[str] = []
    open_days = 0
    closed_days = 0
    for tick, row in enumerate(timeline):
        if not isinstance(row, dict):
            raise ProtocolValidationError(f"timeline[{tick}] must be an object")
        if row.get("world_tick") != tick:
            raise ProtocolValidationError("world_tick sequence must be contiguous from zero")
        expected_date = (t_init + timedelta(days=tick)).isoformat()
        if row.get("agent_world_date") != expected_date:
            raise ProtocolValidationError(
                f"timeline[{tick}] agent_world_date must be {expected_date}"
            )
        status = row.get("market_status")
        if status == "OPEN":
            open_days += 1
        elif status == "CLOSED":
            closed_days += 1
        else:
            raise ProtocolValidationError(f"invalid market_status at world_tick {tick}")

        step = row.get("experiment_step")
        judgement = row.get("judgement_required")
        shadow = row.get("shadow_trade_enabled")
        if step is None:
            if judgement is True:
                raise ProtocolValidationError("judgement requires an experiment_step")
        else:
            if not isinstance(step, int) or step < 0:
                raise ProtocolValidationError("experiment_step must be non-negative integer or null")
            experiment_steps.append(step)
            checkpoint_dates.append(expected_date)
            if judgement is not True:
                raise ProtocolValidationError("every Phase 10 participant checkpoint requires judgement")
        if shadow is True and status != "OPEN":
            raise ProtocolValidationError("shadow trading cannot be enabled on CLOSED days")

        if tick < world["pre_roll_calendar_days"]:
            if row.get("stage") != "warm_up":
                raise ProtocolValidationError("all pre-roll ticks must be warm_up")
            if step is not None or judgement is True or shadow is True:
                raise ProtocolValidationError("warm-up cannot contain participant checkpoints/trading")
            if row.get("stimulus_release") != "none":
                raise ProtocolValidationError("warm-up cannot contain controlled stimulus")

    if experiment_steps != list(range(len(experiment_steps))):
        raise ProtocolValidationError("experiment_step values must be contiguous from zero")
    if open_days != world.get("open_days") or closed_days != world.get("closed_days"):
        raise ProtocolValidationError("OPEN/CLOSED counts do not match world summary")

    critical_dates = data.get("participant_critical_dates")
    if critical_dates != checkpoint_dates:
        raise ProtocolValidationError(
            "participant_critical_dates must equal all formal participant checkpoint dates"
        )

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
    if exposure.get("misinformation") != "participant_only":
        raise ProtocolValidationError("misinformation must remain participant_only")
    if exposure.get("correction") != "participant_only":
        raise ProtocolValidationError("correction must remain participant_only")

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
    if population.get("final_n") != 20:
        raise ProtocolValidationError("Phase 10 Protocol v1 freezes final Agent population at N20")
    rule = population.get("selection_rule", {})
    if rule.get("activation_seed_count") != 100:
        raise ProtocolValidationError("formal-horizon comparison must use all 100 seeds")
    if rule.get("critical_date_any_zero_max_trajectories") != 5:
        raise ProtocolValidationError("critical zero-active threshold drifted")
    if float(rule.get("critical_date_min_mean_active_agents", -1)) != 3.0:
        raise ProtocolValidationError("critical-date minimum mean active threshold drifted")

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
