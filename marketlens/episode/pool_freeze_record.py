from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from marketlens.episode.contract import validate_formal_episode_pool_manifest
from marketlens.episode.freeze_record import (
    EPISODE01_RECORD_RELATIVE_PATH,
    EPISODE02_RECORD_RELATIVE_PATH,
    EPISODE03_RECORD_RELATIVE_PATH,
    EXPECTED_EPISODE01_RECORD_SHA256,
    EXPECTED_EPISODE02_RECORD_SHA256,
    EXPECTED_EPISODE03_RECORD_SHA256,
    validate_episode01_freeze_record,
    validate_episode02_freeze_record,
    validate_episode03_freeze_record,
)

POOL_RECORD_RELATIVE_PATH = Path(
    "marketlens/episode/freeze_records/marketlens-canonical-episode-pool-v1.json"
)
EXPECTED_POOL_RECORD_SHA256 = "ce6d906436f153102412cd8e17da5bc74ec276c422272284d679e495c64db854"
EXPECTED_POOL_MANIFEST_SHA256 = (
    "3f32fa3d67878cb05335af8a89305e0487a4501a834b054d53a16129047ad086"
)
POOL_MANIFEST_RELATIVE_PATH = Path(
    "data/marketlens/canonical_episode/v1/pool_manifest.json"
)

_EXPECTED_POOL_ID = "marketlens-canonical-episode-pool-v1"
_EXPECTED_PLAN_SHA256 = "a907079281f7deca590bd7ec741b56fab614f05b0cdd869c5f2c345fb048a8bc"
_EXPECTED_PRODUCER_SHA256 = "14db0ae7a525ef464975f7ba4da69d98eb8ffd4058d491555a32ee25f92a9126"
_EXPECTED_FINALIZATION_GIT_COMMIT = "592a1e4658f978f344639ea9233a40fc4938c286"

