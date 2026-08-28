from __future__ import annotations

from sqlalchemy import inspect

import pytest

from marketlens.human.orchestration import (
    ExperimentOrchestrationContract,
    ParticipantStage,
)
from marketlens.human.schemas import DecisionAction, JudgementCreate
from marketlens.human.services.judgement_service import (
    JudgementService,
    JudgementStageError,
)
from marketlens.human.services.orchestration_service import (
    ExperimentOrchestrationService,
)
from marketlens.human.services.session_service import SessionService
from marketlens.human.stores.judgement_store import JudgementStore
from marketlens.human.stores.orchestration_store import ExperimentOrchestrationStore
from marketlens.human.stores.session_store import SessionStore
from marketlens.persistence.database import Database
from marketlens.human.schemas import SessionCreate


def _services(tmp_path):
    db = Database(tmp_path / "human.db")
    contract = ExperimentOrchestrationContract()
    orchestration_store = ExperimentOrchestrationStore(db)
    orchestration = ExperimentOrchestrationService(
        orchestration_store, contract=contract
    )
    judgements = JudgementService(
        JudgementStore(db), orchestration_store, contract=contract
    )
    session = SessionService(SessionStore(db)).create(
        SessionCreate(participant_id="P001", request_id="session-001")
    )
    return db, contract, orchestration, judgements, session


def _payload(request_id: str) -> JudgementCreate:
    return JudgementCreate(
        request_id=request_id,
        stock_id="MEI",
        action=DecisionAction.HOLD,
        confidence=70.0,
        evidence_sources=["background"],
        rationale="test",
    )


def test_client_judgement_payload_cannot_supply_provenance_or_stage() -> None:
    assert set(JudgementCreate.model_fields) == {
        "request_id", "stock_id", "action", "confidence", "evidence_sources", "rationale"
    }


def test_contract_preserves_same_state_judgement_pairs() -> None:
    contract = ExperimentOrchestrationContract()
    j0 = contract.judgement_spec("J0")
    j1 = contract.judgement_spec("J1")
    j2 = contract.judgement_spec("J2")
    j3 = contract.judgement_spec("J3")
    j4 = contract.judgement_spec("J4")
    assert (j0.experiment_step, j0.agent_world_date) == (j1.experiment_step, j1.agent_world_date)
    assert (j2.experiment_step, j2.agent_world_date) == (j3.experiment_step, j3.agent_world_date)
    assert j4.experiment_step == 14
    assert j4.agent_world_date == "2023-07-11"


def test_formal_orchestration_initializes_date_and_stage_from_protocol(tmp_path) -> None:
    db, contract, orchestration, _judgements, session = _services(tmp_path)
    state = orchestration.initialize(session.session_id)
    assert state.experiment_step == 0
    assert state.agent_world_date == contract.initial_date == "2023-06-19"
    assert state.current_stage == ParticipantStage.BACKGROUND_REQUIRED.value
    db.dispose()


def test_j0_j1_are_distinct_measurements_on_same_checkpoint(tmp_path) -> None:
    db, _contract, orchestration, judgements, session = _services(tmp_path)
    orchestration.initialize(session.session_id)
    state = orchestration.after_background_delivery(session.session_id)
    assert state.current_stage == ParticipantStage.J0_REQUIRED.value

    j0 = judgements.submit(session.session_id, _payload("j0-request"))
    assert j0.judgement_event == "J0"
    assert j0.experiment_step == 0
    assert j0.agent_world_date == "2023-06-19"
    assert orchestration.get(session.session_id).current_stage == ParticipantStage.MISINFORMATION_DELIVERY_REQUIRED.value

    orchestration.after_stimulus_delivery(session.session_id)
    j1 = judgements.submit(session.session_id, _payload("j1-request"))
    assert j1.judgement_event == "J1"
    assert (j1.experiment_step, j1.agent_world_date) == (j0.experiment_step, j0.agent_world_date)
    assert j1.judgement_id != j0.judgement_id
    assert orchestration.get(session.session_id).current_stage == ParticipantStage.ROUND_ACTIVE.value
    db.dispose()


def test_judgement_retry_is_idempotent_after_stage_advance(tmp_path) -> None:
    db, _contract, orchestration, judgements, session = _services(tmp_path)
    orchestration.initialize(session.session_id)
    orchestration.after_background_delivery(session.session_id)
    first = judgements.submit(session.session_id, _payload("same-request"))
    second = judgements.submit(session.session_id, _payload("same-request"))
    assert first.judgement_id == second.judgement_id
    assert orchestration.get(session.session_id).current_stage == ParticipantStage.MISINFORMATION_DELIVERY_REQUIRED.value
    db.dispose()


