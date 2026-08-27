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
EPISODE02_RECORD_RELATIVE_PATH = Path(
    "marketlens/episode/freeze_records/marketlens-canonical-episode-v1-e02.json"
)
EXPECTED_EPISODE02_RECORD_SHA256 = "b902e8113d20ec10e08e8ae6e2562d7f3c66b6b677ebcb997dfa71d80852d0c5"
EPISODE03_RECORD_RELATIVE_PATH = Path(
    "marketlens/episode/freeze_records/marketlens-canonical-episode-v1-e03.json"
)
EXPECTED_EPISODE03_RECORD_SHA256 = "8a702cb5c714727a84ea5266ab794b4254bfc32e4762f3b63e5c29798ea6746c"

_COMMON_PLAN_SHA256 = "a907079281f7deca590bd7ec741b56fab614f05b0cdd869c5f2c345fb048a8bc"
_COMMON_PRODUCER_SHA256 = "14db0ae7a525ef464975f7ba4da69d98eb8ffd4058d491555a32ee25f92a9126"
_COMMON_N30_SHA256 = "60d846b21c15e2213f6f897a17a7ea98039fbf461abe54ee89e1b6779d24b2d4"
_COMMON_CANDIDATE_RUNTIME_SHA256 = "98a95b5ee631ac4a57648867103c25828bfa1b8af640871640cdf071e2f01a26"

