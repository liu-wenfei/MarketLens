"""Phase 13C canonical Agent-world episode freeze contract.

This module does not execute an LLM or generate a canonical world.  It freezes
and validates the zero-LLM execution plan and the minimum manifest contract that
an eventual one-off formal producer must satisfy.
"""
from __future__ import annotations

import csv
import json
import re
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from marketlens.stimulus.manifest import sha256_json


class CanonicalEpisodeContractError(ValueError):
    """Raised when the predeclared canonical-episode identity drifts."""


EPISODE_ID = "marketlens-canonical-episode-v1"
PLAN_VERSION = "1.0"
PLAN_STATUS = "formal_execution_plan_frozen"
PROTOCOL_VERSION = "1.1"
POPULATION_SIZE = 30
POPULATION_SEED = "marketlens-dev-population-01"
SELECTED_AGENT_IDS_SHA256 = (
    "60d846b21c15e2213f6f897a17a7ea98039fbf461abe54ee89e1b6779d24b2d4"
)
ACTIVATION_SEED = "marketlens-phase09b-activation-01"
EXPECTED_WORLD_TICKS = 27
EXPECTED_AGENT_PIPELINE_EXECUTIONS = 193
EXPECTED_EXECUTION_PLAN_SHA256 = "58e347d4d7b6400555c0533db88b387d5f16f5f991020f758a5cd6477b08ac96"
FORMAL_AGENT_WORLD_DB = "data/marketlens/canonical_episode/v1/agent_world.db"
FORMAL_FORUM_DB = "data/marketlens/canonical_episode/v1/forum.db"
FORMAL_EPISODE_MANIFEST = "data/marketlens/canonical_episode/v1/episode_manifest.json"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def default_plan_path() -> Path:
    return Path(__file__).with_name("execution_plan_v1.json")


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def execution_plan_sha256(plan: Mapping[str, Any]) -> str:
    return sha256_json(dict(plan))


