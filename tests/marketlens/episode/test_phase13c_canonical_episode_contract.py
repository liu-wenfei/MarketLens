from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from marketlens.episode.contract import (
    ACTIVATION_SEED,
    EPISODE_COUNT,
    EPISODE_IDS,
    EPISODE_POOL_ID,
    EXPECTED_AGENT_PIPELINE_EXECUTIONS,
    EXPECTED_EXECUTION_PLAN_SHA256,
    EXPECTED_POOL_AGENT_PIPELINE_EXECUTIONS,
    POPULATION_SEED,
    SELECTED_AGENT_IDS_SHA256,
    CanonicalEpisodeContractError,
    execution_plan_sha256,
    file_sha256,
    formal_assets_present,
    formal_episode_paths,
    load_execution_plan,
    rebuild_execution_plan,
    validate_base_protocol_compatibility,
    validate_execution_plan,
    validate_formal_episode_manifest,
    validate_formal_episode_pool_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def _valid_manifest(tmp_path: Path, episode_id: str = EPISODE_IDS[0]) -> tuple[dict, Path]:
    root = tmp_path
    paths = formal_episode_paths(episode_id)
    data_dir = root / paths["root"]
    data_dir.mkdir(parents=True, exist_ok=True)
    agent = root / paths["agent_world_db"]
    forum = root / paths["forum_db"]
    agent.write_bytes(f"canonical-agent-world-{episode_id}".encode())
    forum.write_bytes(f"canonical-forum-{episode_id}".encode())

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
        "manifest_schema_version": "marketlens-canonical-episode-manifest/1.1",
        "episode_pool_id": EPISODE_POOL_ID,
        "episode_id": episode_id,
        "episode_slot": EPISODE_IDS.index(episode_id) + 1,
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
            "episode_similarity_review_used_for_acceptance": False,
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
            "agent_world_db": {"path": paths["agent_world_db"], "sha256": file_sha256(agent)},
            "forum_db": {"path": paths["forum_db"], "sha256": file_sha256(forum)},
        },
    }
    (root / paths["episode_manifest"]).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest, root


def _valid_pool_manifest(tmp_path: Path) -> tuple[dict, Path]:
    for episode_id in EPISODE_IDS:
        _valid_manifest(tmp_path, episode_id)
    manifest = {
        "manifest_schema_version": "marketlens-canonical-episode-pool-manifest/1.0",
        "episode_pool_id": EPISODE_POOL_ID,
        "status": "formal_frozen",
        "execution_plan_sha256": EXPECTED_EXECUTION_PLAN_SHA256,
        "episode_count": EPISODE_COUNT,
        "episode_ids": list(EPISODE_IDS),
        "participant_assignment": {
            "mode": "balanced_random_across_episode_pool",
            "episode_id_recorded_for_analysis": True,
            "assignment_uses_episode_outcomes": False,
        },
        "episodes": [
            {
                "episode_id": episode_id,
                "episode_manifest_path": formal_episode_paths(episode_id)["episode_manifest"],
            }
            for episode_id in EPISODE_IDS
        ],
    }
    pool_path = tmp_path / "data/marketlens/canonical_episode/v1/pool_manifest.json"
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    pool_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest, tmp_path


def test_frozen_execution_plan_has_exact_pool_identity_and_hash():
    plan = load_execution_plan()
    assert plan["episode_pool"]["pool_id"] == EPISODE_POOL_ID
    assert plan["episode_pool"]["episode_count"] == 3
    assert tuple(plan["episode_pool"]["episode_ids"]) == EPISODE_IDS
    assert plan["protocol_version"] == "1.1"
    assert plan["plan_version"] == "1.2"
    assert plan["population"]["size"] == 30
    assert plan["population"]["selection_seed"] == POPULATION_SEED
    assert plan["population"]["selected_agent_ids_sha256"] == SELECTED_AGENT_IDS_SHA256
    assert plan["activation"]["seed"] == ACTIVATION_SEED
    assert execution_plan_sha256(plan) == EXPECTED_EXECUTION_PLAN_SHA256


def test_phase13c_explicitly_supersedes_only_phase10_single_world_cardinality_semantics():
    from marketlens.experiment.protocol import load_protocol

    plan = load_execution_plan()
    protocol = load_protocol(REPO_ROOT / "marketlens/experiment/protocol_v1.json")
    validate_base_protocol_compatibility(protocol, plan)
    compat = plan["base_protocol_compatibility"]
    assert compat["base_protocol_version"] == "1.1"
    assert compat["superseded_base_canonical_world_fields"] == [
        "generated_once",
        "shared_across_participants",
    ]
    effective = compat["effective_canonical_world_policy"]
    assert effective["predeclared_episode_pool_size"] == 3
    assert effective["each_episode_slot_generated_once_if_technically_valid"] is True
    assert effective["each_frozen_episode_shared_across_multiple_assigned_participants"] is True
    assert effective["participant_specific_world_generation"] is False


def test_each_episode_uses_exact_same_27_tick_plan_and_pool_total_is_predeclared():
    plan = load_execution_plan()
    assert len(plan["days"]) == 27
    assert plan["days"][0]["agent_world_date"] == "2023-06-15"
    assert plan["days"][-1]["agent_world_date"] == "2023-07-11"
    assert sum(row["n_active"] for row in plan["days"]) == 193
    assert EXPECTED_POOL_AGENT_PIPELINE_EXECUTIONS == 579
    assert sum(row["market_open"] for row in plan["days"]) == 17
    assert sum(not row["market_open"] for row in plan["days"]) == 10


