#!/usr/bin/env python3
"""Zero-LLM preflight for the Phase 13C canonical-episode freeze contract."""
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
    EPISODE_ID,
    EXPECTED_AGENT_PIPELINE_EXECUTIONS,
    EXPECTED_EXECUTION_PLAN_SHA256,
    POPULATION_SEED,
    SELECTED_AGENT_IDS_SHA256,
    execution_plan_sha256,
    file_sha256,
    formal_assets_present,
    load_execution_plan,
    rebuild_execution_plan,
)

BANNER = (
    "NON-FORMAL / PHASE 13C CANONICAL EPISODE FREEZE CONTRACT PREFLIGHT / "
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
    rebuilt = rebuild_execution_plan(REPO_ROOT)
    after = {str(path.relative_to(REPO_ROOT)): file_sha256(path) for path in protected}

    if rebuilt != frozen:
        raise RuntimeError("reconstructed formal execution plan differs from frozen plan")
    if before != after:
        raise RuntimeError("protected input changed during zero-LLM contract preflight")

    days = frozen["days"]
    summary = {
        "status": "PASS",
        "evidence_class": BANNER,
        "llm_api_calls": 0,
        "formal_experiment_evidence": False,
        "formal_execution_performed_by_this_preflight": False,
        "episode_id": EPISODE_ID,
        "plan_version": frozen["plan_version"],
        "plan_status": frozen["status"],
        "protocol_version": frozen["protocol_version"],
        "execution_plan_sha256": execution_plan_sha256(frozen),
        "expected_execution_plan_sha256": EXPECTED_EXECUTION_PLAN_SHA256,
        "exact_plan_hash_frozen": execution_plan_sha256(frozen) == EXPECTED_EXECUTION_PLAN_SHA256,
        "population": {
            "size": frozen["population"]["size"],
            "selection_seed": POPULATION_SEED,
            "selected_agent_ids_sha256": SELECTED_AGENT_IDS_SHA256,
        },
        "activation": {
            "seed": ACTIVATION_SEED,
            "world_ticks": len(days),
            "active_agent_pipeline_executions": sum(row["n_active"] for row in days),
            "expected_agent_pipeline_executions": EXPECTED_AGENT_PIPELINE_EXECUTIONS,
            "first_three_active_counts": [row["n_active"] for row in days[:3]],
            "zero_active_days_in_frozen_reference_plan": [
                row["agent_world_date"] for row in days if row["n_active"] == 0
            ],
        },
        "world": {
            "initialization_date": days[0]["agent_world_date"],
            "end_date": days[-1]["agent_world_date"],
            "formal_world_ticks": len(days),
            "open_days": sum(bool(row["market_open"]) for row in days),
            "closed_days": sum(not bool(row["market_open"]) for row in days),
        },
        "generation_policy": frozen["generation_policy"],
        "outcome_conditioned_acceptance_gates_present": any(
            frozen["acceptance_policy"][key] is not None
            for key in (
                "minimum_post_count_gate",
                "minimum_trade_count_gate",
                "price_direction_gate",
                "sentiment_gate",
                "misinformation_effect_gate",
            )
        ),
        "protected_inputs_unchanged": before == after,
        "protected_input_sha256": after,
        "formal_assets_present": formal_assets_present(REPO_ROOT),
        "canonical_episode_formal_assets_bound": False,
        "formal_agent_translation_assets_bound": False,
        "participant_data_used": False,
        "controlled_stimulus_injected_into_agent_world": False,
        "note": (
            "Contract only. No paid canonical episode has been generated. The future formal producer "
            "must reuse inherited TwinMarket execution, create exactly one valid 27-tick episode under "
            "this frozen plan, and freeze the final Agent-world/forum DB pair before translation."
        ),
    }
    if summary["activation"]["active_agent_pipeline_executions"] != EXPECTED_AGENT_PIPELINE_EXECUTIONS:
        raise RuntimeError("frozen plan Agent pipeline total drifted")
    if summary["world"]["formal_world_ticks"] != 27 or summary["world"]["open_days"] != 17 or summary["world"]["closed_days"] != 10:
        raise RuntimeError("frozen 27-tick calendar summary drifted")
    if summary["outcome_conditioned_acceptance_gates_present"]:
        raise RuntimeError("outcome-conditioned formal acceptance gate is present")

    artifact_root = REPO_ROOT / "artifacts/preflight/phase13"
    artifact_root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_phase13c_canonical_episode_contract"
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    target = run_dir / "summary.json"
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Artifact: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