def load_execution_plan(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path is not None else default_plan_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalEpisodeContractError(f"cannot load canonical execution plan: {source}") from exc
    if not isinstance(payload, dict):
        raise CanonicalEpisodeContractError("canonical execution plan root must be an object")
    validate_execution_plan(payload)
    return payload


def validate_execution_plan(plan: Mapping[str, Any]) -> None:
    if execution_plan_sha256(plan) != EXPECTED_EXECUTION_PLAN_SHA256:
        raise CanonicalEpisodeContractError("canonical execution-plan SHA-256 drifted")
    if plan.get("plan_schema_version") != "marketlens-canonical-episode-execution-plan/1.0":
        raise CanonicalEpisodeContractError("canonical plan schema version drifted")
    if plan.get("plan_version") != PLAN_VERSION or plan.get("status") != PLAN_STATUS:
        raise CanonicalEpisodeContractError("canonical plan version/status drifted")
    if plan.get("episode_id") != EPISODE_ID or plan.get("protocol_version") != PROTOCOL_VERSION:
        raise CanonicalEpisodeContractError("canonical episode/protocol identity drifted")

    population = plan.get("population", {})
    if population.get("size") != POPULATION_SIZE:
        raise CanonicalEpisodeContractError("formal population must remain N30")
    if population.get("selection_seed") != POPULATION_SEED:
        raise CanonicalEpisodeContractError("formal population seed drifted")
    if population.get("selected_agent_ids_sha256") != SELECTED_AGENT_IDS_SHA256:
        raise CanonicalEpisodeContractError("formal N30 membership digest drifted")
    guard = population.get("initial_fixture_semantic_guard", {})
    expected_counts = {"Profiles": 30, "Strategy": 30, "TradingDetails": 1304, "StockProfile": 10, "StockData": 1080}
    expected_digests = {
        "Profiles": "a9c59d685756ef8370d9bf7a9460bdbd593c4ffd96ac3061c59e83cb5385ff27",
        "Strategy": "387ee4de16e9535160da835bb505947860e2589d7c551c31d3ae2173d467ed8c",
        "TradingDetails": "35bd353c9de6e5c9aa7603e3c3608f7aed0e634eeecccff03d1139c588169ba5",
        "StockProfile": "3991b7e2ce084c5a5df5a402f2eefe6e33cf58825e5674becbf210e8514683ac",
        "StockData": "80d31d17c0e8fade532194e6e9afb465615b885495f31b398a69b8b9649bb542",
    }
    if guard.get("row_counts") != expected_counts or guard.get("table_digests_sha256") != expected_digests:
        raise CanonicalEpisodeContractError("formal initial N30 semantic fixture guard drifted")

    activation = plan.get("activation", {})
    if activation.get("seed") != ACTIVATION_SEED or activation.get("state_carry_forward") is not True:
        raise CanonicalEpisodeContractError("formal activation identity/state-carry contract drifted")

    world = plan.get("world", {})
    expected_world = {
        "initialization_date": "2023-06-15",
        "participant_visible_start_date": "2023-06-19",
        "end_date": "2023-07-11",
        "formal_world_ticks": 27,
        "open_days": 17,
        "closed_days": 10,
    }
    if {key: world.get(key) for key in expected_world} != expected_world:
        raise CanonicalEpisodeContractError("formal 27-tick world horizon drifted")

    generation = plan.get("generation_policy", {})
    required_true = (
        "single_valid_canonical_episode",
        "generated_before_participant_exposure",
        "shared_across_participants",
        "technical_invalid_attempt_may_restart_from_frozen_initial_state",
        "failed_attempt_evidence_must_be_retained",
        "code_or_contract_change_requires_new_plan_version",
    )
    if any(generation.get(key) is not True for key in required_true):
        raise CanonicalEpisodeContractError("canonical generation policy lost a required invariant")
    forbidden_true = (
        "partial_resume_allowed",
        "seed_substitution_allowed",
        "outcome_based_rerun_allowed",
    )
    if any(generation.get(key) is not False for key in forbidden_true):
        raise CanonicalEpisodeContractError("canonical generation policy permits a forbidden rerun path")

    acceptance = plan.get("acceptance_policy", {})
    required_acceptance_true = (
        "all_27_calendar_ticks_complete",
        "all_active_agent_pipelines_complete",
        "activation_plan_must_match_exactly",
        "authoritative_open_closed_actions_must_match",
        "state_chain_must_be_continuous",
        "protected_inputs_must_remain_unchanged",
        "participant_data_must_be_absent",
        "controlled_stimulus_must_be_absent_from_agent_world",
        "participant_exact_price_coverage_must_be_complete",
        "forum_profile_source_cue_join_must_be_complete",
    )
    if any(acceptance.get(key) is not True for key in required_acceptance_true):
        raise CanonicalEpisodeContractError("canonical technical acceptance gate drifted")
    if acceptance.get("custom_matching_price_forum_belief_logic_allowed") is not False:
        raise CanonicalEpisodeContractError("custom inherited-world logic must remain forbidden")
    for key in (
        "minimum_post_count_gate",
        "minimum_trade_count_gate",
        "price_direction_gate",
        "sentiment_gate",
        "misinformation_effect_gate",
    ):
        if acceptance.get(key) is not None:
            raise CanonicalEpisodeContractError(f"outcome-conditioned formal gate is forbidden: {key}")

    layout = plan.get("formal_asset_layout", {})
    if layout.get("agent_world_db") != FORMAL_AGENT_WORLD_DB:
        raise CanonicalEpisodeContractError("formal Agent-world DB path drifted")
    if layout.get("forum_db") != FORMAL_FORUM_DB:
        raise CanonicalEpisodeContractError("formal ForumDB path drifted")
    if layout.get("episode_manifest") != FORMAL_EPISODE_MANIFEST:
        raise CanonicalEpisodeContractError("formal episode manifest path drifted")

    days = plan.get("days")
    if not isinstance(days, list) or len(days) != EXPECTED_WORLD_TICKS:
        raise CanonicalEpisodeContractError("canonical plan must contain exactly 27 calendar days")
    active_total = 0
    previous_date = None
    for expected_step, row in enumerate(days):
        if row.get("step") != expected_step:
            raise CanonicalEpisodeContractError("canonical day step sequence drifted")
        current_date = str(row.get("agent_world_date"))
        if previous_date is not None:
            from datetime import date, timedelta
            if date.fromisoformat(current_date) != date.fromisoformat(previous_date) + timedelta(days=1):
                raise CanonicalEpisodeContractError("canonical world dates are not contiguous calendar days")
        previous_date = current_date
        ids = row.get("active_agent_ids")
        if not isinstance(ids, list) or len(ids) != len(set(map(str, ids))):
            raise CanonicalEpisodeContractError("canonical active-Agent list is invalid")
        if row.get("n_active") != len(ids):
            raise CanonicalEpisodeContractError("canonical active-Agent count disagrees with IDs")
        expected_action = "advance_trading_day" if row.get("market_open") else "advance_non_trading_day"
        if row.get("expected_market_action") != expected_action:
            raise CanonicalEpisodeContractError("canonical market action disagrees with authoritative OPEN/CLOSED state")
        active_total += len(ids)
    if days[0].get("agent_world_date") != "2023-06-15" or days[-1].get("agent_world_date") != "2023-07-11":
        raise CanonicalEpisodeContractError("canonical plan endpoints drifted")
    if active_total != EXPECTED_AGENT_PIPELINE_EXECUTIONS:
        raise CanonicalEpisodeContractError(
            f"canonical plan expected {EXPECTED_AGENT_PIPELINE_EXECUTIONS} Agent pipeline executions, got {active_total}"
        )


def _trading_days(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        if rows.fieldnames is None or "pretrade_date" not in rows.fieldnames:
            raise CanonicalEpisodeContractError("trading calendar is missing pretrade_date")
        return {str(row["pretrade_date"])[:10] for row in rows if row.get("pretrade_date")}


def rebuild_execution_plan(repo_root: str | Path) -> dict[str, Any]:
    """Rebuild the predeclared 27-day plan from already-frozen Phase 3/4/10 inputs."""
    from marketlens.agents.activation.policy import ActivationPolicy
    from marketlens.agents.activation.profiles import load_activation_profiles
    from marketlens.agents.population.fixture import build_population_bundle
    from marketlens.experiment.protocol import load_protocol
    from marketlens.market.multiday import build_calendar_day_plan, sample_activation_sequence

    root = Path(repo_root).resolve()
    protocol = load_protocol(root / "marketlens/experiment/protocol_v1.json")
    if protocol["protocol_version"] != PROTOCOL_VERSION:
        raise CanonicalEpisodeContractError("Phase 10 formal protocol version drifted")

    with tempfile.TemporaryDirectory(prefix="marketlens_phase13c_plan_") as temp:
        output = Path(temp) / "n30"
        manifest = build_population_bundle(
            source_db=root / "data/sys_1000.db",
            population_size=POPULATION_SIZE,
            seed=POPULATION_SEED,
            output_dir=output,
        )
        if manifest["selection"]["selected_agent_ids_sha256"] != SELECTED_AGENT_IDS_SHA256:
            raise CanonicalEpisodeContractError("rebuilt N30 membership drifted")
        frozen_guard = load_execution_plan()["population"]["initial_fixture_semantic_guard"]
        if manifest["runtime_fixture"]["row_counts"] != frozen_guard["row_counts"]:
            raise CanonicalEpisodeContractError("rebuilt N30 row counts drifted")
        if manifest["runtime_fixture"]["table_digests_sha256"] != frozen_guard["table_digests_sha256"]:
            raise CanonicalEpisodeContractError("rebuilt N30 semantic table digests drifted")
        profiles = load_activation_profiles(output / "population_runtime.db")
        plan = build_calendar_day_plan(
            start_date=protocol["world"]["initialization_date"],
            end_date=protocol["world"]["end_date"],
            trading_days=_trading_days(root / "data/trading_days.csv"),
        )
        sequence = sample_activation_sequence(
            profiles,
            plan=plan,
            seed=ACTIVATION_SEED,
            policy=ActivationPolicy(),
        )

        frozen = load_execution_plan()
        rebuilt = json.loads(json.dumps(frozen))
        rebuilt["days"] = [
            {
                "step": item.day.step,
                "agent_world_date": item.day.current_date,
                "market_open": item.day.market_open,
                "expected_market_action": item.day.expected_market_action,
                "active_agent_ids": list(map(str, item.batch.active_agent_ids)),
                "n_active": len(item.batch.active_agent_ids),
            }
            for item in sequence
        ]
        rebuilt["population"]["selected_agent_ids_sha256"] = manifest["selection"]["selected_agent_ids_sha256"]
        validate_execution_plan(rebuilt)
        return rebuilt


def validate_formal_episode_manifest(
    manifest: Mapping[str, Any], *, repo_root: str | Path, verify_files: bool = True
) -> None:
    """Validate the minimum final manifest a future paid producer must freeze.

    This validation is intentionally outcome-blind: it verifies execution integrity,
    not post/trade counts, market direction, sentiment, or participant effects.
    """
    root = Path(repo_root).resolve()
    if manifest.get("manifest_schema_version") != "marketlens-canonical-episode-manifest/1.0":
        raise CanonicalEpisodeContractError("canonical episode manifest schema drifted")
    if manifest.get("episode_id") != EPISODE_ID or manifest.get("status") != "formal_frozen":
        raise CanonicalEpisodeContractError("formal episode identity/status invalid")
    if manifest.get("protocol_version") != PROTOCOL_VERSION:
        raise CanonicalEpisodeContractError("formal episode protocol version drifted")
    if manifest.get("execution_plan_sha256") != execution_plan_sha256(load_execution_plan()):
        raise CanonicalEpisodeContractError("formal episode execution-plan hash mismatch")

    population = manifest.get("population", {})
    if population.get("size") != POPULATION_SIZE or population.get("selection_seed") != POPULATION_SEED:
        raise CanonicalEpisodeContractError("formal episode population identity drifted")
    if population.get("selected_agent_ids_sha256") != SELECTED_AGENT_IDS_SHA256:
        raise CanonicalEpisodeContractError("formal episode N30 membership drifted")
    if manifest.get("activation", {}).get("seed") != ACTIVATION_SEED:
        raise CanonicalEpisodeContractError("formal episode activation seed drifted")

    world = manifest.get("world", {})
    if world.get("initialization_date") != "2023-06-15" or world.get("end_date") != "2023-07-11":
        raise CanonicalEpisodeContractError("formal episode horizon drifted")
    if world.get("formal_world_ticks") != EXPECTED_WORLD_TICKS:
        raise CanonicalEpisodeContractError("formal episode did not complete 27 ticks")

    attempt = manifest.get("attempt", {})
    if attempt.get("seed_substitution_used") is not False:
        raise CanonicalEpisodeContractError("formal episode used seed substitution")
    if attempt.get("partial_resume_used") is not False:
        raise CanonicalEpisodeContractError("formal episode used forbidden partial resume")
    if attempt.get("outcome_review_used_for_acceptance") is not False:
        raise CanonicalEpisodeContractError("formal episode acceptance was outcome-conditioned")

    execution = manifest.get("execution", {})
    if execution.get("active_agent_pipeline_executions_expected") != EXPECTED_AGENT_PIPELINE_EXECUTIONS:
        raise CanonicalEpisodeContractError("formal episode expected pipeline count drifted")
    if execution.get("active_agent_pipeline_executions_completed") != EXPECTED_AGENT_PIPELINE_EXECUTIONS:
        raise CanonicalEpisodeContractError("not all predeclared Agent pipelines completed")
    if execution.get("failed_agent_pipeline_count") != 0:
        raise CanonicalEpisodeContractError("formal episode contains Agent pipeline failures")
    if execution.get("participant_data_used") is not False:
        raise CanonicalEpisodeContractError("participant data entered canonical Agent world")
    if execution.get("controlled_stimulus_injected_into_agent_world") is not False:
        raise CanonicalEpisodeContractError("controlled stimulus entered canonical Agent world")
    if execution.get("custom_matching_price_forum_belief_logic_used") is not False:
        raise CanonicalEpisodeContractError("custom inherited-world logic entered canonical episode")

    validation = manifest.get("validation", {})
    required_true = (
        "all_days_complete",
        "activation_plan_exact",
        "calendar_actions_exact",
        "state_chain_complete",
        "protected_sources_unchanged",
        "participant_price_coverage_complete",
        "forum_profile_source_cue_join_complete",
    )
    if any(validation.get(key) is not True for key in required_true):
        raise CanonicalEpisodeContractError("formal episode failed a predeclared technical validation gate")

    daily = manifest.get("daily_state_chain")
    plan = load_execution_plan()
    if not isinstance(daily, list) or len(daily) != EXPECTED_WORLD_TICKS:
        raise CanonicalEpisodeContractError("formal episode daily state chain must have 27 entries")
    for expected, actual in zip(plan["days"], daily, strict=True):
        if actual.get("step") != expected["step"] or actual.get("agent_world_date") != expected["agent_world_date"]:
            raise CanonicalEpisodeContractError("formal episode daily state chain date/step drifted")
        for key in ("agent_world_db_sha256", "forum_db_sha256"):
            if not isinstance(actual.get(key), str) or not _HEX64.fullmatch(actual[key]):
                raise CanonicalEpisodeContractError(f"invalid daily state hash: {key}")

    outputs = manifest.get("outputs", {})
    expected_paths = {
        "agent_world_db": FORMAL_AGENT_WORLD_DB,
        "forum_db": FORMAL_FORUM_DB,
    }
    for key, relative in expected_paths.items():
        record = outputs.get(key, {})
        if record.get("path") != relative:
            raise CanonicalEpisodeContractError(f"formal output path drifted: {key}")
        expected_sha = record.get("sha256")
        if not isinstance(expected_sha, str) or not _HEX64.fullmatch(expected_sha):
            raise CanonicalEpisodeContractError(f"formal output hash missing/invalid: {key}")
        if verify_files:
            target = (root / relative).resolve()
            if not target.is_file():
                raise CanonicalEpisodeContractError(f"formal output file not found: {target}")
            if file_sha256(target) != expected_sha:
                raise CanonicalEpisodeContractError(f"formal output SHA-256 mismatch: {key}")


def formal_assets_present(repo_root: str | Path) -> bool:
    root = Path(repo_root).resolve()
    return all((root / rel).is_file() for rel in (FORMAL_AGENT_WORLD_DB, FORMAL_FORUM_DB, FORMAL_EPISODE_MANIFEST))