_EPISODES = {
    "marketlens-canonical-episode-v1-e01": {
        "record_path": EPISODE01_RECORD_RELATIVE_PATH,
        "record_sha256": EXPECTED_EPISODE01_RECORD_SHA256,
        "accepted_attempt_number": 1,
        "agent_world_db_sha256": "f9999c8e6774eb5dd2ffade5f5503ac0f863aae9e458636e92fb427198ce1741",
        "forum_db_sha256": "3be8a5682049e011b5f2c74d40e9bc42e265364f3bb30f82f85cb4d54d064dca",
        "validator": validate_episode01_freeze_record,
    },
    "marketlens-canonical-episode-v1-e02": {
        "record_path": EPISODE02_RECORD_RELATIVE_PATH,
        "record_sha256": EXPECTED_EPISODE02_RECORD_SHA256,
        "accepted_attempt_number": 1,
        "agent_world_db_sha256": "577aedbe7f5d07d6fd573e2614275ac99ee804d68d38b303fe9c590c2759efbd",
        "forum_db_sha256": "b4c1fcd260cf8a84bf8860c8de09c1ede30a7d95ffcb92a81edce67eb5b9fb0b",
        "validator": validate_episode02_freeze_record,
    },
    "marketlens-canonical-episode-v1-e03": {
        "record_path": EPISODE03_RECORD_RELATIVE_PATH,
        "record_sha256": EXPECTED_EPISODE03_RECORD_SHA256,
        "accepted_attempt_number": 3,
        "agent_world_db_sha256": "da8a077875d0011239f0c713e5b2e3556901bc9a828793f05f08c69f1584cb31",
        "forum_db_sha256": "42ab83af3aa2da27b4c29f9f9a8097f98f47e87e03bc3fd4f1a606c1dc248f0f",
        "validator": validate_episode03_freeze_record,
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pool_freeze_record(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    path = root / POOL_RECORD_RELATIVE_PATH
    if not path.is_file():
        raise RuntimeError(f"Missing tracked canonical pool freeze record: {path}")
    actual_sha = _sha256(path)
    if actual_sha != EXPECTED_POOL_RECORD_SHA256:
        raise RuntimeError(
            "Canonical pool freeze-record hash mismatch: "
            f"expected {EXPECTED_POOL_RECORD_SHA256}, got {actual_sha}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def validate_pool_record_semantics(record: dict[str, Any]) -> None:
    if record.get("record_schema_version") != "marketlens-canonical-episode-pool-freeze-record/1.0":
        raise RuntimeError("Unexpected canonical pool freeze-record schema version")
    if record.get("record_status") != "tracked_formal_pool_freeze_record":
        raise RuntimeError("Canonical pool tracked record is not frozen")
    if record.get("episode_pool_id") != _EXPECTED_POOL_ID:
        raise RuntimeError("Canonical pool identity mismatch")
    if record.get("formal_pool_status") != "formal_frozen":
        raise RuntimeError("Canonical pool formal status mismatch")

    source = record.get("source_pool_manifest", {})
    if source.get("path") != str(POOL_MANIFEST_RELATIVE_PATH):
        raise RuntimeError("Canonical pool source-manifest path mismatch")
    if source.get("sha256") != EXPECTED_POOL_MANIFEST_SHA256:
        raise RuntimeError("Canonical pool source-manifest SHA-256 mismatch")

    context = record.get("finalization_context", {})
    required_context = {
        "git_commit": _EXPECTED_FINALIZATION_GIT_COMMIT,
        "git_branch": "dissertation",
        "phase13c_execution_plan_sha256": _EXPECTED_PLAN_SHA256,
        "phase13d_producer_contract_sha256": _EXPECTED_PRODUCER_SHA256,
        "pool_finalization_is_zero_llm": True,
        "llm_api_calls": 0,
        "outcome_review_used": False,
        "episode_similarity_review_used": False,
    }
    for key, expected in required_context.items():
        if context.get(key) != expected:
            raise RuntimeError(f"Canonical pool finalization invariant failed: {key}")

    assignment = record.get("participant_assignment", {})
    required_assignment = {
        "mode": "balanced_random_across_episode_pool",
        "episode_id_recorded_for_analysis": True,
        "assignment_uses_episode_outcomes": False,
    }
    for key, expected in required_assignment.items():
        if assignment.get(key) != expected:
            raise RuntimeError(f"Canonical pool assignment invariant failed: {key}")

    rows = record.get("episode_records")
    expected_ids = list(_EPISODES)
    if not isinstance(rows, list) or [row.get("episode_id") for row in rows] != expected_ids:
        raise RuntimeError("Canonical pool tracked episode membership/order mismatch")

    for row in rows:
        episode_id = row["episode_id"]
        expected = _EPISODES[episode_id]
        required = {
            "tracked_record_path": str(expected["record_path"]),
            "tracked_record_sha256": expected["record_sha256"],
            "accepted_attempt_number": expected["accepted_attempt_number"],
            "active_agent_pipeline_executions_completed": 193,
            "agent_world_db_sha256": expected["agent_world_db_sha256"],
            "forum_db_sha256": expected["forum_db_sha256"],
        }
        for key, value in required.items():
            if row.get(key) != value:
                raise RuntimeError(f"Canonical pool {episode_id} invariant failed: {key}")

    aggregate = record.get("aggregate_execution", {})
    required_aggregate = {
        "episode_count": 3,
        "formal_world_ticks_per_episode": 27,
        "aggregate_formal_world_ticks": 81,
        "agent_pipeline_executions_per_episode": 193,
        "aggregate_agent_pipeline_executions": 579,
        "exact_backend_api_call_count_claimed": False,
    }
    for key, expected in required_aggregate.items():
        if aggregate.get(key) != expected:
            raise RuntimeError(f"Canonical pool aggregate invariant failed: {key}")

    semantics = record.get("freeze_semantics", {})
    for key in (
        "all_three_episode_records_are_required",
        "pool_manifest_must_not_be_regenerated_or_overwritten",
        "episodes_must_not_be_rerun_or_replaced_for_natural_outcomes",
        "episodes_must_not_be_rerun_or_replaced_for_cross_episode_similarity",
        "tracked_record_does_not_replace_raw_formal_assets",
        "raw_formal_assets_remain_gitignored",
    ):
        if semantics.get(key) is not True:
            raise RuntimeError(f"Canonical pool freeze semantic failed: {key}")


def validate_tracked_episode_records(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    results: dict[str, Any] = {}
    for episode_id, expected in _EPISODES.items():
        record_path = root / expected["record_path"]
        if not record_path.is_file():
            raise RuntimeError(f"Missing tracked per-episode freeze record: {record_path}")
        if _sha256(record_path) != expected["record_sha256"]:
            raise RuntimeError(f"Tracked per-episode freeze-record hash mismatch: {episode_id}")
        result = expected["validator"](root)
        if result.get("status") != "PASS":
            raise RuntimeError(f"Tracked per-episode validator failed: {episode_id}")
        if result.get("accepted_attempt_number") != expected["accepted_attempt_number"]:
            raise RuntimeError(f"Tracked per-episode accepted attempt drifted: {episode_id}")
        if result.get("active_agent_pipeline_executions_completed") != 193:
            raise RuntimeError(f"Tracked per-episode pipeline count drifted: {episode_id}")
        results[episode_id] = {
            "status": "PASS",
            "accepted_attempt_number": result["accepted_attempt_number"],
        }
    return results


def validate_local_pool_evidence_if_present(
    repo_root: str | Path, record: dict[str, Any]
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    pool_path = root / record["source_pool_manifest"]["path"]
    if not pool_path.exists():
        return {
            "local_formal_pool_manifest_present": False,
            "local_pool_manifest_hash_match": None,
            "local_pool_contract_validation": None,
            "local_pool_finalization_fields_match": None,
        }
    if not pool_path.is_file():
        raise RuntimeError(f"Canonical pool manifest path is not a file: {pool_path}")

    actual_sha = _sha256(pool_path)
    if actual_sha != record["source_pool_manifest"]["sha256"]:
        raise RuntimeError(
            "Local canonical pool manifest hash mismatch: "
            f"expected {record['source_pool_manifest']['sha256']}, got {actual_sha}"
        )

    manifest = json.loads(pool_path.read_text(encoding="utf-8"))
    validate_formal_episode_pool_manifest(manifest, repo_root=root, verify_files=True)

    finalization_match = (
        manifest.get("manifest_schema_version") == "marketlens-canonical-episode-pool-manifest/1.0"
        and manifest.get("status") == "formal_frozen"
        and manifest.get("episode_pool_id") == _EXPECTED_POOL_ID
        and manifest.get("execution_plan_sha256") == _EXPECTED_PLAN_SHA256
        and manifest.get("producer_contract_sha256") == _EXPECTED_PRODUCER_SHA256
        and manifest.get("episode_count") == 3
        and manifest.get("participant_assignment", {}).get("mode")
            == "balanced_random_across_episode_pool"
        and manifest.get("participant_assignment", {}).get("episode_id_recorded_for_analysis") is True
        and manifest.get("participant_assignment", {}).get("assignment_uses_episode_outcomes") is False
        and manifest.get("finalization", {}).get("llm_api_calls") == 0
        and manifest.get("finalization", {}).get("outcome_review_used") is False
        and manifest.get("finalization", {}).get("episode_similarity_review_used") is False
    )
    if not finalization_match:
        raise RuntimeError("Local canonical pool manifest disagrees with tracked pool freeze record")

    return {
        "local_formal_pool_manifest_present": True,
        "local_pool_manifest_hash_match": True,
        "local_pool_contract_validation": True,
        "local_pool_finalization_fields_match": True,
    }


def validate_pool_freeze_record(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    record = load_pool_freeze_record(root)
    validate_pool_record_semantics(record)
    episode_results = validate_tracked_episode_records(root)
    local = validate_local_pool_evidence_if_present(root, record)
    return {
        "status": "PASS",
        "episode_pool_id": record["episode_pool_id"],
        "record_sha256": EXPECTED_POOL_RECORD_SHA256,
        "pool_manifest_sha256": EXPECTED_POOL_MANIFEST_SHA256,
        "episode_count": 3,
        "episode_ids": list(_EPISODES),
        "accepted_attempt_numbers": {
            episode_id: item["accepted_attempt_number"]
            for episode_id, item in episode_results.items()
        },
        "aggregate_agent_pipeline_executions": 579,
        "exact_backend_api_call_count_claimed": False,
        "llm_api_calls": 0,
        "outcome_review_used": False,
        "episode_similarity_review_used": False,
        **local,
    }