def test_first_three_days_match_the_once_only_n30_real_backend_reference():
    plan = load_execution_plan()
    assert [row["n_active"] for row in plan["days"][:3]] == [10, 7, 3]
    assert [row["market_open"] for row in plan["days"][:3]] == [True, True, False]


def test_generation_policy_is_fixed_three_episode_balanced_and_outcome_blind():
    policy = load_execution_plan()["generation_policy"]
    assert policy["fixed_episode_pool_size"] == 3
    assert policy["same_population_across_episodes"] is True
    assert policy["same_activation_plan_across_episodes"] is True
    assert policy["balanced_random_assignment_across_episode_pool"] is True
    assert policy["episode_id_must_be_recorded_for_analysis"] is True
    assert policy["participant_specific_world_generation"] is False
    assert policy["partial_resume_allowed"] is False
    assert policy["seed_substitution_allowed"] is False
    assert policy["outcome_based_rerun_allowed"] is False
    assert policy["outcome_based_episode_exclusion_allowed"] is False
    assert policy["episode_similarity_based_rerun_allowed"] is False
    assert policy["failed_attempt_evidence_must_be_retained"] is True
    assert policy["technically_valid_completed_episode_must_be_retained"] is True


def test_acceptance_policy_has_no_outcome_or_cross_episode_diversity_gate():
    policy = load_execution_plan()["acceptance_policy"]
    assert policy["minimum_post_count_gate"] is None
    assert policy["minimum_trade_count_gate"] is None
    assert policy["price_direction_gate"] is None
    assert policy["sentiment_gate"] is None
    assert policy["misinformation_effect_gate"] is None
    assert policy["minimum_cross_episode_divergence_gate"] is None
    assert policy["episode_similarity_gate"] is None


def test_rebuilt_plan_from_frozen_phase3_phase4_phase10_inputs_matches_exactly():
    frozen = load_execution_plan()
    rebuilt = rebuild_execution_plan(REPO_ROOT)
    assert rebuilt == frozen
    assert execution_plan_sha256(rebuilt) == EXPECTED_EXECUTION_PLAN_SHA256


def test_plan_hash_drift_is_fail_closed():
    plan = copy.deepcopy(load_execution_plan())
    plan["episode_pool"]["episode_count"] = 4
    with pytest.raises(CanonicalEpisodeContractError, match="SHA-256 drifted"):
        validate_execution_plan(plan)


def test_formal_episode_manifest_accepts_only_allowed_slot_and_hash_pinned_db_pair(tmp_path: Path):
    manifest, root = _valid_manifest(tmp_path, EPISODE_IDS[1])
    validate_formal_episode_manifest(manifest, repo_root=root, verify_files=True)

    agent = root / formal_episode_paths(EPISODE_IDS[1])["agent_world_db"]
    agent.write_bytes(b"tampered")
    with pytest.raises(CanonicalEpisodeContractError, match="Agent-world DB|output SHA-256 mismatch"):
        validate_formal_episode_manifest(manifest, repo_root=root, verify_files=True)


def test_formal_episode_manifest_rejects_outcome_similarity_conditioning_and_partial_resume(tmp_path: Path):
    manifest, root = _valid_manifest(tmp_path)
    bad = copy.deepcopy(manifest)
    bad["attempt"]["outcome_review_used_for_acceptance"] = True
    with pytest.raises(CanonicalEpisodeContractError, match="outcome-conditioned"):
        validate_formal_episode_manifest(bad, repo_root=root, verify_files=False)

    bad = copy.deepcopy(manifest)
    bad["attempt"]["episode_similarity_review_used_for_acceptance"] = True
    with pytest.raises(CanonicalEpisodeContractError, match="similarity-conditioned"):
        validate_formal_episode_manifest(bad, repo_root=root, verify_files=False)

    bad = copy.deepcopy(manifest)
    bad["attempt"]["partial_resume_used"] = True
    with pytest.raises(CanonicalEpisodeContractError, match="partial resume"):
        validate_formal_episode_manifest(bad, repo_root=root, verify_files=False)


def test_formal_episode_manifest_rejects_unregistered_episode_id(tmp_path: Path):
    manifest, root = _valid_manifest(tmp_path)
    manifest["episode_id"] = "marketlens-canonical-episode-v1-e99"
    with pytest.raises(CanonicalEpisodeContractError, match="identity/status"):
        validate_formal_episode_manifest(manifest, repo_root=root, verify_files=False)


def test_formal_pool_manifest_requires_exact_three_episode_pool_and_balanced_outcome_blind_assignment(tmp_path: Path):
    manifest, root = _valid_pool_manifest(tmp_path)
    validate_formal_episode_pool_manifest(manifest, repo_root=root, verify_files=True)

    bad = copy.deepcopy(manifest)
    bad["participant_assignment"]["assignment_uses_episode_outcomes"] = True
    with pytest.raises(CanonicalEpisodeContractError, match="outcome-blind"):
        validate_formal_episode_pool_manifest(bad, repo_root=root, verify_files=False)


def test_formal_asset_presence_probe_is_boolean_and_does_not_bind_assets():
    assert isinstance(formal_assets_present(REPO_ROOT), bool)
