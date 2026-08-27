"""MarketLens canonical episode pool v2 contract.

v2 preserves the frozen v1 timing/population/activation/world contract and
changes only the formal namespace, final Agent forum ``post`` language, and versioned formal runtime-reliability controls.
The v1 contract and evidence remain untouched and independently validatable.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping

from marketlens.episode import contract as v1
from marketlens.stimulus.manifest import sha256_json


class CanonicalEpisodeV2ContractError(ValueError):
    """Raised when the predeclared v2 episode contract drifts."""


EPISODE_POOL_ID = "marketlens-canonical-episode-pool-v2"
EPISODE_IDS = (
    "marketlens-canonical-episode-v2-e01",
    "marketlens-canonical-episode-v2-e02",
    "marketlens-canonical-episode-v2-e03",
)
EPISODE_COUNT = 3
PLAN_VERSION = "2.3"
PLAN_STATUS = "formal_episode_pool_v2_execution_plan_frozen"
PROTOCOL_VERSION = v1.PROTOCOL_VERSION
POPULATION_SIZE = v1.POPULATION_SIZE
POPULATION_SEED = v1.POPULATION_SEED
SELECTED_AGENT_IDS_SHA256 = v1.SELECTED_AGENT_IDS_SHA256
ACTIVATION_SEED = v1.ACTIVATION_SEED
EXPECTED_WORLD_TICKS = v1.EXPECTED_WORLD_TICKS
EXPECTED_AGENT_PIPELINE_EXECUTIONS = v1.EXPECTED_AGENT_PIPELINE_EXECUTIONS
EXPECTED_POOL_AGENT_PIPELINE_EXECUTIONS = EXPECTED_AGENT_PIPELINE_EXECUTIONS * EPISODE_COUNT
EXPECTED_V1_EXECUTION_PLAN_SHA256 = v1.EXPECTED_EXECUTION_PLAN_SHA256
EXPECTED_EXECUTION_PLAN_SHA256 = "14baf4ea091c27288bc18a627d9d02642099ad59c1c66f4506a458bdb270957c"
EXPECTED_PRODUCER_CONTRACT_SHA256 = "43adf89370e9aa6d3e0d4ff736856ef887e6efe8170b024ee3300648904a30a3"
FORMAL_POOL_ROOT = "data/marketlens/canonical_episode/v2"
FORMAL_POOL_MANIFEST = f"{FORMAL_POOL_ROOT}/pool_manifest.json"
RAW_EVIDENCE_ROOT_TEMPLATE = "artifacts/formal/canonical_episode_v2/{episode_id}"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def default_plan_path() -> Path:
    return Path(__file__).with_name("execution_plan_v2.json")


def file_sha256(path: str | Path) -> str:
    return v1.file_sha256(path)


def execution_plan_sha256(plan: Mapping[str, Any]) -> str:
    return sha256_json(dict(plan))


def episode_index(episode_id: str) -> int:
    try:
        return EPISODE_IDS.index(str(episode_id)) + 1
    except ValueError as exc:
        raise CanonicalEpisodeV2ContractError(
            f"unknown canonical v2 episode id: {episode_id}"
        ) from exc


def formal_episode_paths(episode_id: str) -> dict[str, str]:
    index = episode_index(episode_id)
    root = f"{FORMAL_POOL_ROOT}/episode_{index:02d}"
    return {
        "root": root,
        "agent_world_db": f"{root}/agent_world.db",
        "forum_db": f"{root}/forum.db",
        "episode_manifest": f"{root}/episode_manifest.json",
        "raw_execution_evidence_root": RAW_EVIDENCE_ROOT_TEMPLATE.format(
            episode_id=episode_id
        ),
    }


def _expected_plan_from_v1() -> dict[str, Any]:
    base = copy.deepcopy(v1.load_execution_plan())
    base["plan_schema_version"] = "marketlens-canonical-episode-pool-execution-plan/2.0"
    base["plan_version"] = PLAN_VERSION
    base["status"] = PLAN_STATUS
    base["runtime_reliability_policy"] = {
        "scope": "backend_retry_timing_and_attempt_interruption_capture_only",
        "outer_tenacity_retry_wait_seconds": 1,
        "outer_tenacity_stop_after_attempt": 10,
        "openai_client_internal_retry_changed": False,
        "http_timeout_override_added": False,
        "keyboard_interrupt_attempt_status": "INTERRUPTED",
        "keyboard_interrupt_exit_code": 130,
        "interrupted_workspace_preserved": True,
        "partial_resume_after_interrupt_allowed": False,
        "restart_after_interrupt": "new attempt from frozen initial N30 state only",
        "historical_attempt_manifest_rewrite_allowed": False,
        "agent_reasoning_semantics_changed": False,
    }
    base["v2_forum_output"] = {
        "intervention_scope": "final_agent_forum_post_field_only",
        "participant_visible_agent_forum_language": "English",
        "post_generated_directly_in_english": True,
        "live_translation_used": False,
        "inherited_natural_news_language_changed": False,
        "agent_reasoning_pipeline_rewritten": False,
        "belief_language_policy": "preserve_inherited_chinese_output",
        "deterministic_language_gate": {
            "zero_llm": True,
            "all_stored_posts_checked": True,
            "cjk_characters_allowed_in_post": False,
            "latin_letter_required": True,
            "content_quality_or_sentiment_gate": False,
            "type_prefix_allowed_in_post": False,
        },
        "chinese_source_terms_may_be_copied_into_post": False,
        "same_call_self_check_required": True,
        "entity_name_registry": {
            "path": "marketlens/episode/entity_name_registry_v2_1.json",
            "registry_id": "marketlens-entity-name-registry-v2.1",
            "registry_version": "2.1",
            "status": "formal_v2_entity_name_registry_frozen",
            "sha256": "0bdf5dfc9851e21440496dfdf220de512965efeed33f6ee67ef68ec91a65ad5b",
            "simulation_reference_date": "2023-06-15",
            "counts": {"sectors": 10, "indices": 10, "companies": 50, "total_entities": 70},
            "known_entity_policy": "exact_canonical_english_display_or_stable_code",
            "unknown_entity_fallback": "ticker_or_index_code",
            "free_model_translation_or_transliteration": False,
            "post_generation_entity_rewriting": False,
            "glossary_scope": "final_agent_forum_post_prompt_only",
        },
        "post_type_declaration_policy": "yaml_type_field_only",
        "inherited_type_instruction_clarified_in_v2_prompt": True,
    }
    base["acceptance_policy"][
        "participant_visible_agent_forum_posts_must_be_english"
    ] = True
    base["formal_asset_layout"]["pool_manifest"] = FORMAL_POOL_MANIFEST
    base["formal_asset_layout"][
        "episode_root_template"
    ] = f"{FORMAL_POOL_ROOT}/episode_{{index:02d}}"
    base["formal_asset_layout"][
        "raw_execution_evidence_root_template"
    ] = RAW_EVIDENCE_ROOT_TEMPLATE
    base["episode_pool"]["pool_id"] = EPISODE_POOL_ID
    base["episode_pool"]["episode_ids"] = list(EPISODE_IDS)
    base["episode_pool"][
        "replication_rule"
    ] = (
        "same frozen initial N30 world + same activation plan; independent "
        "stochastic TwinMarket/LLM execution per episode; final Agent forum "
        "post field generated directly in English"
    )
    return base


def validate_execution_plan(plan: Mapping[str, Any]) -> None:
    if v1.execution_plan_sha256(v1.load_execution_plan()) != EXPECTED_V1_EXECUTION_PLAN_SHA256:
        raise CanonicalEpisodeV2ContractError("frozen v1 execution plan drifted")
    if execution_plan_sha256(plan) != EXPECTED_EXECUTION_PLAN_SHA256:
        raise CanonicalEpisodeV2ContractError("canonical v2 execution-plan SHA-256 drifted")
    expected = _expected_plan_from_v1()
    if dict(plan) != expected:
        raise CanonicalEpisodeV2ContractError(
            "v2 execution plan changed outside the predeclared forum/runtime overlays"
        )


def load_execution_plan(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path is not None else default_plan_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalEpisodeV2ContractError(
            f"cannot load canonical v2 execution plan: {source}"
        ) from exc
    if not isinstance(payload, dict):
        raise CanonicalEpisodeV2ContractError("canonical v2 execution plan root must be an object")
    validate_execution_plan(payload)
    return payload


def validate_formal_episode_manifest(
    manifest: Mapping[str, Any], *, repo_root: str | Path, verify_files: bool = True
) -> None:
    root = Path(repo_root).resolve()
    if manifest.get("manifest_schema_version") != "marketlens-canonical-episode-manifest/2.0":
        raise CanonicalEpisodeV2ContractError("canonical v2 episode manifest schema drifted")
    episode_id = str(manifest.get("episode_id", ""))
    if episode_id not in EPISODE_IDS or manifest.get("status") != "formal_frozen":
        raise CanonicalEpisodeV2ContractError("formal v2 episode identity/status invalid")
    if manifest.get("episode_pool_id") != EPISODE_POOL_ID:
        raise CanonicalEpisodeV2ContractError("formal v2 episode-pool identity drifted")
    if manifest.get("episode_slot") != episode_index(episode_id):
        raise CanonicalEpisodeV2ContractError("formal v2 episode slot identity drifted")
    if manifest.get("protocol_version") != PROTOCOL_VERSION:
        raise CanonicalEpisodeV2ContractError("formal v2 protocol version drifted")
    if manifest.get("execution_plan_sha256") != EXPECTED_EXECUTION_PLAN_SHA256:
        raise CanonicalEpisodeV2ContractError("formal v2 execution-plan hash mismatch")
    if manifest.get("producer_contract_sha256") != EXPECTED_PRODUCER_CONTRACT_SHA256:
        raise CanonicalEpisodeV2ContractError("formal v2 producer-contract hash mismatch")

    population = manifest.get("population", {})
    if population.get("size") != POPULATION_SIZE or population.get("selection_seed") != POPULATION_SEED:
        raise CanonicalEpisodeV2ContractError("formal v2 population identity drifted")
    if population.get("selected_agent_ids_sha256") != SELECTED_AGENT_IDS_SHA256:
        raise CanonicalEpisodeV2ContractError("formal v2 N30 membership drifted")
    if manifest.get("activation", {}).get("seed") != ACTIVATION_SEED:
        raise CanonicalEpisodeV2ContractError("formal v2 activation seed drifted")

    world = manifest.get("world", {})
    if world.get("initialization_date") != "2023-06-15" or world.get("end_date") != "2023-07-11":
        raise CanonicalEpisodeV2ContractError("formal v2 horizon drifted")
    if world.get("formal_world_ticks") != EXPECTED_WORLD_TICKS:
        raise CanonicalEpisodeV2ContractError("formal v2 episode did not complete 27 ticks")

    attempt = manifest.get("attempt", {})
    for key, label in (
        ("seed_substitution_used", "seed substitution"),
        ("partial_resume_used", "partial resume"),
        ("outcome_review_used_for_acceptance", "outcome-conditioned acceptance"),
        ("episode_similarity_review_used_for_acceptance", "similarity-conditioned acceptance"),
    ):
        if attempt.get(key) is not False:
            raise CanonicalEpisodeV2ContractError(f"formal v2 episode used forbidden {label}")

    execution = manifest.get("execution", {})
    if execution.get("active_agent_pipeline_executions_expected") != EXPECTED_AGENT_PIPELINE_EXECUTIONS:
        raise CanonicalEpisodeV2ContractError("formal v2 expected pipeline count drifted")
    if execution.get("active_agent_pipeline_executions_completed") != EXPECTED_AGENT_PIPELINE_EXECUTIONS:
        raise CanonicalEpisodeV2ContractError("not all predeclared v2 Agent pipelines completed")
    if execution.get("failed_agent_pipeline_count") != 0:
        raise CanonicalEpisodeV2ContractError("formal v2 episode contains Agent pipeline failures")
    if execution.get("participant_data_used") is not False:
        raise CanonicalEpisodeV2ContractError("participant data entered canonical v2 Agent world")
    if execution.get("controlled_stimulus_injected_into_agent_world") is not False:
        raise CanonicalEpisodeV2ContractError("controlled stimulus entered canonical v2 Agent world")
    if execution.get("custom_matching_price_forum_belief_logic_used") is not False:
        raise CanonicalEpisodeV2ContractError("custom inherited-world logic entered canonical v2 episode")

    forum_output = manifest.get("forum_output", {})
    expected_output = _expected_plan_from_v1()["v2_forum_output"]
    if forum_output != expected_output:
        raise CanonicalEpisodeV2ContractError("formal v2 forum-output contract drifted")

    validation = manifest.get("validation", {})
    required_true = (
        "all_days_complete",
        "activation_plan_exact",
        "calendar_actions_exact",
        "state_chain_complete",
        "protected_sources_unchanged",
        "participant_price_coverage_complete",
        "forum_profile_source_cue_join_complete",
        "forum_post_language_complete",
    )
    if any(validation.get(key) is not True for key in required_true):
        raise CanonicalEpisodeV2ContractError("formal v2 episode failed a predeclared technical validation gate")

    daily = manifest.get("daily_state_chain")
    plan = load_execution_plan()
    if not isinstance(daily, list) or len(daily) != EXPECTED_WORLD_TICKS:
        raise CanonicalEpisodeV2ContractError("formal v2 daily state chain must have 27 entries")
    for expected, actual in zip(plan["days"], daily, strict=True):
        if actual.get("step") != expected["step"] or actual.get("agent_world_date") != expected["agent_world_date"]:
            raise CanonicalEpisodeV2ContractError("formal v2 daily state chain date/step drifted")
        for key in ("agent_world_db_sha256", "forum_db_sha256"):
            if not isinstance(actual.get(key), str) or not _HEX64.fullmatch(actual[key]):
                raise CanonicalEpisodeV2ContractError(f"invalid v2 daily state hash: {key}")

    outputs = manifest.get("outputs", {})
    paths = formal_episode_paths(episode_id)
    for key in ("agent_world_db", "forum_db"):
        relative = paths[key]
        record = outputs.get(key, {})
        if record.get("path") != relative:
            raise CanonicalEpisodeV2ContractError(f"formal v2 output path drifted: {key}")
        expected_sha = record.get("sha256")
        if not isinstance(expected_sha, str) or not _HEX64.fullmatch(expected_sha):
            raise CanonicalEpisodeV2ContractError(f"formal v2 output hash missing/invalid: {key}")
        if verify_files:
            target = root / relative
            if not target.is_file() or file_sha256(target) != expected_sha:
                raise CanonicalEpisodeV2ContractError(f"formal v2 output SHA-256 mismatch: {key}")


def validate_formal_episode_pool_manifest(
    manifest: Mapping[str, Any], *, repo_root: str | Path, verify_files: bool = True
) -> None:
    root = Path(repo_root).resolve()
    if manifest.get("manifest_schema_version") != "marketlens-canonical-episode-pool-manifest/2.0":
        raise CanonicalEpisodeV2ContractError("canonical v2 pool manifest schema drifted")
    if manifest.get("episode_pool_id") != EPISODE_POOL_ID or manifest.get("status") != "formal_frozen":
        raise CanonicalEpisodeV2ContractError("formal v2 pool identity/status invalid")
    if manifest.get("execution_plan_sha256") != EXPECTED_EXECUTION_PLAN_SHA256:
        raise CanonicalEpisodeV2ContractError("formal v2 pool execution-plan hash mismatch")
    if manifest.get("producer_contract_sha256") != EXPECTED_PRODUCER_CONTRACT_SHA256:
        raise CanonicalEpisodeV2ContractError("formal v2 pool producer-contract hash mismatch")
    if manifest.get("forum_output") != _expected_plan_from_v1()["v2_forum_output"]:
        raise CanonicalEpisodeV2ContractError("formal v2 pool forum-output contract drifted")
    if manifest.get("episode_count") != EPISODE_COUNT or tuple(manifest.get("episode_ids", ())) != EPISODE_IDS:
        raise CanonicalEpisodeV2ContractError("formal v2 pool membership invalid")
    assignment = manifest.get("participant_assignment", {})
    if assignment.get("mode") != "balanced_random_across_episode_pool":
        raise CanonicalEpisodeV2ContractError("formal v2 participant assignment policy drifted")
    if assignment.get("episode_id_recorded_for_analysis") is not True:
        raise CanonicalEpisodeV2ContractError("v2 participant records must retain episode_id")
    if assignment.get("assignment_uses_episode_outcomes") is not False:
        raise CanonicalEpisodeV2ContractError("v2 participant assignment must be outcome-blind")

    records = manifest.get("episodes")
    if not isinstance(records, list) or [row.get("episode_id") for row in records] != list(EPISODE_IDS):
        raise CanonicalEpisodeV2ContractError("formal v2 pool records drifted")
    for row in records:
        episode_id = row["episode_id"]
        expected_manifest = formal_episode_paths(episode_id)["episode_manifest"]
        if row.get("episode_manifest_path") != expected_manifest:
            raise CanonicalEpisodeV2ContractError("formal v2 per-episode manifest path drifted")
        if verify_files:
            target = root / expected_manifest
            if not target.is_file():
                raise CanonicalEpisodeV2ContractError(f"formal v2 episode manifest not found: {target}")
            payload = json.loads(target.read_text(encoding="utf-8"))
            validate_formal_episode_manifest(payload, repo_root=root, verify_files=True)


def formal_assets_present(repo_root: str | Path) -> bool:
    root = Path(repo_root).resolve()
    required = [FORMAL_POOL_MANIFEST]
    for episode_id in EPISODE_IDS:
        paths = formal_episode_paths(episode_id)
        required.extend((paths["agent_world_db"], paths["forum_db"], paths["episode_manifest"]))
    return all((root / rel).is_file() for rel in required)
