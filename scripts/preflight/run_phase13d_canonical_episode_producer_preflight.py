#!/usr/bin/env python3
"""Zero-LLM preflight for the Phase 13D formal episode producer contract."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.episode.producer import (  # noqa: E402
    PRODUCER_CONTRACT_SHA256,
    dry_run_summary,
    load_producer_contract,
)

BANNER = (
    "NON-FORMAL / PHASE 13D FORMAL CANONICAL EPISODE PRODUCER CONTRACT PREFLIGHT / "
    "ZERO-LLM / NOT FORMAL EXPERIMENT EVIDENCE"
)


def main() -> int:
    print(BANNER)
    contract = load_producer_contract()
    summary = dry_run_summary(repo_root=REPO_ROOT)
    controls = contract["execution_controls"]
    acceptance = contract["technical_acceptance"]
    compact = {
        "status": "PASS",
        "evidence_class": BANNER,
        "llm_api_calls": 0,
        "formal_experiment_evidence": False,
        "formal_execution_performed_by_this_preflight": False,
        "phase13d_contract_status": contract["status"],
        "phase13d_contract_version": contract["contract_version"],
        "producer_contract_sha256": PRODUCER_CONTRACT_SHA256,
        "phase13c_execution_plan_sha256": summary["phase13c_execution_plan_sha256"],
        "episode_pool_id": summary["episode_pool_id"],
        "episode_ids": summary["episode_ids"],
        "default_mode": controls["default_mode"],
        "full_pool_execute_command_allowed": controls["full_pool_execute_command_allowed"],
        "one_explicit_episode_slot_per_execute_command": controls[
            "one_explicit_episode_slot_per_execute_command"
        ],
        "formal_execute_requires_clean_git": controls["formal_execute_requires_clean_git"],
        "formal_execute_requires_explicit_acknowledgement": controls[
            "formal_execute_requires_explicit_acknowledgement"
        ],
        "overwrite_formal_slot_allowed": controls["overwrite_formal_slot_allowed"],
        "partial_resume_allowed": controls["partial_resume_allowed"],
        "failed_attempt_evidence_retained": controls["failed_attempt_evidence_retained"],
        "pool_finalization_is_zero_llm": controls["pool_finalization_is_zero_llm"],
        "backend_public_identity": {
            "model_name": summary["backend"]["model_name"],
            "base_url": summary["backend"]["base_url"],
            "api_key_configured": summary["backend"]["api_key_configured"],
            "api_key_recorded": False,
            "exact_backend_call_count_claimed": False,
        },
        "protected_input_hashes_match_predeclared_contract": True,
        "protected_input_sha256": summary["protected_input_sha256"],
        "candidate_fixture_verified": True,
        "candidate_population_size": summary["candidate_fixture"]["population_size"],
        "selected_agent_ids_sha256": summary["candidate_fixture"]["selected_agent_ids_sha256"],
        "world_ticks_per_episode": summary["world_ticks_per_episode"],
        "agent_pipeline_executions_per_episode": summary[
            "agent_pipeline_executions_per_episode"
        ],
        "expected_pool_agent_pipeline_executions": summary[
            "expected_pool_agent_pipeline_executions"
        ],
        "outcome_conditioned_acceptance_gates_present": any(
            acceptance[key] is not None
            for key in (
                "minimum_post_count",
                "minimum_trade_count",
                "price_direction",
                "sentiment",
                "misinformation_effect",
                "cross_episode_divergence",
            )
        ),
        "participant_data_used": False,
        "controlled_stimulus_injected_into_agent_world": False,
        "formal_assets_written": False,
        "slot_state": summary["slot_state"],
        "note": (
            "Producer contract only. The default path validates exact Phase 13C v1.2 plan, "
            "public backend/model identity, protected input hashes, and frozen N30 fixture without "
            "calling an LLM. Formal execution remains one explicit episode slot per command."
        ),
    }
    if compact["outcome_conditioned_acceptance_gates_present"]:
        raise RuntimeError("Phase 13D contains an outcome-conditioned technical acceptance gate")
    if compact["full_pool_execute_command_allowed"] is not False:
        raise RuntimeError("Phase 13D accidentally permits one-command full-pool execution")
    if compact["one_explicit_episode_slot_per_execute_command"] is not True:
        raise RuntimeError("Phase 13D one-slot execution boundary drifted")
    if compact["world_ticks_per_episode"] != 27 or compact["agent_pipeline_executions_per_episode"] != 193:
        raise RuntimeError("Phase 13D frozen episode workload drifted")
    if compact["expected_pool_agent_pipeline_executions"] != 579:
        raise RuntimeError("Phase 13D frozen pool workload drifted")

    artifact_root = REPO_ROOT / "artifacts/preflight/phase13"
    artifact_root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_phase13d_producer_contract"
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    target = run_dir / "summary.json"
    target.write_text(json.dumps(compact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(compact, indent=2, ensure_ascii=False))
    print(f"Artifact: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
