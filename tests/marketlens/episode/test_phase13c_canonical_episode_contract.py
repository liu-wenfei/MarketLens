from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from marketlens.episode.contract import (
    ACTIVATION_SEED,
    EPISODE_ID,
    EXPECTED_AGENT_PIPELINE_EXECUTIONS,
    EXPECTED_EXECUTION_PLAN_SHA256,
    POPULATION_SEED,
    SELECTED_AGENT_IDS_SHA256,
    CanonicalEpisodeContractError,
    execution_plan_sha256,
    file_sha256,
    formal_assets_present,
    load_execution_plan,
    rebuild_execution_plan,
    validate_execution_plan,
    validate_formal_episode_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def _valid_manifest(tmp_path: Path) -> tuple[dict, Path]:
    root = tmp_path
    data_dir = root / "data/marketlens/canonical_episode/v1"
    data_dir.mkdir(parents=True)
    agent = data_dir / "agent_world.db"
    forum = data_dir / "forum.db"
    agent.write_bytes(b"canonical-agent-world")
    forum.write_bytes(b"canonical-forum")

    plan = load_execution_plan()
    daily = [
        {
            "step": row["step"],
            "agent_world_date": row["agent_world_date"],
            "agent_world_db_sha256": "a" * 64,
            "forum_db_sha256": "b" * 64,
        }
        for row in plan["days"]
    ]
    manifest = {
        "manifest_schema_version": "marketlens-canonical-episode-manifest/1.0",
        "episode_id": EPISODE_ID,
        "status": "formal_frozen",
        "protocol_version": "1.1",
        "execution_plan_sha256": EXPECTED_EXECUTION_PLAN_SHA256,
        "population": {
            "size": 30,
            "selection_seed": POPULATION_SEED,
            "selected_agent_ids_sha256": SELECTED_AGENT_IDS_SHA256,
        },
        "activation": {"seed": ACTIVATION_SEED},
        "world": {
            "initialization_date": "2023-06-15",
            "end_date": "2023-07-11",
            "formal_world_ticks": 27,
        },
        "attempt": {
            "seed_substitution_used": False,
            "partial_resume_used": False,
            "outcome_review_used_for_acceptance": False,
        },
        "execution": {
            "active_agent_pipeline_executions_expected": EXPECTED_AGENT_PIPELINE_EXECUTIONS,
            "active_agent_pipeline_executions_completed": EXPECTED_AGENT_PIPELINE_EXECUTIONS,
            "failed_agent_pipeline_count": 0,
            "participant_data_used": False,
            "controlled_stimulus_injected_into_agent_world": False,
            "custom_matching_price_forum_belief_logic_used": False,
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
        "daily_state_chain": daily,
        "outputs": {
            "agent_world_db": {
                "path": "data/marketlens/canonical_episode/v1/agent_world.db",
                "sha256": file_sha256(agent),
            },
            "forum_db": {
                "path": "data/marketlens/canonical_episode/v1/forum.db",
                "sha256": file_sha256(forum),
            },
        },
    }
    return manifest, root


def test_frozen_execution_plan_has_exact_identity_and_hash():
    plan = load_execution_plan()
    assert plan["episode_id"] == EPISODE_ID
    assert plan["protocol_version"] == "1.1"
    assert plan["population"]["size"] == 30
    assert plan["population"]["selection_seed"] == POPULATION_SEED
    assert plan["population"]["selected_agent_ids_sha256"] == SELECTED_AGENT_IDS_SHA256
    assert plan["activation"]["seed"] == ACTIVATION_SEED
    assert execution_plan_sha256(plan) == EXPECTED_EXECUTION_PLAN_SHA256


def test_frozen_plan_is_exact_27_calendar_ticks_and_193_agent_pipelines():
    plan = load_execution_plan()
    assert len(plan["days"]) == 27
    assert plan["days"][0]["agent_world_date"] == "2023-06-15"
    assert plan["days"][-1]["agent_world_date"] == "2023-07-11"
    assert sum(row["n_active"] for row in plan["days"]) == 193
    assert sum(row["market_open"] for row in plan["days"]) == 17
    assert sum(not row["market_open"] for row in plan["days"]) == 10


def test_first_three_days_match_the_once_only_n30_real_backend_reference():
    plan = load_execution_plan()
    assert [row["n_active"] for row in plan["days"][:3]] == [10, 7, 3]
    assert [row["market_open"] for row in plan["days"][:3]] == [True, True, False]


def test_generation_policy_forbids_seed_fishing_partial_resume_and_outcome_rerun():
    plan = load_execution_plan()
    policy = plan["generation_policy"]
    assert policy["partial_resume_allowed"] is False
    assert policy["seed_substitution_allowed"] is False
    assert policy["outcome_based_rerun_allowed"] is False
    assert policy["failed_attempt_evidence_must_be_retained"] is True


def test_acceptance_policy_has_no_post_trade_price_sentiment_or_effect_gate():
    policy = load_execution_plan()["acceptance_policy"]
    assert policy["minimum_post_count_gate"] is None
    assert policy["minimum_trade_count_gate"] is None
    assert policy["price_direction_gate"] is None
    assert policy["sentiment_gate"] is None
    assert policy["misinformation_effect_gate"] is None


def test_rebuilt_plan_from_frozen_phase3_phase4_phase10_inputs_matches_exactly():
    frozen = load_execution_plan()
    rebuilt = rebuild_execution_plan(REPO_ROOT)
    assert rebuilt == frozen
    assert execution_plan_sha256(rebuilt) == EXPECTED_EXECUTION_PLAN_SHA256


def test_plan_hash_drift_is_fail_closed():
    plan = copy.deepcopy(load_execution_plan())
    plan["days"][4]["active_agent_ids"] = []
    plan["days"][4]["n_active"] = 0
    with pytest.raises(CanonicalEpisodeContractError, match="SHA-256 drifted"):
        validate_execution_plan(plan)


def test_formal_manifest_contract_accepts_only_hash_pinned_db_pair(tmp_path: Path):
    manifest, root = _valid_manifest(tmp_path)
    validate_formal_episode_manifest(manifest, repo_root=root, verify_files=True)

    agent = root / "data/marketlens/canonical_episode/v1/agent_world.db"
    agent.write_bytes(b"tampered")
    with pytest.raises(CanonicalEpisodeContractError, match="Agent-world DB|output SHA-256 mismatch"):
        validate_formal_episode_manifest(manifest, repo_root=root, verify_files=True)


def test_formal_manifest_rejects_outcome_conditioning_and_partial_resume(tmp_path: Path):
    manifest, root = _valid_manifest(tmp_path)
    bad = copy.deepcopy(manifest)
    bad["attempt"]["outcome_review_used_for_acceptance"] = True
    with pytest.raises(CanonicalEpisodeContractError, match="outcome-conditioned"):
        validate_formal_episode_manifest(bad, repo_root=root, verify_files=False)

    bad = copy.deepcopy(manifest)
    bad["attempt"]["partial_resume_used"] = True
    with pytest.raises(CanonicalEpisodeContractError, match="partial resume"):
        validate_formal_episode_manifest(bad, repo_root=root, verify_files=False)


def test_formal_asset_presence_probe_is_boolean_and_does_not_bind_assets():
    assert isinstance(formal_assets_present(REPO_ROOT), bool)
