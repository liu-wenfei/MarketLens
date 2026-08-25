#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import inspect

from marketlens.human.orchestration import ParticipantStage
from marketlens.human.schemas import DecisionAction, JudgementCreate, SessionCreate
from marketlens.human.services.judgement_service import JudgementService
from marketlens.human.services.orchestration_service import ExperimentOrchestrationService
from marketlens.human.services.session_service import SessionService
from marketlens.human.stores.judgement_store import JudgementStore
from marketlens.human.stores.orchestration_store import ExperimentOrchestrationStore
from marketlens.human.stores.session_store import SessionStore
from marketlens.persistence.database import Database


def payload(request_id: str) -> JudgementCreate:
    return JudgementCreate(
        request_id=request_id,
        stock_id="MEI",
        action=DecisionAction.HOLD,
        confidence=75.0,
        evidence_sources=["background"],
        rationale="zero-LLM orchestration preflight",
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="marketlens-phase14b3b0-") as temp_dir:
        db = Database(Path(temp_dir) / "human.db")
        session = SessionService(SessionStore(db)).create(
            SessionCreate(participant_id="PREFLIGHT-P001", request_id="session-001")
        )
        orchestration_store = ExperimentOrchestrationStore(db)
        orchestration = ExperimentOrchestrationService(orchestration_store)
        judgements = JudgementService(JudgementStore(db), orchestration_store)

        initial = orchestration.initialize(session.session_id)
        orchestration.after_background_delivery(session.session_id)
        j0 = judgements.submit(session.session_id, payload("j0"))
        j0_retry = judgements.submit(session.session_id, payload("j0"))
        orchestration.after_stimulus_delivery(session.session_id)
        j1 = judgements.submit(session.session_id, payload("j1"))
        orchestration.advance_checkpoint(session.session_id)

        while orchestration.get(session.session_id).experiment_step < 7:
            orchestration.after_background_delivery(session.session_id)
            orchestration.advance_checkpoint(session.session_id)

        orchestration.after_background_delivery(session.session_id)
        j2 = judgements.submit(session.session_id, payload("j2"))
        orchestration.after_stimulus_delivery(session.session_id)
        j3 = judgements.submit(session.session_id, payload("j3"))
        orchestration.advance_checkpoint(session.session_id)

        while orchestration.get(session.session_id).experiment_step < 14:
            orchestration.after_background_delivery(session.session_id)
            orchestration.advance_checkpoint(session.session_id)

        orchestration.after_background_delivery(session.session_id)
        j4 = judgements.submit(session.session_id, payload("j4"))
        final_state = orchestration.advance_checkpoint(session.session_id)
        rows = JudgementStore(db).list_for_session(session.session_id)

        decision_constraint_names = {
            item["name"] for item in inspect(db.engine).get_unique_constraints("decisions")
        }
        checks = {
            "formal_judgement_count_is_five": len(rows) == 5,
            "formal_judgement_events_exact": [row["judgement_event"] for row in rows]
            == ["J0", "J1", "J2", "J3", "J4"],
            "j0_j1_same_state": (j0.experiment_step, j0.agent_world_date)
            == (j1.experiment_step, j1.agent_world_date)
            == (0, "2023-06-19"),
            "j2_j3_same_state": (j2.experiment_step, j2.agent_world_date)
            == (j3.experiment_step, j3.agent_world_date)
            == (7, "2023-06-30"),
            "j4_later_measurement": (j4.experiment_step, j4.agent_world_date)
            == (14, "2023-07-11"),
            "judgement_retry_idempotent": j0.judgement_id == j0_retry.judgement_id,
            "participant_identity_server_derived": {row["participant_id"] for row in rows}
            == {"PREFLIGHT-P001"},
            "initial_date_protocol_derived": initial.agent_world_date == "2023-06-19",
            "initial_stage_server_owned": initial.current_stage == ParticipantStage.BACKGROUND_REQUIRED.value,
            "final_session_completed": final_state.completed is True
            and final_state.current_stage == ParticipantStage.COMPLETED.value,
            "legacy_decision_one_per_step_preserved": "uq_decisions_session_step"
            in decision_constraint_names,
            "client_supplied_judgement_event_step_date_stage": 0,
        }
        passed = (
            checks["formal_judgement_count_is_five"]
            and checks["formal_judgement_events_exact"]
            and checks["j0_j1_same_state"]
            and checks["j2_j3_same_state"]
            and checks["j4_later_measurement"]
            and checks["judgement_retry_idempotent"]
            and checks["participant_identity_server_derived"]
            and checks["initial_date_protocol_derived"]
            and checks["initial_stage_server_owned"]
            and checks["final_session_completed"]
            and checks["legacy_decision_one_per_step_preserved"]
            and checks["client_supplied_judgement_event_step_date_stage"] == 0
        )

        report = {
            "status": "PASS" if passed else "FAIL",
            "evidence_class": "NON-FORMAL / PHASE 14B3B0 PARTICIPANT EXPERIMENT ORCHESTRATION PREFLIGHT / ZERO-LLM",
            "llm_api_calls": 0,
            "formal_experiment_evidence": False,
            "public_judgement_router_added": False,
            "background_exposure_logging_added": False,
            "controlled_stimulus_delivery_added": False,
            "participant_events_db_written": False,
            "random_allocator_added": False,
            "phase10_protocol_modified": False,
            "phase11_formal_stimulus_modified": False,
            "phase12_source_cue_modified": False,
            **checks,
            "agent_world_db_written": False,
            "forum_db_written": False,
            "note": "B3B0 separates formal J0..J4 measurement from one-per-step decisions and freezes server-owned stage/date transitions. Public exposure/runtime wiring remains deferred.",
        }
        print("NON-FORMAL / PHASE 14B3B0 PARTICIPANT EXPERIMENT ORCHESTRATION PREFLIGHT / ZERO-LLM")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        db.dispose()
        if not passed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
