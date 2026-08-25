from __future__ import annotations

from dataclasses import dataclass

from marketlens.human.orchestration import (
    ExperimentOrchestrationContract,
    ExperimentOrchestrationError,
    ParticipantStage,
)
from marketlens.human.services.session_service import SessionNotFoundError
from marketlens.human.stores.errors import StoreSessionNotFoundError
from marketlens.human.stores.orchestration_store import (
    ExperimentOrchestrationStore,
    StoreExperimentStateConflictError,
)


class ExperimentStateConflictError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParticipantExperimentState:
    session_id: str
    participant_id: str
    experiment_step: int
    agent_world_date: str | None
    current_stage: str | None
    experiment_status: str
    completed: bool


def _to_state(row) -> ParticipantExperimentState:
    return ParticipantExperimentState(
        session_id=row["session_id"],
        participant_id=row["participant_id"],
        experiment_step=int(row["current_step"]),
        agent_world_date=row["current_date"],
        current_stage=row["current_stage"],
        experiment_status=row["experiment_status"],
        completed=bool(row["completed"]),
    )


class ExperimentOrchestrationService:
    """Server-owned state transitions; callers never supply date/stage targets."""

    def __init__(
        self,
        store: ExperimentOrchestrationStore,
        *,
        contract: ExperimentOrchestrationContract | None = None,
    ):
        self.store = store
        self.contract = contract or ExperimentOrchestrationContract()

    def get(self, session_id: str) -> ParticipantExperimentState:
        row = self.store.get(session_id)
        if row is None:
            raise SessionNotFoundError(session_id)
        return _to_state(row)

    def initialize(self, session_id: str) -> ParticipantExperimentState:
        try:
            row = self.store.initialize_idempotent(
                session_id=session_id,
                initial_step=self.contract.initial_step,
                initial_date=self.contract.initial_date,
                initial_stage=self.contract.initial_stage.value,
            )
        except StoreSessionNotFoundError as exc:
            raise SessionNotFoundError(session_id) from exc
        except StoreExperimentStateConflictError as exc:
            raise ExperimentStateConflictError(str(exc)) from exc
        return _to_state(row)

    def after_background_delivery(self, session_id: str) -> ParticipantExperimentState:
        state = self.get(session_id)
        if state.agent_world_date is None:
            raise ExperimentStateConflictError("session has no protocol-bound current date")
        try:
            self.contract.validate_checkpoint(state.experiment_step, state.agent_world_date)
            next_stage = self.contract.after_background_stage(state.experiment_step)
            row = self.store.transition_stage(
                session_id=session_id,
                experiment_step=state.experiment_step,
                agent_world_date=state.agent_world_date,
                expected_stage=ParticipantStage.BACKGROUND_REQUIRED.value,
                next_stage=next_stage.value,
            )
        except (ExperimentOrchestrationError, StoreExperimentStateConflictError) as exc:
            raise ExperimentStateConflictError(str(exc)) from exc
        return _to_state(row)

    def after_stimulus_delivery(self, session_id: str) -> ParticipantExperimentState:
        state = self.get(session_id)
        if state.agent_world_date is None or state.current_stage is None:
            raise ExperimentStateConflictError("session has no protocol-bound stage/date")
        try:
            self.contract.validate_checkpoint(state.experiment_step, state.agent_world_date)
            next_stage = self.contract.after_stimulus_stage(state.current_stage)
            row = self.store.transition_stage(
                session_id=session_id,
                experiment_step=state.experiment_step,
                agent_world_date=state.agent_world_date,
                expected_stage=state.current_stage,
                next_stage=next_stage.value,
            )
        except (ExperimentOrchestrationError, StoreExperimentStateConflictError) as exc:
            raise ExperimentStateConflictError(str(exc)) from exc
        return _to_state(row)

    def advance_checkpoint(self, session_id: str) -> ParticipantExperimentState:
        state = self.get(session_id)
        if state.agent_world_date is None:
            raise ExperimentStateConflictError("session has no protocol-bound current date")
        try:
            self.contract.validate_checkpoint(state.experiment_step, state.agent_world_date)
            next_checkpoint = self.contract.next_checkpoint(state.experiment_step)
            if next_checkpoint is None:
                next_step = None
                next_date = None
                next_stage = ParticipantStage.COMPLETED
            else:
                next_step, next_date = next_checkpoint
                next_stage = ParticipantStage.BACKGROUND_REQUIRED
            row = self.store.advance_checkpoint(
                session_id=session_id,
                experiment_step=state.experiment_step,
                agent_world_date=state.agent_world_date,
                expected_stage=ParticipantStage.ROUND_ACTIVE.value,
                next_step=next_step,
                next_date=next_date,
                next_stage=next_stage.value,
            )
        except (ExperimentOrchestrationError, StoreExperimentStateConflictError) as exc:
            raise ExperimentStateConflictError(str(exc)) from exc
        return _to_state(row)
