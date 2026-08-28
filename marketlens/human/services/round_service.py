from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from marketlens.human.orchestration import (
    ExperimentOrchestrationContract,
    ExperimentOrchestrationError,
    ParticipantStage,
)
from marketlens.human.schemas import RoundComplete, RoundCompletionRead
from marketlens.human.services.orchestration_service import ExperimentOrchestrationService
from marketlens.human.services.session_service import (
    IdempotencyConflictError,
    SessionNotFoundError,
)
from marketlens.human.stores.errors import (
    StoreIdempotencyConflictError,
    StoreRoundAlreadyCompletedError,
    StoreSessionNotFoundError,
    StoreWrongExperimentStepError,
)
from marketlens.human.stores.round_store import (
    RoundStore,
    StoreProtocolRoundStateConflictError,
)


class RoundAlreadyCompletedError(ValueError):
    pass


class WrongExperimentStepError(ValueError):
    pass


class RoundStateConflictError(ValueError):
    pass


def _to_completion(row) -> RoundCompletionRead:
    return RoundCompletionRead(
        completion_id=row["completion_id"],
        session_id=row["session_id"],
        request_id=row["request_id"],
        step=row["step"],
        next_step=(None if row["next_step"] is None else int(row["next_step"])),
        completed_at=row["completed_at"],
    )


class RoundService:
    def __init__(self, rounds: RoundStore):
        self.rounds = rounds

    def complete(self, session_id: str, payload: RoundComplete) -> RoundCompletionRead:
        now = datetime.now(timezone.utc).isoformat()
        try:
            row = self.rounds.complete_idempotent(
                completion_id=str(uuid4()),
                session_id=session_id,
                request_id=payload.request_id,
                step=payload.step,
                completed_at=now,
            )
        except StoreSessionNotFoundError as exc:
            raise SessionNotFoundError(session_id) from exc
        except StoreIdempotencyConflictError as exc:
            raise IdempotencyConflictError(str(exc)) from exc
        except StoreRoundAlreadyCompletedError as exc:
            raise RoundAlreadyCompletedError(str(exc)) from exc
        except StoreWrongExperimentStepError as exc:
            raise WrongExperimentStepError(str(exc)) from exc
        return _to_completion(row)


class ParticipantProtocolRoundService:
    """Complete participant checkpoints using only the frozen server-owned protocol."""

    def __init__(
        self,
        *,
        rounds: RoundStore,
        orchestration: ExperimentOrchestrationService,
        contract: ExperimentOrchestrationContract | None = None,
    ):
        self.rounds = rounds
        self.orchestration = orchestration
        self.contract = contract or orchestration.contract

    def complete(self, session_id: str, payload: RoundComplete) -> RoundCompletionRead:
        # A replay must be resolved before consulting the current session state:
        # the first successful request has already advanced to the next checkpoint.
        existing = self.rounds.get_by_request_id(session_id, payload.request_id)
        if existing is not None:
            if int(existing["step"]) != int(payload.step):
                raise IdempotencyConflictError(
                    "request_id was already used to complete a different step"
                )
            return _to_completion(existing)

        existing_step = self.rounds.get_by_step(session_id, payload.step)
        if existing_step is not None:
            raise RoundAlreadyCompletedError(
                f"Round {payload.step} was already completed"
            )

        state = self.orchestration.get(session_id)
        if int(payload.step) != int(state.experiment_step):
            raise WrongExperimentStepError(
                f"Round step {payload.step} does not match current step {state.experiment_step}"
            )
        if (
            state.completed
            or state.agent_world_date is None
            or state.current_stage != ParticipantStage.ROUND_ACTIVE.value
        ):
            raise RoundStateConflictError(
                "participant round completion requires the server-owned ROUND_ACTIVE stage"
            )

        try:
            self.contract.validate_checkpoint(
                state.experiment_step,
                state.agent_world_date,
            )
            next_checkpoint = self.contract.next_checkpoint(state.experiment_step)
        except ExperimentOrchestrationError as exc:
            raise RoundStateConflictError(str(exc)) from exc

        if next_checkpoint is None:
            next_step = None
            next_date = None
            next_stage = ParticipantStage.COMPLETED
        else:
            next_step, next_date = next_checkpoint
            next_stage = ParticipantStage.BACKGROUND_REQUIRED

        interstitial_stage = (
            ParticipantStage.FEEDBACK_REQUIRED.value
            if self.contract.feedback_required_after_round(state.experiment_step)
            else None
        )

        now = datetime.now(timezone.utc).isoformat()
        try:
            row = self.rounds.complete_protocol_idempotent(
                completion_id=str(uuid4()),
                session_id=session_id,
                request_id=payload.request_id,
                step=state.experiment_step,
                agent_world_date=state.agent_world_date,
                expected_stage=ParticipantStage.ROUND_ACTIVE.value,
                next_step=next_step,
                next_date=next_date,
                next_stage=next_stage.value,
                interstitial_stage=interstitial_stage,
                completed_at=now,
            )
        except StoreSessionNotFoundError as exc:
            raise SessionNotFoundError(session_id) from exc
        except StoreIdempotencyConflictError as exc:
            raise IdempotencyConflictError(str(exc)) from exc
        except StoreRoundAlreadyCompletedError as exc:
            raise RoundAlreadyCompletedError(str(exc)) from exc
        except StoreProtocolRoundStateConflictError as exc:
            raise RoundStateConflictError(str(exc)) from exc
        return _to_completion(row)
