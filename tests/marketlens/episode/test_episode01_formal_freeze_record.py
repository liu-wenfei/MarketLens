from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from marketlens.episode.freeze_record import (
    EPISODE01_RECORD_RELATIVE_PATH,
    EXPECTED_EPISODE01_RECORD_SHA256,
    load_episode01_freeze_record,
    validate_episode01_freeze_record,
    validate_local_evidence_if_present,
    validate_record_semantics,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_tracked_episode01_record_has_exact_frozen_hash() -> None:
    record_path = REPO_ROOT / EPISODE01_RECORD_RELATIVE_PATH
    assert record_path.is_file()
    assert _sha256(record_path) == EXPECTED_EPISODE01_RECORD_SHA256


def test_tracked_episode01_record_semantics_pass() -> None:
    record = load_episode01_freeze_record(REPO_ROOT)
    validate_record_semantics(record)


def test_episode01_acceptance_is_technical_not_outcome_conditioned() -> None:
    record = load_episode01_freeze_record(REPO_ROOT)
    acceptance = record["acceptance"]
    assert acceptance["status"] == "formal_frozen_technically_valid"
    assert acceptance["acceptance_basis"] == "predeclared_technical_gates_only"
    assert acceptance["outcome_conditioned_acceptance"] is False
    assert acceptance["episode_similarity_review_used_for_acceptance"] is False
    assert acceptance["seed_substitution_used"] is False
    assert acceptance["partial_resume_used"] is False


def test_episode01_identity_and_outputs_are_frozen() -> None:
    record = load_episode01_freeze_record(REPO_ROOT)
    assert record["producer_identity"]["git_commit"] == "96c2a0b33587293b76eee9ba01978ef75d902abb"
    assert record["execution"]["formal_world_ticks"] == 27
    assert record["execution"]["active_agent_pipeline_executions_completed"] == 193
    assert record["execution"]["failed_agent_pipeline_count"] == 0
    assert record["outputs"]["agent_world_db"]["sha256"] == (
        "f9999c8e6774eb5dd2ffade5f5503ac0f863aae9e458636e92fb427198ce1741"
    )
    assert record["outputs"]["forum_db"]["sha256"] == (
        "3be8a5682049e011b5f2c74d40e9bc42e265364f3bb30f82f85cb4d54d064dca"
    )


def test_record_hash_guard_rejects_modified_copy(tmp_path: Path) -> None:
    target = tmp_path / EPISODE01_RECORD_RELATIVE_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes((REPO_ROOT / EPISODE01_RECORD_RELATIVE_PATH).read_bytes())
    assert load_episode01_freeze_record(tmp_path)["episode_id"] == "marketlens-canonical-episode-v1-e01"
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        load_episode01_freeze_record(tmp_path)


def test_local_evidence_absence_is_portable_not_failure(tmp_path: Path) -> None:
    record = load_episode01_freeze_record(REPO_ROOT)
    result = validate_local_evidence_if_present(tmp_path, record)
    assert result["local_formal_evidence_present"] is False
    assert result["local_agent_world_db_hash_match"] is None


def test_partial_local_evidence_is_rejected(tmp_path: Path) -> None:
    record = json.loads(json.dumps(load_episode01_freeze_record(REPO_ROOT)))
    agent_path = tmp_path / record["outputs"]["agent_world_db"]["path"]
    agent_path.parent.mkdir(parents=True)
    agent_path.write_bytes(b"partial")
    with pytest.raises(RuntimeError, match="Partial local Episode 01 formal evidence"):
        validate_local_evidence_if_present(tmp_path, record)


def test_complete_local_evidence_can_be_cross_checked(tmp_path: Path) -> None:
    record = json.loads(json.dumps(load_episode01_freeze_record(REPO_ROOT)))
    agent_path = tmp_path / record["outputs"]["agent_world_db"]["path"]
    forum_path = tmp_path / record["outputs"]["forum_db"]["path"]
    episode_manifest_path = tmp_path / record["source_manifests"]["episode_manifest"]
    attempt_manifest_path = tmp_path / record["source_manifests"]["attempt_manifest"]
    for path in (agent_path, forum_path, episode_manifest_path, attempt_manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    agent_path.write_bytes(b"agent")
    forum_path.write_bytes(b"forum")
    record["outputs"]["agent_world_db"]["sha256"] = _sha256(agent_path)
    record["outputs"]["forum_db"]["sha256"] = _sha256(forum_path)

    episode_manifest = {
        "status": "formal_frozen",
        "episode_id": record["episode_id"],
        "execution_plan_sha256": record["producer_identity"]["phase13c_execution_plan_sha256"],
        "producer_contract_sha256": record["producer_identity"]["phase13d_producer_contract_sha256"],
        "execution": {
            "active_agent_pipeline_executions_completed": 193,
            "failed_agent_pipeline_count": 0,
        },
        "validation": {"state_chain_complete": True},
        "outputs": {
            "agent_world_db": {"sha256": record["outputs"]["agent_world_db"]["sha256"]},
            "forum_db": {"sha256": record["outputs"]["forum_db"]["sha256"]},
        },
    }
    episode_manifest_path.write_text(json.dumps(episode_manifest), encoding="utf-8")

    attempt_manifest = {
        "status": "FORMAL_FROZEN",
        "episode_id": record["episode_id"],
        "attempt_number": 1,
        "phase13c_execution_plan_sha256": record["producer_identity"]["phase13c_execution_plan_sha256"],
        "phase13d_producer_contract_sha256": record["producer_identity"]["phase13d_producer_contract_sha256"],
        "partial_resume_used": False,
        "seed_substitution_used": False,
        "outcome_review_used_for_acceptance": False,
        "episode_similarity_review_used_for_acceptance": False,
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


def test_top_level_validator_passes_on_tracked_record() -> None:
    result = validate_episode01_freeze_record(REPO_ROOT)
    assert result["status"] == "PASS"
    assert result["accepted_attempt_number"] == 1
    assert result["formal_world_ticks"] == 27
    assert result["active_agent_pipeline_executions_completed"] == 193
