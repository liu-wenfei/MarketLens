from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

EPISODE01_RECORD_RELATIVE_PATH = Path(
    "marketlens/episode/freeze_records/marketlens-canonical-episode-v1-e01.json"
)
EXPECTED_EPISODE01_RECORD_SHA256 = (
    "a1a1a8bbd8f0600401a8a11b36b1b6b9e5c5718450253df3028a691aad0623c3"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_episode01_freeze_record(repo_root: Path) -> dict[str, Any]:
    path = repo_root / EPISODE01_RECORD_RELATIVE_PATH
    if not path.is_file():
        raise RuntimeError(f"Missing tracked Episode 01 freeze record: {path}")
    actual_sha = _sha256(path)
    if actual_sha != EXPECTED_EPISODE01_RECORD_SHA256:
        raise RuntimeError(
            "Episode 01 freeze record hash mismatch: "
            f"expected {EXPECTED_EPISODE01_RECORD_SHA256}, got {actual_sha}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def validate_record_semantics(record: dict[str, Any]) -> None:
    if record.get("record_schema_version") != "marketlens-canonical-episode-freeze-record/1.0":
        raise RuntimeError("Unexpected Episode 01 freeze-record schema version")
    if record.get("record_status") != "tracked_formal_freeze_record":
        raise RuntimeError("Episode 01 tracked record is not frozen")
    if record.get("episode_pool_id") != "marketlens-canonical-episode-pool-v1":
        raise RuntimeError("Episode 01 pool identity mismatch")
    if record.get("episode_id") != "marketlens-canonical-episode-v1-e01":
        raise RuntimeError("Episode 01 identity mismatch")
    if record.get("episode_slot") != 1:
        raise RuntimeError("Episode 01 slot mismatch")

    acceptance = record["acceptance"]
    required_acceptance = {
        "status": "formal_frozen_technically_valid",
        "accepted_attempt_number": 1,
        "acceptance_basis": "predeclared_technical_gates_only",
        "outcome_conditioned_acceptance": False,
        "episode_similarity_review_used_for_acceptance": False,
        "seed_substitution_used": False,
        "partial_resume_used": False,
    }
    for key, expected in required_acceptance.items():
        if acceptance.get(key) != expected:
            raise RuntimeError(f"Episode 01 acceptance invariant failed: {key}")

    producer = record["producer_identity"]
    required_producer = {
        "git_commit": "96c2a0b33587293b76eee9ba01978ef75d902abb",
        "git_branch": "dissertation",
        "phase13c_execution_plan_sha256": "a907079281f7deca590bd7ec741b56fab614f05b0cdd869c5f2c345fb048a8bc",
        "phase13d_producer_contract_sha256": "14db0ae7a525ef464975f7ba4da69d98eb8ffd4058d491555a32ee25f92a9126",
        "backend_model_name": "gpt-5.4-mini",
        "backend_base_url": "https://zhi-api.com/v1",
        "api_key_recorded": False,
    }
    for key, expected in required_producer.items():
        if producer.get(key) != expected:
            raise RuntimeError(f"Episode 01 producer invariant failed: {key}")

    population = record["population"]
    if population.get("size") != 30:
        raise RuntimeError("Episode 01 population size mismatch")
    if population.get("selected_agent_ids_sha256") != (
        "60d846b21c15e2213f6f897a17a7ea98039fbf461abe54ee89e1b6779d24b2d4"
    ):
        raise RuntimeError("Episode 01 N30 identity mismatch")

    execution = record["execution"]
    expected_execution = {
        "initialization_date": "2023-06-15",
        "end_date": "2023-07-11",
        "formal_world_ticks": 27,
        "active_agent_pipeline_executions_expected": 193,
        "active_agent_pipeline_executions_completed": 193,
        "failed_agent_pipeline_count": 0,
        "participant_data_used": False,
        "controlled_stimulus_injected_into_agent_world": False,
        "custom_matching_price_forum_belief_logic_used": False,
    }
    for key, expected in expected_execution.items():
        if execution.get(key) != expected:
            raise RuntimeError(f"Episode 01 execution invariant failed: {key}")

    validation = record["technical_validation"]
    for key in (
        "all_days_complete",
        "activation_plan_exact",
        "calendar_actions_exact",
        "state_chain_complete",
        "protected_sources_unchanged",
        "participant_price_coverage_complete",
        "forum_profile_source_cue_join_complete",
    ):
        if validation.get(key) is not True:
            raise RuntimeError(f"Episode 01 technical gate failed: {key}")
    if validation.get("participant_price_cells_expected") != 150:
        raise RuntimeError("Episode 01 expected participant price-cell count mismatch")
    if validation.get("participant_price_cells_missing") != 0:
        raise RuntimeError("Episode 01 has missing participant price cells")
    if validation.get("participant_price_cells_invalid") != 0:
        raise RuntimeError("Episode 01 has invalid participant price cells")
    if validation.get("participant_visible_nonrepost_posts_checked") != 193:
        raise RuntimeError("Episode 01 checked forum-post count mismatch")
    if validation.get("missing_same_day_profile_snapshots") != 0:
        raise RuntimeError("Episode 01 has missing same-day profile snapshots")

    outputs = record["outputs"]
    if outputs["agent_world_db"].get("sha256") != (
        "f9999c8e6774eb5dd2ffade5f5503ac0f863aae9e458636e92fb427198ce1741"
    ):
        raise RuntimeError("Episode 01 agent_world.db hash mismatch in tracked record")
    if outputs["forum_db"].get("sha256") != (
        "3be8a5682049e011b5f2c74d40e9bc42e265364f3bb30f82f85cb4d54d064dca"
    ):
        raise RuntimeError("Episode 01 forum.db hash mismatch in tracked record")

    semantics = record["freeze_semantics"]
    for key in (
        "episode_must_not_be_rerun_or_replaced_for_natural_outcomes",
        "episode_must_not_be_rerun_or_replaced_for_cross_episode_similarity",
        "tracked_record_does_not_replace_raw_formal_assets",
        "raw_formal_assets_remain_gitignored",
    ):
        if semantics.get(key) is not True:
            raise RuntimeError(f"Episode 01 freeze semantic failed: {key}")


def _load_json_if_present(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def validate_local_evidence_if_present(
    repo_root: Path, record: dict[str, Any]
) -> dict[str, Any]:
    outputs = record["outputs"]
    agent_path = repo_root / outputs["agent_world_db"]["path"]
    forum_path = repo_root / outputs["forum_db"]["path"]
    episode_manifest_path = repo_root / record["source_manifests"]["episode_manifest"]
    attempt_manifest_path = repo_root / record["source_manifests"]["attempt_manifest"]

    any_present = any(
        path.exists()
        for path in (agent_path, forum_path, episode_manifest_path, attempt_manifest_path)
    )
    if not any_present:
        return {
            "local_formal_evidence_present": False,
            "local_agent_world_db_hash_match": None,
            "local_forum_db_hash_match": None,
            "episode_manifest_match": None,
            "attempt_manifest_match": None,
        }

    required_paths = (agent_path, forum_path, episode_manifest_path, attempt_manifest_path)
    missing = [str(path.relative_to(repo_root)) for path in required_paths if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Partial local Episode 01 formal evidence is not acceptable; missing: "
            + ", ".join(missing)
        )

    agent_match = _sha256(agent_path) == outputs["agent_world_db"]["sha256"]
    forum_match = _sha256(forum_path) == outputs["forum_db"]["sha256"]
    if not agent_match:
        raise RuntimeError("Local Episode 01 agent_world.db does not match tracked freeze record")
    if not forum_match:
        raise RuntimeError("Local Episode 01 forum.db does not match tracked freeze record")

    episode_manifest = _load_json_if_present(episode_manifest_path)
    attempt_manifest = _load_json_if_present(attempt_manifest_path)
    assert episode_manifest is not None
    assert attempt_manifest is not None

    episode_manifest_match = (
        episode_manifest.get("status") == "formal_frozen"
        and episode_manifest.get("episode_id") == record["episode_id"]
        and episode_manifest.get("execution_plan_sha256")
        == record["producer_identity"]["phase13c_execution_plan_sha256"]
        and episode_manifest.get("producer_contract_sha256")
        == record["producer_identity"]["phase13d_producer_contract_sha256"]
        and episode_manifest.get("execution", {}).get("active_agent_pipeline_executions_completed")
        == 193
        and episode_manifest.get("execution", {}).get("failed_agent_pipeline_count") == 0
        and episode_manifest.get("validation", {}).get("state_chain_complete") is True
        and episode_manifest.get("outputs", {}).get("agent_world_db", {}).get("sha256")
        == outputs["agent_world_db"]["sha256"]
        and episode_manifest.get("outputs", {}).get("forum_db", {}).get("sha256")
        == outputs["forum_db"]["sha256"]
    )
    if not episode_manifest_match:
        raise RuntimeError("Local Episode 01 episode_manifest.json disagrees with tracked freeze record")

    attempt_manifest_match = (
        attempt_manifest.get("status") == "FORMAL_FROZEN"
        and attempt_manifest.get("episode_id") == record["episode_id"]
        and attempt_manifest.get("attempt_number") == 1
        and attempt_manifest.get("phase13c_execution_plan_sha256")
        == record["producer_identity"]["phase13c_execution_plan_sha256"]
        and attempt_manifest.get("phase13d_producer_contract_sha256")
        == record["producer_identity"]["phase13d_producer_contract_sha256"]
        and attempt_manifest.get("partial_resume_used") is False
        and attempt_manifest.get("seed_substitution_used") is False
        and attempt_manifest.get("outcome_review_used_for_acceptance") is False
        and attempt_manifest.get("episode_similarity_review_used_for_acceptance") is False
        and attempt_manifest.get("formal_outputs", {}).get("agent_world_db", {}).get("sha256")
        == outputs["agent_world_db"]["sha256"]
        and attempt_manifest.get("formal_outputs", {}).get("forum_db", {}).get("sha256")
        == outputs["forum_db"]["sha256"]
    )
    if not attempt_manifest_match:
        raise RuntimeError("Local Episode 01 attempt_manifest.json disagrees with tracked freeze record")

    return {
        "local_formal_evidence_present": True,
        "local_agent_world_db_hash_match": True,
        "local_forum_db_hash_match": True,
        "episode_manifest_match": True,
        "attempt_manifest_match": True,
    }


def validate_episode01_freeze_record(repo_root: Path) -> dict[str, Any]:
    record = load_episode01_freeze_record(repo_root)
    validate_record_semantics(record)
    local = validate_local_evidence_if_present(repo_root, record)
    return {
        "status": "PASS",
        "record_sha256": EXPECTED_EPISODE01_RECORD_SHA256,
        "episode_id": record["episode_id"],
        "acceptance_status": record["acceptance"]["status"],
        "accepted_attempt_number": record["acceptance"]["accepted_attempt_number"],
        "producer_git_commit": record["producer_identity"]["git_commit"],
        "phase13c_execution_plan_sha256": record["producer_identity"]["phase13c_execution_plan_sha256"],
        "phase13d_producer_contract_sha256": record["producer_identity"]["phase13d_producer_contract_sha256"],
        "agent_world_db_sha256": record["outputs"]["agent_world_db"]["sha256"],
        "forum_db_sha256": record["outputs"]["forum_db"]["sha256"],
        "formal_world_ticks": record["execution"]["formal_world_ticks"],
        "active_agent_pipeline_executions_completed": record["execution"]["active_agent_pipeline_executions_completed"],
        "failed_agent_pipeline_count": record["execution"]["failed_agent_pipeline_count"],
        "outcome_conditioned_acceptance": record["acceptance"]["outcome_conditioned_acceptance"],
        "episode_similarity_review_used_for_acceptance": record["acceptance"]["episode_similarity_review_used_for_acceptance"],
        "seed_substitution_used": record["acceptance"]["seed_substitution_used"],
        "partial_resume_used": record["acceptance"]["partial_resume_used"],
        **local,
    }
