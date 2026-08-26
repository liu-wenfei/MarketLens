from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from marketlens.episode.freeze_record import (
    EPISODE01_RECORD_RELATIVE_PATH,
    EPISODE02_RECORD_RELATIVE_PATH,
    EPISODE03_RECORD_RELATIVE_PATH,
    EXPECTED_EPISODE01_RECORD_SHA256,
    EXPECTED_EPISODE02_RECORD_SHA256,
    EXPECTED_EPISODE03_RECORD_SHA256,
    load_episode01_freeze_record,
    load_episode02_freeze_record,
    load_episode03_freeze_record,
    validate_attempt_history_if_present,
    validate_episode01_freeze_record,
    validate_episode02_freeze_record,
    validate_episode03_freeze_record,
    validate_local_evidence_if_present,
    validate_record_semantics,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_episode01_and_episode02_records_remain_exactly_frozen() -> None:
    assert _sha256(REPO_ROOT / EPISODE01_RECORD_RELATIVE_PATH) == EXPECTED_EPISODE01_RECORD_SHA256
    assert _sha256(REPO_ROOT / EPISODE02_RECORD_RELATIVE_PATH) == EXPECTED_EPISODE02_RECORD_SHA256
    assert load_episode01_freeze_record(REPO_ROOT)["acceptance"]["accepted_attempt_number"] == 1
    assert load_episode02_freeze_record(REPO_ROOT)["acceptance"]["accepted_attempt_number"] == 1
    assert validate_episode01_freeze_record(REPO_ROOT)["status"] == "PASS"
    assert validate_episode02_freeze_record(REPO_ROOT)["status"] == "PASS"


def test_tracked_episode03_record_has_exact_frozen_hash() -> None:
    record_path = REPO_ROOT / EPISODE03_RECORD_RELATIVE_PATH
    assert record_path.is_file()
    assert _sha256(record_path) == EXPECTED_EPISODE03_RECORD_SHA256


def test_tracked_episode03_record_semantics_pass() -> None:
    record = load_episode03_freeze_record(REPO_ROOT)
    validate_record_semantics(record)


def test_episode03_acceptance_is_attempt03_and_not_outcome_conditioned() -> None:
    record = load_episode03_freeze_record(REPO_ROOT)
    acceptance = record["acceptance"]
    assert acceptance["status"] == "formal_frozen_technically_valid"
    assert acceptance["accepted_attempt_number"] == 3
    assert acceptance["acceptance_basis"] == "predeclared_technical_gates_only"
    assert acceptance["outcome_conditioned_acceptance"] is False
    assert acceptance["episode_similarity_review_used_for_acceptance"] is False
    assert acceptance["seed_substitution_used"] is False
    assert acceptance["partial_resume_used"] is False


def test_episode03_attempt_history_preserves_failed_attempts_and_accepts_only_attempt03() -> None:
    record = load_episode03_freeze_record(REPO_ROOT)
    history = record["attempt_history"]
    assert history["frozen_initial_runtime_sha256"] == (
        "98a95b5ee631ac4a57648867103c25828bfa1b8af640871640cdf071e2f01a26"
    )
    attempts = history["attempts"]
    assert [a["attempt_number"] for a in attempts] == [1, 2, 3]
    assert attempts[0]["classification"] == "external_process_interruption"
    assert attempts[0]["raw_manifest_status"] == "running"
    assert attempts[0]["acceptance_role"] == "not_accepted"
    assert attempts[1]["classification"] == "producer_captured_technical_invalid"
    assert attempts[1]["raw_manifest_status"] == "TECHNICAL_INVALID"
    assert attempts[1]["error_type"] == "Phase09CError"
    assert attempts[1]["acceptance_role"] == "not_accepted"
    assert attempts[2]["classification"] == "formal_frozen_technical_pass"
    assert attempts[2]["raw_manifest_status"] == "FORMAL_FROZEN"
    assert attempts[2]["acceptance_role"] == "accepted"


def test_episode03_identity_and_outputs_are_frozen() -> None:
    record = load_episode03_freeze_record(REPO_ROOT)
    assert record["producer_identity"]["git_commit"] == "f3035ecd334074c52f3c48bd41afdf55bf10d964"
    assert record["execution"]["formal_world_ticks"] == 27
    assert record["execution"]["active_agent_pipeline_executions_completed"] == 193
    assert record["execution"]["failed_agent_pipeline_count"] == 0
    assert record["outputs"]["agent_world_db"]["sha256"] == (
        "da8a077875d0011239f0c713e5b2e3556901bc9a828793f05f08c69f1584cb31"
    )
    assert record["outputs"]["forum_db"]["sha256"] == (
        "42ab83af3aa2da27b4c29f9f9a8097f98f47e87e03bc3fd4f1a606c1dc248f0f"
    )


def test_episode03_record_hash_guard_rejects_modified_copy(tmp_path: Path) -> None:
    target = tmp_path / EPISODE03_RECORD_RELATIVE_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes((REPO_ROOT / EPISODE03_RECORD_RELATIVE_PATH).read_bytes())
    assert load_episode03_freeze_record(tmp_path)["episode_id"] == "marketlens-canonical-episode-v1-e03"
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        load_episode03_freeze_record(tmp_path)


def test_episode03_local_formal_evidence_absence_is_portable_not_failure(tmp_path: Path) -> None:
    record = load_episode03_freeze_record(REPO_ROOT)
    result = validate_local_evidence_if_present(tmp_path, record)
    assert result["local_formal_evidence_present"] is False
    assert result["local_agent_world_db_hash_match"] is None


def test_episode03_failed_attempt_history_absence_is_portable_not_failure(tmp_path: Path) -> None:
    record = load_episode03_freeze_record(REPO_ROOT)
    result = validate_attempt_history_if_present(tmp_path, record)
    assert result == {
        "local_failed_attempt_history_present": False,
        "attempt001_fingerprint_match": None,
        "attempt002_fingerprint_match": None,
    }


def test_episode03_partial_local_formal_evidence_is_rejected(tmp_path: Path) -> None:
    record = json.loads(json.dumps(load_episode03_freeze_record(REPO_ROOT)))
    agent_path = tmp_path / record["outputs"]["agent_world_db"]["path"]
    agent_path.parent.mkdir(parents=True)
    agent_path.write_bytes(b"partial")
    with pytest.raises(RuntimeError, match="Partial local Episode 03 formal evidence"):
        validate_local_evidence_if_present(tmp_path, record)


def test_episode03_complete_local_evidence_can_be_cross_checked(tmp_path: Path) -> None:
    record = json.loads(json.dumps(load_episode03_freeze_record(REPO_ROOT)))
    agent_path = tmp_path / record["outputs"]["agent_world_db"]["path"]
    forum_path = tmp_path / record["outputs"]["forum_db"]["path"]
    episode_manifest_path = tmp_path / record["source_manifests"]["episode_manifest"]
    attempt_manifest_path = tmp_path / record["source_manifests"]["attempt_manifest"]
    for path in (agent_path, forum_path, episode_manifest_path, attempt_manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    agent_path.write_bytes(b"agent3")
    forum_path.write_bytes(b"forum3")
    record["outputs"]["agent_world_db"]["sha256"] = _sha256(agent_path)
    record["outputs"]["forum_db"]["sha256"] = _sha256(forum_path)

    episode_manifest = {
        "status": "formal_frozen",
        "episode_id": record["episode_id"],
        "episode_slot": 3,
        "git": {"commit": record["producer_identity"]["git_commit"]},
        "execution_plan_sha256": record["producer_identity"]["phase13c_execution_plan_sha256"],
        "producer_contract_sha256": record["producer_identity"]["phase13d_producer_contract_sha256"],
        "world": {"formal_world_ticks": 27},
        "execution": {
            "active_agent_pipeline_executions_completed": 193,
            "failed_agent_pipeline_count": 0,
        },
        "validation": {
            "all_days_complete": True,
            "activation_plan_exact": True,
            "calendar_actions_exact": True,
            "state_chain_complete": True,
            "protected_sources_unchanged": True,
            "participant_price_coverage_complete": True,
            "forum_profile_source_cue_join_complete": True,
        },
        "outputs": {
            "agent_world_db": {"sha256": record["outputs"]["agent_world_db"]["sha256"]},
            "forum_db": {"sha256": record["outputs"]["forum_db"]["sha256"]},
        },
    }
    episode_manifest_path.write_text(json.dumps(episode_manifest), encoding="utf-8")

    attempt_manifest = {
        "status": "FORMAL_FROZEN",
        "episode_id": record["episode_id"],
        "attempt_number": 3,
        "git": {"commit": record["producer_identity"]["git_commit"]},
        "phase13c_execution_plan_sha256": record["producer_identity"]["phase13c_execution_plan_sha256"],
        "phase13d_producer_contract_sha256": record["producer_identity"]["phase13d_producer_contract_sha256"],
        "partial_resume_used": False,
        "seed_substitution_used": False,
        "outcome_review_used_for_acceptance": False,
        "episode_similarity_review_used_for_acceptance": False,
        "days_completed": 27,
        "active_agent_pipeline_executions_completed": 193,
        "formal_outputs": {
            "agent_world_db": {"sha256": record["outputs"]["agent_world_db"]["sha256"]},
            "forum_db": {"sha256": record["outputs"]["forum_db"]["sha256"]},
        },
    }
    attempt_manifest_path.write_text(json.dumps(attempt_manifest), encoding="utf-8")

    result = validate_local_evidence_if_present(tmp_path, record)
    assert result == {
        "local_formal_evidence_present": True,
        "local_agent_world_db_hash_match": True,
        "local_forum_db_hash_match": True,
        "episode_manifest_match": True,
        "attempt_manifest_match": True,
    }


def test_actual_failed_attempt_history_cross_checks_when_present() -> None:
    record = load_episode03_freeze_record(REPO_ROOT)
    result = validate_attempt_history_if_present(REPO_ROOT, record)
    if result["local_failed_attempt_history_present"]:
        assert result["attempt001_fingerprint_match"] is True
        assert result["attempt002_fingerprint_match"] is True


def test_top_level_episode03_validator_passes_on_tracked_record() -> None:
    result = validate_episode03_freeze_record(REPO_ROOT)
    assert result["status"] == "PASS"
    assert result["accepted_attempt_number"] == 3
    assert result["formal_world_ticks"] == 27
    assert result["active_agent_pipeline_executions_completed"] == 193