_EXPECTED = {
    "marketlens-canonical-episode-v1-e01": {
        "label": "Episode 01",
        "slot": 1,
        "record_path": EPISODE01_RECORD_RELATIVE_PATH,
        "record_sha256": EXPECTED_EPISODE01_RECORD_SHA256,
        "accepted_attempt_number": 1,
        "git_commit": "96c2a0b33587293b76eee9ba01978ef75d902abb",
        "agent_world_db_sha256": "f9999c8e6774eb5dd2ffade5f5503ac0f863aae9e458636e92fb427198ce1741",
        "forum_db_sha256": "3be8a5682049e011b5f2c74d40e9bc42e265364f3bb30f82f85cb4d54d064dca",
    },
    "marketlens-canonical-episode-v1-e02": {
        "label": "Episode 02",
        "slot": 2,
        "record_path": EPISODE02_RECORD_RELATIVE_PATH,
        "record_sha256": EXPECTED_EPISODE02_RECORD_SHA256,
        "accepted_attempt_number": 1,
        "git_commit": "e2a3e57a008aa3e9744d447047637dcffc4e3d7c",
        "agent_world_db_sha256": "577aedbe7f5d07d6fd573e2614275ac99ee804d68d38b303fe9c590c2759efbd",
        "forum_db_sha256": "b4c1fcd260cf8a84bf8860c8de09c1ede30a7d95ffcb92a81edce67eb5b9fb0b",
    },
    "marketlens-canonical-episode-v1-e03": {
        "label": "Episode 03",
        "slot": 3,
        "record_path": EPISODE03_RECORD_RELATIVE_PATH,
        "record_sha256": EXPECTED_EPISODE03_RECORD_SHA256,
        "accepted_attempt_number": 3,
        "git_commit": "f3035ecd334074c52f3c48bd41afdf55bf10d964",
        "agent_world_db_sha256": "da8a077875d0011239f0c713e5b2e3556901bc9a828793f05f08c69f1584cb31",
        "forum_db_sha256": "42ab83af3aa2da27b4c29f9f9a8097f98f47e87e03bc3fd4f1a606c1dc248f0f",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_freeze_record(repo_root: Path, episode_id: str) -> dict[str, Any]:
    expected = _EXPECTED[episode_id]
    path = repo_root / expected["record_path"]
    if not path.is_file():
        raise RuntimeError(f"Missing tracked {expected['label']} freeze record: {path}")
    actual_sha = _sha256(path)
    if actual_sha != expected["record_sha256"]:
        raise RuntimeError(
            f"{expected['label']} freeze record hash mismatch: "
            f"expected {expected['record_sha256']}, got {actual_sha}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_episode01_freeze_record(repo_root: Path) -> dict[str, Any]:
    return _load_freeze_record(repo_root, "marketlens-canonical-episode-v1-e01")


def load_episode02_freeze_record(repo_root: Path) -> dict[str, Any]:
    return _load_freeze_record(repo_root, "marketlens-canonical-episode-v1-e02")


def load_episode03_freeze_record(repo_root: Path) -> dict[str, Any]:
    return _load_freeze_record(repo_root, "marketlens-canonical-episode-v1-e03")


def validate_record_semantics(record: dict[str, Any]) -> None:
    episode_id = record.get("episode_id")
    if episode_id not in _EXPECTED:
        raise RuntimeError(f"Unknown canonical episode freeze-record identity: {episode_id}")
    expected = _EXPECTED[episode_id]
    label = expected["label"]

    if record.get("record_schema_version") != "marketlens-canonical-episode-freeze-record/1.0":
        raise RuntimeError(f"Unexpected {label} freeze-record schema version")
    if record.get("record_status") != "tracked_formal_freeze_record":
        raise RuntimeError(f"{label} tracked record is not frozen")
    if record.get("episode_pool_id") != "marketlens-canonical-episode-pool-v1":
        raise RuntimeError(f"{label} pool identity mismatch")
    if record.get("episode_slot") != expected["slot"]:
        raise RuntimeError(f"{label} slot mismatch")

    acceptance = record["acceptance"]
    required_acceptance = {
        "status": "formal_frozen_technically_valid",
        "accepted_attempt_number": expected["accepted_attempt_number"],
        "acceptance_basis": "predeclared_technical_gates_only",
        "outcome_conditioned_acceptance": False,
        "episode_similarity_review_used_for_acceptance": False,
        "seed_substitution_used": False,
        "partial_resume_used": False,
    }
    for key, expected_value in required_acceptance.items():
        if acceptance.get(key) != expected_value:
            raise RuntimeError(f"{label} acceptance invariant failed: {key}")

    producer = record["producer_identity"]
    required_producer = {
        "git_commit": expected["git_commit"],
        "git_branch": "dissertation",
        "phase13c_execution_plan_sha256": _COMMON_PLAN_SHA256,
        "phase13d_producer_contract_sha256": _COMMON_PRODUCER_SHA256,
        "backend_model_name": "gpt-5.4-mini",
        "backend_base_url": "https://zhi-api.com/v1",
        "api_key_recorded": False,
    }
    for key, expected_value in required_producer.items():
        if producer.get(key) != expected_value:
            raise RuntimeError(f"{label} producer invariant failed: {key}")

    population = record["population"]
    if population.get("size") != 30:
        raise RuntimeError(f"{label} population size mismatch")
    if population.get("selection_seed") != "marketlens-dev-population-01":
        raise RuntimeError(f"{label} population selection seed mismatch")
    if population.get("activation_seed") != "marketlens-phase09b-activation-01":
        raise RuntimeError(f"{label} activation seed mismatch")
    if population.get("selected_agent_ids_sha256") != _COMMON_N30_SHA256:
        raise RuntimeError(f"{label} N30 identity mismatch")

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
    for key, expected_value in expected_execution.items():
        if execution.get(key) != expected_value:
            raise RuntimeError(f"{label} execution invariant failed: {key}")

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
            raise RuntimeError(f"{label} technical gate failed: {key}")
    if validation.get("participant_price_cells_expected") != 150:
        raise RuntimeError(f"{label} expected participant price-cell count mismatch")
    if validation.get("participant_price_cells_missing") != 0:
        raise RuntimeError(f"{label} has missing participant price cells")
    if validation.get("participant_price_cells_invalid") != 0:
        raise RuntimeError(f"{label} has invalid participant price cells")
    if validation.get("participant_visible_nonrepost_posts_checked") != 193:
        raise RuntimeError(f"{label} checked forum-post count mismatch")
    if validation.get("missing_same_day_profile_snapshots") != 0:
        raise RuntimeError(f"{label} has missing same-day profile snapshots")

    if episode_id == "marketlens-canonical-episode-v1-e03":
        history = record.get("attempt_history")
        if not isinstance(history, dict):
            raise RuntimeError("Episode 03 attempt history is missing")
        policy = history.get("policy", {})
        required_policy = {
            "failed_attempt_evidence_retained": True,
            "partial_resume_allowed": False,
            "restart_from_frozen_initial_state_only": True,
            "acceptance_not_outcome_conditioned": True,
        }
        for key, expected_value in required_policy.items():
            if policy.get(key) != expected_value:
                raise RuntimeError(f"Episode 03 attempt-history policy failed: {key}")
        if history.get("frozen_initial_runtime_sha256") != _COMMON_CANDIDATE_RUNTIME_SHA256:
            raise RuntimeError("Episode 03 frozen initial runtime identity mismatch")
        attempts = history.get("attempts")
        if not isinstance(attempts, list) or [a.get("attempt_number") for a in attempts] != [1, 2, 3]:
            raise RuntimeError("Episode 03 attempt history must contain attempts 1, 2, 3 in order")
        a1, a2, a3 = attempts
        expected_a1 = {
            "acceptance_role": "not_accepted",
            "classification": "external_process_interruption",
            "raw_manifest_status": "running",
            "days_completed": 12,
            "active_agent_pipeline_executions_completed": 90,
            "manifest_sha256": "1ff97c0a9b03120e92ac9742ba34524a5115ba480dbf9f69b64f1b8ac4ed3bb8",
            "workspace_agent_world_db_sha256": "dfdff33203d3c7abc9955171d9a0d1beb74d32ce5de81d0941f84cf1c3f509f3",
            "workspace_forum_db_sha256": "f2e27b3a701a3969b5fc5d7f6cb74210e5d1748bb9314a43e24c807fd769d715",
        }
        expected_a2 = {
            "acceptance_role": "not_accepted",
            "classification": "producer_captured_technical_invalid",
            "raw_manifest_status": "TECHNICAL_INVALID",
            "error_type": "Phase09CError",
            "days_completed": 12,
            "active_agent_pipeline_executions_completed": 90,
            "manifest_sha256": "dfe5718e85ff8ebebecfa2beedd786016daa1c3918ec91c00d15da479d29b502",
            "workspace_agent_world_db_sha256": "0fbeac8e4438dc6ebd5f3f0951977c5c7bcaf5bd25a7823dae2ebada5f61cc33",
            "workspace_forum_db_sha256": "3a9d5d24a1c797bd53f99cf942420150a8e8012e9b12f2b1ae92e85f1ec08906",
        }
        expected_a3 = {
            "acceptance_role": "accepted",
            "classification": "formal_frozen_technical_pass",
            "raw_manifest_status": "FORMAL_FROZEN",
            "days_completed": 27,
            "active_agent_pipeline_executions_completed": 193,
        }
        for attempt, expected_fields in ((a1, expected_a1), (a2, expected_a2), (a3, expected_a3)):
            for key, expected_value in expected_fields.items():
                if attempt.get(key) != expected_value:
                    raise RuntimeError(
                        f"Episode 03 attempt {attempt.get('attempt_number')} provenance failed: {key}"
                    )
            for flag in (
                "partial_resume_used",
                "seed_substitution_used",
                "outcome_review_used_for_acceptance",
                "episode_similarity_review_used_for_acceptance",
            ):
                if attempt.get(flag) is not False:
                    raise RuntimeError(
                        f"Episode 03 attempt {attempt.get('attempt_number')} provenance failed: {flag}"
                    )

    outputs = record["outputs"]
    if outputs["agent_world_db"].get("sha256") != expected["agent_world_db_sha256"]:
        raise RuntimeError(f"{label} agent_world.db hash mismatch in tracked record")
    if outputs["forum_db"].get("sha256") != expected["forum_db_sha256"]:
        raise RuntimeError(f"{label} forum.db hash mismatch in tracked record")

    semantics = record["freeze_semantics"]
    for key in (
        "episode_must_not_be_rerun_or_replaced_for_natural_outcomes",
        "episode_must_not_be_rerun_or_replaced_for_cross_episode_similarity",
        "tracked_record_does_not_replace_raw_formal_assets",
        "raw_formal_assets_remain_gitignored",
    ):
        if semantics.get(key) is not True:
            raise RuntimeError(f"{label} freeze semantic failed: {key}")


def _load_json_if_present(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def validate_local_evidence_if_present(
    repo_root: Path, record: dict[str, Any]
) -> dict[str, Any]:
    episode_id = record["episode_id"]
    expected = _EXPECTED[episode_id]
    label = expected["label"]
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
            f"Partial local {label} formal evidence is not acceptable; missing: "
            + ", ".join(missing)
        )

    agent_match = _sha256(agent_path) == outputs["agent_world_db"]["sha256"]
    forum_match = _sha256(forum_path) == outputs["forum_db"]["sha256"]
    if not agent_match:
        raise RuntimeError(f"Local {label} agent_world.db does not match tracked freeze record")
    if not forum_match:
        raise RuntimeError(f"Local {label} forum.db does not match tracked freeze record")

    episode_manifest = _load_json_if_present(episode_manifest_path)
    attempt_manifest = _load_json_if_present(attempt_manifest_path)
    assert episode_manifest is not None
    assert attempt_manifest is not None

    episode_manifest_match = (
        episode_manifest.get("status") == "formal_frozen"
        and episode_manifest.get("episode_id") == record["episode_id"]
        and episode_manifest.get("episode_slot", expected["slot"]) == expected["slot"]
        and episode_manifest.get("git", {}).get("commit", expected["git_commit"]) == expected["git_commit"]
        and episode_manifest.get("execution_plan_sha256") == _COMMON_PLAN_SHA256
        and episode_manifest.get("producer_contract_sha256") == _COMMON_PRODUCER_SHA256
        and episode_manifest.get("world", {}).get("formal_world_ticks", 27) == 27
        and episode_manifest.get("execution", {}).get("active_agent_pipeline_executions_completed") == 193
        and episode_manifest.get("execution", {}).get("failed_agent_pipeline_count") == 0
        and episode_manifest.get("validation", {}).get("all_days_complete", True) is True
        and episode_manifest.get("validation", {}).get("activation_plan_exact", True) is True
        and episode_manifest.get("validation", {}).get("calendar_actions_exact", True) is True
        and episode_manifest.get("validation", {}).get("state_chain_complete") is True
        and episode_manifest.get("validation", {}).get("protected_sources_unchanged", True) is True
        and episode_manifest.get("validation", {}).get("participant_price_coverage_complete", True) is True
        and episode_manifest.get("validation", {}).get("forum_profile_source_cue_join_complete", True) is True
        and episode_manifest.get("outputs", {}).get("agent_world_db", {}).get("sha256") == outputs["agent_world_db"]["sha256"]
        and episode_manifest.get("outputs", {}).get("forum_db", {}).get("sha256") == outputs["forum_db"]["sha256"]
    )
    if not episode_manifest_match:
        raise RuntimeError(f"Local {label} episode_manifest.json disagrees with tracked freeze record")

    attempt_manifest_match = (
        attempt_manifest.get("status") == "FORMAL_FROZEN"
        and attempt_manifest.get("episode_id") == record["episode_id"]
        and attempt_manifest.get("attempt_number") == expected["accepted_attempt_number"]
        and attempt_manifest.get("git", {}).get("commit", expected["git_commit"]) == expected["git_commit"]
        and attempt_manifest.get("phase13c_execution_plan_sha256") == _COMMON_PLAN_SHA256
        and attempt_manifest.get("phase13d_producer_contract_sha256") == _COMMON_PRODUCER_SHA256
        and attempt_manifest.get("partial_resume_used") is False
        and attempt_manifest.get("seed_substitution_used") is False
        and attempt_manifest.get("outcome_review_used_for_acceptance") is False
        and attempt_manifest.get("episode_similarity_review_used_for_acceptance") is False
        and attempt_manifest.get("days_completed", 27) == 27
        and attempt_manifest.get("active_agent_pipeline_executions_completed", 193) == 193
        and attempt_manifest.get("formal_outputs", {}).get("agent_world_db", {}).get("sha256") == outputs["agent_world_db"]["sha256"]
        and attempt_manifest.get("formal_outputs", {}).get("forum_db", {}).get("sha256") == outputs["forum_db"]["sha256"]
    )
    if not attempt_manifest_match:
        raise RuntimeError(f"Local {label} attempt_manifest.json disagrees with tracked freeze record")

    return {
        "local_formal_evidence_present": True,
        "local_agent_world_db_hash_match": True,
        "local_forum_db_hash_match": True,
        "episode_manifest_match": True,
        "attempt_manifest_match": True,
    }


def validate_attempt_history_if_present(
    repo_root: Path, record: dict[str, Any]
) -> dict[str, Any]:
    if record.get("episode_id") != "marketlens-canonical-episode-v1-e03":
        return {}

    history = record.get("attempt_history", {})
    attempts = {item["attempt_number"]: item for item in history.get("attempts", [])}
    root = repo_root / "artifacts/formal/canonical_episode/marketlens-canonical-episode-v1-e03"
    paths = {
        1: {
            "manifest": root / "attempt_001/attempt_manifest.json",
            "agent": root / "attempt_001/workspace/agent_world.db",
            "forum": root / "attempt_001/workspace/forum.db",
        },
        2: {
            "manifest": root / "attempt_002/attempt_manifest.json",
            "agent": root / "attempt_002/workspace/agent_world.db",
            "forum": root / "attempt_002/workspace/forum.db",
        },
    }
    all_paths = [path for group in paths.values() for path in group.values()]
    if not any(path.exists() for path in all_paths):
        return {
            "local_failed_attempt_history_present": False,
            "attempt001_fingerprint_match": None,
            "attempt002_fingerprint_match": None,
        }
    missing = [str(path.relative_to(repo_root)) for path in all_paths if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Partial local Episode 03 failed-attempt evidence is not acceptable; missing: "
            + ", ".join(missing)
        )

    matches: dict[int, bool] = {}
    for number in (1, 2):
        entry = attempts[number]
        group = paths[number]
        fingerprint_match = (
            _sha256(group["manifest"]) == entry["manifest_sha256"]
            and _sha256(group["agent"]) == entry["workspace_agent_world_db_sha256"]
            and _sha256(group["forum"]) == entry["workspace_forum_db_sha256"]
        )
        if not fingerprint_match:
            raise RuntimeError(f"Local Episode 03 attempt_{number:03d} fingerprint mismatch")

        manifest = _load_json_if_present(group["manifest"])
        assert manifest is not None
        common_match = (
            manifest.get("episode_id") == record["episode_id"]
            and manifest.get("attempt_number") == number
            and manifest.get("git", {}).get("commit") == record["producer_identity"]["git_commit"]
            and manifest.get("phase13c_execution_plan_sha256") == _COMMON_PLAN_SHA256
            and manifest.get("phase13d_producer_contract_sha256") == _COMMON_PRODUCER_SHA256
            and manifest.get("candidate_fixture", {}).get("runtime_sha256_before") == _COMMON_CANDIDATE_RUNTIME_SHA256
            and manifest.get("partial_resume_used") is False
            and manifest.get("seed_substitution_used") is False
            and manifest.get("outcome_review_used_for_acceptance") is False
            and manifest.get("episode_similarity_review_used_for_acceptance") is False
            and manifest.get("days_completed") == 12
            and manifest.get("active_agent_pipeline_executions_completed") == 90
        )
        if number == 1:
            manifest_match = common_match and manifest.get("status") == "running"
        else:
            manifest_match = (
                common_match
                and manifest.get("status") == "TECHNICAL_INVALID"
                and manifest.get("error_type") == "Phase09CError"
                and manifest.get("protected_sources_unchanged_at_failure_capture") is True
                and manifest.get("workspace_preserved") is True
                and manifest.get("partial_resume_allowed") is False
                and manifest.get("restart_policy") == "new attempt from frozen initial N30 state only"
            )
        if not manifest_match:
            raise RuntimeError(f"Local Episode 03 attempt_{number:03d} manifest provenance mismatch")
        matches[number] = True

    return {
        "local_failed_attempt_history_present": True,
        "attempt001_fingerprint_match": matches[1],
        "attempt002_fingerprint_match": matches[2],
    }


def _validate_episode_freeze_record(repo_root: Path, episode_id: str) -> dict[str, Any]:
    record = _load_freeze_record(repo_root, episode_id)
    validate_record_semantics(record)
    local = validate_local_evidence_if_present(repo_root, record)
    history_local = validate_attempt_history_if_present(repo_root, record)
    expected = _EXPECTED[episode_id]
    return {
        "status": "PASS",
        "record_sha256": expected["record_sha256"],
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
        **history_local,
    }


def validate_episode01_freeze_record(repo_root: Path) -> dict[str, Any]:
    return _validate_episode_freeze_record(repo_root, "marketlens-canonical-episode-v1-e01")


def validate_episode02_freeze_record(repo_root: Path) -> dict[str, Any]:
    return _validate_episode_freeze_record(repo_root, "marketlens-canonical-episode-v1-e02")


def validate_episode03_freeze_record(repo_root: Path) -> dict[str, Any]:
    return _validate_episode_freeze_record(repo_root, "marketlens-canonical-episode-v1-e03")
