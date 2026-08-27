from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from marketlens.episode.freeze_record import (
    validate_episode01_freeze_record,
    validate_episode02_freeze_record,
    validate_episode03_freeze_record,
)
from marketlens.episode.pool_freeze_record import (
    EXPECTED_POOL_MANIFEST_SHA256,
    EXPECTED_POOL_RECORD_SHA256,
    POOL_RECORD_RELATIVE_PATH,
    load_pool_freeze_record,
    validate_local_pool_evidence_if_present,
    validate_pool_freeze_record,
    validate_pool_record_semantics,
    validate_tracked_episode_records,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_tracked_pool_record_has_exact_frozen_hash() -> None:
    path = REPO_ROOT / POOL_RECORD_RELATIVE_PATH
    assert path.is_file()
    assert _sha256(path) == EXPECTED_POOL_RECORD_SHA256


def test_tracked_pool_record_semantics_pass() -> None:
    record = load_pool_freeze_record(REPO_ROOT)
    validate_pool_record_semantics(record)


def test_pool_identity_and_source_manifest_are_frozen() -> None:
    record = load_pool_freeze_record(REPO_ROOT)
    assert record["episode_pool_id"] == "marketlens-canonical-episode-pool-v1"
    assert record["formal_pool_status"] == "formal_frozen"
    assert record["source_pool_manifest"]["sha256"] == EXPECTED_POOL_MANIFEST_SHA256


def test_pool_finalization_is_zero_llm_and_outcome_blind() -> None:
    record = load_pool_freeze_record(REPO_ROOT)
    context = record["finalization_context"]
    assignment = record["participant_assignment"]
    assert context["pool_finalization_is_zero_llm"] is True
    assert context["llm_api_calls"] == 0
    assert context["outcome_review_used"] is False
    assert context["episode_similarity_review_used"] is False
    assert assignment["mode"] == "balanced_random_across_episode_pool"
    assert assignment["assignment_uses_episode_outcomes"] is False


def test_pool_tracks_exact_episode_records_and_accepted_attempts() -> None:
    record = load_pool_freeze_record(REPO_ROOT)
    rows = record["episode_records"]
    assert [row["accepted_attempt_number"] for row in rows] == [1, 1, 3]
    assert [row["active_agent_pipeline_executions_completed"] for row in rows] == [193, 193, 193]


def test_pool_aggregate_uses_pipeline_executions_not_api_call_claim() -> None:
    record = load_pool_freeze_record(REPO_ROOT)
    aggregate = record["aggregate_execution"]
    assert aggregate["aggregate_agent_pipeline_executions"] == 579
    assert aggregate["exact_backend_api_call_count_claimed"] is False


def test_existing_episode_freeze_records_remain_valid() -> None:
    assert validate_episode01_freeze_record(REPO_ROOT)["status"] == "PASS"
    assert validate_episode02_freeze_record(REPO_ROOT)["status"] == "PASS"
    assert validate_episode03_freeze_record(REPO_ROOT)["status"] == "PASS"


def test_pool_cross_checks_all_tracked_episode_records() -> None:
    result = validate_tracked_episode_records(REPO_ROOT)
    assert [result[e]["accepted_attempt_number"] for e in result] == [1, 1, 3]


def test_pool_record_hash_guard_rejects_modified_copy(tmp_path: Path) -> None:
    target = tmp_path / POOL_RECORD_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((REPO_ROOT / POOL_RECORD_RELATIVE_PATH).read_bytes())
    assert load_pool_freeze_record(tmp_path)["episode_pool_id"] == "marketlens-canonical-episode-pool-v1"
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        load_pool_freeze_record(tmp_path)


def test_local_pool_manifest_absence_is_portable_not_failure(tmp_path: Path) -> None:
    record = load_pool_freeze_record(REPO_ROOT)
    result = validate_local_pool_evidence_if_present(tmp_path, record)
    assert result == {
        "local_formal_pool_manifest_present": False,
        "local_pool_manifest_hash_match": None,
        "local_pool_contract_validation": None,
        "local_pool_finalization_fields_match": None,
    }


def test_pool_semantics_reject_finalization_drift() -> None:
    record = json.loads(json.dumps(load_pool_freeze_record(REPO_ROOT)))
    record["finalization_context"]["llm_api_calls"] = 1
    with pytest.raises(RuntimeError, match="llm_api_calls"):
        validate_pool_record_semantics(record)


def test_pool_semantics_reject_outcome_assignment() -> None:
    record = json.loads(json.dumps(load_pool_freeze_record(REPO_ROOT)))
    record["participant_assignment"]["assignment_uses_episode_outcomes"] = True
    with pytest.raises(RuntimeError, match="assignment_uses_episode_outcomes"):
        validate_pool_record_semantics(record)


def test_top_level_pool_validator_passes_on_tracked_record() -> None:
    result = validate_pool_freeze_record(REPO_ROOT)
    assert result["status"] == "PASS"
    assert result["episode_count"] == 3
    assert result["aggregate_agent_pipeline_executions"] == 579
    assert result["exact_backend_api_call_count_claimed"] is False