def test_wrong_stage_fails_closed_without_creating_judgement(tmp_path) -> None:
    db, _contract, orchestration, judgements, session = _services(tmp_path)
    orchestration.initialize(session.session_id)
    with pytest.raises(JudgementStageError):
        judgements.submit(session.session_id, _payload("too-early"))
    assert JudgementStore(db).list_for_session(session.session_id) == ()
    db.dispose()


def _advance_ordinary(orchestration, session_id: str) -> None:
    state = orchestration.after_background_delivery(session_id)
    assert state.current_stage == ParticipantStage.ROUND_ACTIVE.value

    if orchestration.contract.feedback_required_after_round(
        state.experiment_step
    ):
        # Unit-test simulation only: the protocol-round integration
        # tests separately verify that the real round completion
        # atomically records the behaviour lock and enters this stage.
        orchestration.store.transition_stage(
            session_id=session_id,
            experiment_step=state.experiment_step,
            agent_world_date=state.agent_world_date,
            expected_stage=ParticipantStage.ROUND_ACTIVE.value,
            next_stage=ParticipantStage.FEEDBACK_REQUIRED.value,
        )
        orchestration.continue_after_feedback(session_id)
    else:
        orchestration.advance_checkpoint(session_id)


def test_protocol_driven_advancement_reaches_j2_j3_and_j4(tmp_path) -> None:
    db, _contract, orchestration, judgements, session = _services(tmp_path)
    orchestration.initialize(session.session_id)
    orchestration.after_background_delivery(session.session_id)
    judgements.submit(session.session_id, _payload("j0"))
    orchestration.after_stimulus_delivery(session.session_id)
    judgements.submit(session.session_id, _payload("j1"))
    orchestration.advance_checkpoint(session.session_id)

    while orchestration.get(session.session_id).experiment_step < 7:
        _advance_ordinary(orchestration, session.session_id)

    state = orchestration.after_background_delivery(session.session_id)
    assert state.current_stage == ParticipantStage.J2_REQUIRED.value
    j2 = judgements.submit(session.session_id, _payload("j2"))
    assert (j2.experiment_step, j2.agent_world_date) == (7, "2023-06-30")
    orchestration.after_stimulus_delivery(session.session_id)
    j3 = judgements.submit(session.session_id, _payload("j3"))
    assert (j3.experiment_step, j3.agent_world_date) == (7, "2023-06-30")
    orchestration.advance_checkpoint(session.session_id)

    while orchestration.get(session.session_id).experiment_step < 14:
        _advance_ordinary(orchestration, session.session_id)

    state = orchestration.after_background_delivery(session.session_id)
    assert state.current_stage == ParticipantStage.J4_REQUIRED.value
    j4 = judgements.submit(session.session_id, _payload("j4"))
    assert (j4.experiment_step, j4.agent_world_date) == (14, "2023-07-11")
    final_round_state = orchestration.get(session.session_id)
    assert final_round_state.current_stage == ParticipantStage.ROUND_ACTIVE.value

    # Unit-test simulation only: integration tests verify the real terminal
    # round completion atomically records the behaviour lock and enters
    # FEEDBACK_REQUIRED.
    orchestration.store.transition_stage(
        session_id=session.session_id,
        experiment_step=final_round_state.experiment_step,
        agent_world_date=final_round_state.agent_world_date,
        expected_stage=ParticipantStage.ROUND_ACTIVE.value,
        next_stage=ParticipantStage.FEEDBACK_REQUIRED.value,
    )

    feedback_state = orchestration.get(session.session_id)
    assert feedback_state.experiment_step == 14
    assert feedback_state.current_stage == ParticipantStage.FEEDBACK_REQUIRED.value
    assert feedback_state.completed is False

    after_feedback = orchestration.continue_after_feedback(session.session_id)
    assert after_feedback.experiment_step == 14
    assert after_feedback.current_stage == ParticipantStage.DEBRIEF_REQUIRED.value
    assert after_feedback.completed is False

    completed = orchestration.complete_after_debrief(session.session_id)
    assert completed.completed is True
    assert completed.current_stage == ParticipantStage.COMPLETED.value
    assert [r["judgement_event"] for r in JudgementStore(db).list_for_session(session.session_id)] == ["J0", "J1", "J2", "J3", "J4"]
    db.dispose()


def test_participant_identity_is_derived_from_session(tmp_path) -> None:
    db, _contract, orchestration, judgements, session = _services(tmp_path)
    orchestration.initialize(session.session_id)
    orchestration.after_background_delivery(session.session_id)
    row = judgements.submit(session.session_id, _payload("j0"))
    assert row.participant_id == "P001"
    db.dispose()


def test_existing_decision_one_per_step_constraint_is_preserved(tmp_path) -> None:
    db = Database(tmp_path / "schema.db")
    constraints = inspect(db.engine).get_unique_constraints("decisions")
    names = {item["name"] for item in constraints}
    assert "uq_decisions_session_step" in names
    db.dispose()
