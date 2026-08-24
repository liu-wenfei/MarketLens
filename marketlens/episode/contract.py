"""Phase 13C canonical Agent-world episode-pool freeze contract.

This module does not execute an LLM or generate formal worlds. It freezes and
validates the zero-LLM execution plan shared by a fixed pool of pre-generated
canonical episodes and the minimum manifests that a later formal producer must
satisfy.
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
    """Raised when the predeclared canonical-episode-pool identity drifts."""


EPISODE_POOL_ID = "marketlens-canonical-episode-pool-v1"
EPISODE_IDS = (
    "marketlens-canonical-episode-v1-e01",
    "marketlens-canonical-episode-v1-e02",
    "marketlens-canonical-episode-v1-e03",
)
EPISODE_COUNT = 3
PLAN_VERSION = "1.2"
PLAN_STATUS = "formal_episode_pool_execution_plan_frozen"
PROTOCOL_VERSION = "1.1"
POPULATION_SIZE = 30
POPULATION_SEED = "marketlens-dev-population-01"
SELECTED_AGENT_IDS_SHA256 = (
    "60d846b21c15e2213f6f897a17a7ea98039fbf461abe54ee89e1b6779d24b2d4"
)
ACTIVATION_SEED = "marketlens-phase09b-activation-01"
EXPECTED_WORLD_TICKS = 27
EXPECTED_AGENT_PIPELINE_EXECUTIONS = 193
EXPECTED_POOL_AGENT_PIPELINE_EXECUTIONS = EXPECTED_AGENT_PIPELINE_EXECUTIONS * EPISODE_COUNT
EXPECTED_EXECUTION_PLAN_SHA256 = "a907079281f7deca590bd7ec741b56fab614f05b0cdd869c5f2c345fb048a8bc"
FORMAL_POOL_ROOT = "data/marketlens/canonical_episode/v1"
FORMAL_POOL_MANIFEST = f"{FORMAL_POOL_ROOT}/pool_manifest.json"

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


def episode_index(episode_id: str) -> int:
    try:
        return EPISODE_IDS.index(str(episode_id)) + 1
    except ValueError as exc:
        raise CanonicalEpisodeContractError(f"unknown canonical episode id: {episode_id}") from exc


def formal_episode_paths(episode_id: str) -> dict[str, str]:
    index = episode_index(episode_id)
    root = f"{FORMAL_POOL_ROOT}/episode_{index:02d}"
    return {
        "root": root,
        "agent_world_db": f"{root}/agent_world.db",
        "forum_db": f"{root}/forum.db",
        "episode_manifest": f"{root}/episode_manifest.json",
        "raw_execution_evidence_root": f"artifacts/formal/canonical_episode/{episode_id}",
    }


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
    if plan.get("plan_schema_version") != "marketlens-canonical-episode-pool-execution-plan/1.0":
        raise CanonicalEpisodeContractError("canonical plan schema version drifted")
    if plan.get("plan_version") != PLAN_VERSION or plan.get("status") != PLAN_STATUS:
        raise CanonicalEpisodeContractError("canonical plan version/status drifted")
    if plan.get("protocol_version") != PROTOCOL_VERSION:
        raise CanonicalEpisodeContractError("canonical protocol identity drifted")

    compatibility = plan.get("base_protocol_compatibility", {})
    if compatibility.get("base_protocol_version") != PROTOCOL_VERSION:
        raise CanonicalEpisodeContractError("base protocol compatibility version drifted")
    if compatibility.get("base_protocol_role") != "timing_population_participant_trade_and_stimulus_base":
        raise CanonicalEpisodeContractError("base protocol compatibility role drifted")
    if compatibility.get("extension_status") != "phase13c_episode_pool_supersedes_base_canonical_world_cardinality_only":
        raise CanonicalEpisodeContractError("Phase 13C protocol extension status drifted")
    if compatibility.get("superseded_base_canonical_world_fields") != [
        "generated_once",
        "shared_across_participants",
    ]:
        raise CanonicalEpisodeContractError("Phase 13C superseded base fields drifted")
    effective = compatibility.get("effective_canonical_world_policy", {})
    expected_effective = {
        "predeclared_episode_pool_size": EPISODE_COUNT,
        "each_episode_slot_generated_once_if_technically_valid": True,
        "all_episode_slots_generated_before_participant_exposure": True,
        "each_frozen_episode_shared_across_multiple_assigned_participants": True,
        "participant_assignment_mode": "balanced_random_across_episode_pool",
        "episode_id_recorded_for_analysis": True,
        "participant_specific_world_generation": False,
    }
    if effective != expected_effective:
        raise CanonicalEpisodeContractError("effective Phase 13C canonical-world policy drifted")
    retained = compatibility.get("retained_base_canonical_world_invariants", {})
    expected_retained = {
        "generated_before_participant_exposure": True,
        "immutable_during_formal_collection": True,
        "participant_observes_completed_state": True,
        "snapshot_is_storage_not_market_generator": True,
    }
    if retained != expected_retained:
        raise CanonicalEpisodeContractError("retained base canonical-world invariants drifted")

    pool = plan.get("episode_pool", {})
    if pool.get("pool_id") != EPISODE_POOL_ID:
        raise CanonicalEpisodeContractError("canonical episode-pool identity drifted")
    if pool.get("episode_count") != EPISODE_COUNT or tuple(pool.get("episode_ids", ())) != EPISODE_IDS:
        raise CanonicalEpisodeContractError("canonical episode-pool membership drifted")

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
    if generation.get("fixed_episode_pool_size") != EPISODE_COUNT:
        raise CanonicalEpisodeContractError("formal episode-pool size drifted")
    required_true = (
        "all_episode_slots_generated_before_participant_exposure",
        "same_population_across_episodes",
        "same_activation_plan_across_episodes",
        "same_protocol_across_episodes",
        "balanced_random_assignment_across_episode_pool",
        "episode_id_must_be_recorded_for_analysis",
        "technical_invalid_attempt_may_restart_same_episode_slot_from_frozen_initial_state",
        "failed_attempt_evidence_must_be_retained",
        "technically_valid_completed_episode_must_be_retained",
        "code_or_contract_change_requires_new_plan_version",
    )
    if any(generation.get(key) is not True for key in required_true):
        raise CanonicalEpisodeContractError("canonical generation policy lost a required invariant")
    required_false = (
        "participant_specific_world_generation",
        "partial_resume_allowed",
        "seed_substitution_allowed",
        "outcome_based_rerun_allowed",
        "outcome_based_episode_exclusion_allowed",
        "episode_similarity_based_rerun_allowed",
    )
    if any(generation.get(key) is not False for key in required_false):
        raise CanonicalEpisodeContractError("canonical generation policy permits a forbidden selection/rerun path")

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
        "minimum_cross_episode_divergence_gate",
        "episode_similarity_gate",
    ):
        if acceptance.get(key) is not None:
            raise CanonicalEpisodeContractError(f"outcome-conditioned formal gate is forbidden: {key}")

    layout = plan.get("formal_asset_layout", {})
    expected_layout = {
        "pool_manifest": FORMAL_POOL_MANIFEST,
        "episode_root_template": f"{FORMAL_POOL_ROOT}/episode_{{index:02d}}",
        "agent_world_db_name": "agent_world.db",
        "forum_db_name": "forum.db",
        "episode_manifest_name": "episode_manifest.json",
        "raw_execution_evidence_root_template": "artifacts/formal/canonical_episode/{episode_id}",
    }
    if layout != expected_layout:
        raise CanonicalEpisodeContractError("formal episode-pool asset layout drifted")

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
            f"canonical plan expected {EXPECTED_AGENT_PIPELINE_EXECUTIONS} Agent pipeline executions per episode, got {active_total}"
        )


def _trading_days(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        if rows.fieldnames is None or "pretrade_date" not in rows.fieldnames:
            raise CanonicalEpisodeContractError("trading calendar is missing pretrade_date")
        return {str(row["pretrade_date"])[:10] for row in rows if row.get("pretrade_date")}


def validate_base_protocol_compatibility(
    protocol: Mapping[str, Any], plan: Mapping[str, Any]
) -> None:
    """Validate the narrow Phase 13C override without mutating Phase 10 v1.1.

    Phase 10 v1.1 remains the frozen base for timing, N30 selection, participant
    trading, and stimulus timing. Phase 13C supersedes only the original single-
    world cardinality/sharing semantics. This explicit overlay avoids silently
    rewriting the already-frozen Phase 10 / Phase 11 assets.
    """
    if protocol.get("protocol_version") != PROTOCOL_VERSION:
        raise CanonicalEpisodeContractError("Phase 10 base protocol version drifted")
    canonical = protocol.get("canonical_world", {})
    expected_base = {
        "generated_once": True,
        "generated_before_participant_exposure": True,
        "shared_across_participants": True,
        "immutable_during_formal_collection": True,
        "participant_observes_completed_state": True,
        "snapshot_is_storage_not_market_generator": True,
    }
    if canonical != expected_base:
        raise CanonicalEpisodeContractError(
            "Phase 10 v1.1 canonical_world base block drifted; Phase 13C only permits an explicit overlay"
        )
    compatibility = plan.get("base_protocol_compatibility", {})
    if compatibility.get("superseded_base_canonical_world_fields") != [
        "generated_once",
        "shared_across_participants",
    ]:
        raise CanonicalEpisodeContractError(
            "Phase 13C must supersede exactly the two single-world cardinality/sharing fields"
        )
    unchanged = set(compatibility.get("unchanged_base_protocol_domains", ()))
    required = {
        "world_timing",
        "participant_decision_dates",
        "judgement_timing",
        "participant_price_taker_trading",
        "participant_only_misinformation_and_correction",
        "warm_up",
        "formal_N30_population",
        "authoritative_open_closed_calendar",
    }
    if unchanged != required:
        raise CanonicalEpisodeContractError("Phase 13C unchanged base-protocol domain declaration drifted")


def rebuild_execution_plan(repo_root: str | Path) -> dict[str, Any]:
    """Rebuild the shared 27-day plan from already-frozen Phase 3/4/10 inputs."""
    from marketlens.agents.activation.policy import ActivationPolicy
    from marketlens.agents.activation.profiles import load_activation_profiles
    from marketlens.agents.population.fixture import build_population_bundle
    from marketlens.experiment.protocol import load_protocol
    from marketlens.market.multiday import build_calendar_day_plan, sample_activation_sequence

    root = Path(repo_root).resolve()
    protocol = load_protocol(root / "marketlens/experiment/protocol_v1.json")
    if protocol["protocol_version"] != PROTOCOL_VERSION:
        raise CanonicalEpisodeContractError("Phase 10 formal protocol version drifted")
    validate_base_protocol_compatibility(protocol, load_execution_plan())

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
    """Validate one formal episode slot without conditioning on natural outcomes."""
    root = Path(repo_root).resolve()
    if manifest.get("manifest_schema_version") != "marketlens-canonical-episode-manifest/1.1":
        raise CanonicalEpisodeContractError("canonical episode manifest schema drifted")
    episode_id = str(manifest.get("episode_id", ""))
    if episode_id not in EPISODE_IDS or manifest.get("status") != "formal_frozen":
        raise CanonicalEpisodeContractError("formal episode identity/status invalid")
    if manifest.get("episode_pool_id") != EPISODE_POOL_ID:
        raise CanonicalEpisodeContractError("formal episode pool identity drifted")
    if manifest.get("episode_slot") != episode_index(episode_id):
        raise CanonicalEpisodeContractError("formal episode slot identity drifted")
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
    if attempt.get("episode_similarity_review_used_for_acceptance") is not False:
        raise CanonicalEpisodeContractError("formal episode acceptance was similarity-conditioned")

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
    paths = formal_episode_paths(episode_id)
    expected_paths = {
        "agent_world_db": paths["agent_world_db"],
        "forum_db": paths["forum_db"],
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


def validate_formal_episode_pool_manifest(
    manifest: Mapping[str, Any], *, repo_root: str | Path, verify_files: bool = True
) -> None:
    """Validate the frozen three-episode pool and its participant assignment contract."""
    root = Path(repo_root).resolve()
    if manifest.get("manifest_schema_version") != "marketlens-canonical-episode-pool-manifest/1.0":
        raise CanonicalEpisodeContractError("canonical episode-pool manifest schema drifted")
    if manifest.get("episode_pool_id") != EPISODE_POOL_ID or manifest.get("status") != "formal_frozen":
        raise CanonicalEpisodeContractError("formal episode-pool identity/status invalid")
    if manifest.get("execution_plan_sha256") != execution_plan_sha256(load_execution_plan()):
        raise CanonicalEpisodeContractError("formal episode-pool execution-plan hash mismatch")
    if manifest.get("episode_count") != EPISODE_COUNT or tuple(manifest.get("episode_ids", ())) != EPISODE_IDS:
        raise CanonicalEpisodeContractError("formal episode-pool membership invalid")
    assignment = manifest.get("participant_assignment", {})
    if assignment.get("mode") != "balanced_random_across_episode_pool":
        raise CanonicalEpisodeContractError("formal participant episode assignment policy drifted")
    if assignment.get("episode_id_recorded_for_analysis") is not True:
        raise CanonicalEpisodeContractError("participant records must retain episode_id")
    if assignment.get("assignment_uses_episode_outcomes") is not False:
        raise CanonicalEpisodeContractError("participant episode assignment must be outcome-blind")

    records = manifest.get("episodes")
    if not isinstance(records, list) or [row.get("episode_id") for row in records] != list(EPISODE_IDS):
        raise CanonicalEpisodeContractError("formal episode-pool records drifted")
    for row in records:
        episode_id = row["episode_id"]
        expected_manifest = formal_episode_paths(episode_id)["episode_manifest"]
        if row.get("episode_manifest_path") != expected_manifest:
            raise CanonicalEpisodeContractError("formal per-episode manifest path drifted")
        if verify_files:
            target = root / expected_manifest
            if not target.is_file():
                raise CanonicalEpisodeContractError(f"formal episode manifest not found: {target}")
            payload = json.loads(target.read_text(encoding="utf-8"))
            validate_formal_episode_manifest(payload, repo_root=root, verify_files=True)


def formal_assets_present(repo_root: str | Path) -> bool:
    root = Path(repo_root).resolve()
    required = [FORMAL_POOL_MANIFEST]
    for episode_id in EPISODE_IDS:
        paths = formal_episode_paths(episode_id)
        required.extend((paths["agent_world_db"], paths["forum_db"], paths["episode_manifest"]))
    return all((root / rel).is_file() for rel in required)
