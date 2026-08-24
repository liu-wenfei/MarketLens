#!/usr/bin/env python3
"""Zero-LLM preflight for the Phase 13C canonical episode-pool contract."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.episode.contract import (  # noqa: E402
    ACTIVATION_SEED,
    EPISODE_COUNT,
    EPISODE_IDS,
    EPISODE_POOL_ID,
    EXPECTED_AGENT_PIPELINE_EXECUTIONS,
    EXPECTED_EXECUTION_PLAN_SHA256,
    EXPECTED_POOL_AGENT_PIPELINE_EXECUTIONS,
    POPULATION_SEED,
    SELECTED_AGENT_IDS_SHA256,
    execution_plan_sha256,
    file_sha256,
    formal_assets_present,
    load_execution_plan,
    validate_base_protocol_compatibility,
    rebuild_execution_plan,
)

BANNER = (
    "NON-FORMAL / PHASE 13C CANONICAL EPISODE-POOL FREEZE CONTRACT PREFLIGHT / "
    "ZERO-LLM / NOT FORMAL EXPERIMENT EVIDENCE"
)


def main() -> int:
    print(BANNER)
    protected = [
        REPO_ROOT / "data/sys_1000.db",
        REPO_ROOT / "data/trading_days.csv",
        REPO_ROOT / "data/sorted_impact_news.pkl",
        REPO_ROOT / "marketlens/experiment/protocol_v1.json",
    ]
    before = {str(path.relative_to(REPO_ROOT)): file_sha256(path) for path in protected}
    frozen = load_execution_plan()
    from marketlens.experiment.protocol import load_protocol
    base_protocol = load_protocol(REPO_ROOT / "marketlens/experiment/protocol_v1.json")
    validate_base_protocol_compatibility(base_protocol, frozen)
    rebuilt = rebuild_execution_plan(REPO_ROOT)
    after = {str(path.relative_to(REPO_ROOT)): file_sha256(path) for path in protected}

    if rebuilt != frozen:
        raise RuntimeError("reconstructed formal execution plan differs from frozen plan")
    if before != after:
        raise RuntimeError("protected input changed during zero-LLM contract preflight")

    days = frozen["days"]
    generation = frozen["generation_policy"]
    acceptance = frozen["acceptance_policy"]
    summary = {
        "status": "PASS",
        "evidence_class": BANNER,
        "llm_api_calls": 0,
        "formal_experiment_evidence": False,
        "formal_execution_performed_by_this_preflight": False,
        "episode_pool_id": EPISODE_POOL_ID,
        "episode_count": EPISODE_COUNT,
        "episode_ids": list(EPISODE_IDS),
        "plan_version": frozen["plan_version"],
        "plan_status": frozen["status"],
        "protocol_version": frozen["protocol_version"],
        "base_protocol_compatibility": {
            "base_protocol_version": frozen["base_protocol_compatibility"]["base_protocol_version"],
            "base_protocol_file_mutated": False,
            "superseded_base_canonical_world_fields": frozen["base_protocol_compatibility"]["superseded_base_canonical_world_fields"],
            "effective_episode_pool_size": frozen["base_protocol_compatibility"]["effective_canonical_world_policy"]["predeclared_episode_pool_size"],
            "participant_assignment_mode": frozen["base_protocol_compatibility"]["effective_canonical_world_policy"]["participant_assignment_mode"],
            "participant_specific_world_generation": frozen["base_protocol_compatibility"]["effective_canonical_world_policy"]["participant_specific_world_generation"],
        },
        "execution_plan_sha256": execution_plan_sha256(frozen),
        "expected_execution_plan_sha256": EXPECTED_EXECUTION_PLAN_SHA256,
        "exact_plan_hash_frozen": execution_plan_sha256(frozen) == EXPECTED_EXECUTION_PLAN_SHA256,
        "population": {
            "size": frozen["population"]["size"],
            "selection_seed": POPULATION_SEED,
            "selected_agent_ids_sha256": SELECTED_AGENT_IDS_SHA256,
            "same_population_across_episodes": generation["same_population_across_episodes"],
        },
        "activation": {
            "seed": ACTIVATION_SEED,
            "same_activation_plan_across_episodes": generation["same_activation_plan_across_episodes"],
            "world_ticks_per_episode": len(days),
            "agent_pipeline_executions_per_episode": sum(row["n_active"] for row in days),
            "expected_agent_pipeline_executions_per_episode": EXPECTED_AGENT_PIPELINE_EXECUTIONS,
            "expected_agent_pipeline_executions_full_pool": EXPECTED_POOL_AGENT_PIPELINE_EXECUTIONS,
            "first_three_active_counts": [row["n_active"] for row in days[:3]],
            "zero_active_days_in_frozen_reference_plan": [
                row["agent_world_date"] for row in days if row["n_active"] == 0
            ],
        },
        "world": {
            "initialization_date": days[0]["agent_world_date"],
            "end_date": days[-1]["agent_world_date"],
            "formal_world_ticks_per_episode": len(days),
            "open_days_per_episode": sum(bool(row["market_open"]) for row in days),
            "closed_days_per_episode": sum(not bool(row["market_open"]) for row in days),
        },
        "participant_assignment": {
            "mode": "balanced_random_across_episode_pool",
            "episode_id_must_be_recorded_for_analysis": generation["episode_id_must_be_recorded_for_analysis"],
            "participant_specific_world_generation": generation["participant_specific_world_generation"],
        },
        "outcome_conditioned_acceptance_gates_present": any(
            acceptance[key] is not None
            for key in (
                "minimum_post_count_gate",
                "minimum_trade_count_gate",
                "price_direction_gate",
                "sentiment_gate",
                "misinformation_effect_gate",
                "minimum_cross_episode_divergence_gate",
                "episode_similarity_gate",
            )
        ),
        "outcome_based_episode_exclusion_allowed": generation["outcome_based_episode_exclusion_allowed"],
        "episode_similarity_based_rerun_allowed": generation["episode_similarity_based_rerun_allowed"],
        "technically_valid_completed_episode_must_be_retained": generation[
            "technically_valid_completed_episode_must_be_retained"
        ],
        "protected_inputs_unchanged": before == after,
        "protected_input_sha256": after,
        "formal_assets_present": formal_assets_present(REPO_ROOT),
        "canonical_episode_pool_formal_assets_bound": False,
        "formal_agent_translation_assets_bound": False,
        "participant_data_used": False,
        "controlled_stimulus_injected_into_agent_world": False,
        "note": (
            "Contract only. No paid canonical episode has been generated. The future formal producer must "
            "reuse inherited TwinMarket execution to generate exactly three technically valid episode slots "
            "under the same frozen N30 population, activation plan, and Phase 10 v1.1 base protocol plus the explicit Phase 13C episode-pool cardinality/assignment extension. Natural episode "
            "outcomes or cross-episode similarity cannot be used to rerun, exclude, or replace a technically "
            "valid episode. Participants are later assigned across the frozen pool in a balanced random manner."
        ),
    }
    if summary["activation"]["agent_pipeline_executions_per_episode"] != EXPECTED_AGENT_PIPELINE_EXECUTIONS:
        raise RuntimeError("frozen plan Agent pipeline total drifted")
    if summary["activation"]["expected_agent_pipeline_executions_full_pool"] != 579:
        raise RuntimeError("predeclared three-episode pipeline total drifted")
    if (
        summary["world"]["formal_world_ticks_per_episode"] != 27
        or summary["world"]["open_days_per_episode"] != 17
        or summary["world"]["closed_days_per_episode"] != 10
    ):
        raise RuntimeError("frozen 27-tick calendar summary drifted")
    if summary["outcome_conditioned_acceptance_gates_present"]:
        raise RuntimeError("outcome-conditioned formal acceptance gate is present")
    if summary["outcome_based_episode_exclusion_allowed"] or summary["episode_similarity_based_rerun_allowed"]:
        raise RuntimeError("episode selection/rerun policy became outcome-conditioned")

    artifact_root = REPO_ROOT / "artifacts/preflight/phase13"
    artifact_root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_phase13c_canonical_episode_pool_contract"
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    target = run_dir / "summary.json"
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Artifact: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
