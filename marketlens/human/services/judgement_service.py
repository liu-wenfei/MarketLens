from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from marketlens.human.orchestration import (
    ExperimentOrchestrationContract,
    ExperimentOrchestrationError,
)
from marketlens.human.schemas import JudgementCreate, JudgementRead
from marketlens.human.services.session_service import (
    IdempotencyConflictError,
    SessionNotFoundError,
)
from marketlens.human.stores.errors import (
    StoreIdempotencyConflictError,
    StoreSessionNotFoundError,
)
from marketlens.human.stores.judgement_store import (
    JudgementStore,
    StoreJudgementAlreadySubmittedError,
    StoreJudgementStageError,
)
from marketlens.human.stores.orchestration_store import ExperimentOrchestrationStore


class JudgementAlreadySubmittedError(ValueError):
    pass


class JudgementStageError(ValueError):
    pass


def _to_judgement(row) -> JudgementRead:
    return JudgementRead(
        judgement_id=row["judgement_id"],
        session_id=row["session_id"],
        participant_id=row["participant_id"],
        request_id=row["request_id"],
        judgement_event=row["judgement_event"],
        experiment_step=int(row["experiment_step"]),
        agent_world_date=row["agent_world_date"],
        stock_id=row["stock_id"],
        action=row["action"],
        confidence=float(row["confidence"]),
        evidence_sources=json.loads(row["evidence_sources"]),
        rationale=row["rationale"],
        submitted_at=row["submitted_at"],
    )


class JudgementService:
    """Submit the formal judgement required by the current server-owned stage."""

    def __init__(
        self,
        judgements: JudgementStore,
        orchestration: ExperimentOrchestrationStore,
        *,
        contract: ExperimentOrchestrationContract | None = None,
    ):
        self.judgements = judgements
        self.orchestration = orchestration
        self.contract = contract or ExperimentOrchestrationContract()

    def submit(self, session_id: str, payload: JudgementCreate) -> JudgementRead:
        # Idempotent replay must be resolved before consulting the *current*
        # orchestration stage. A successful first submission advances the stage,
        # so checking stage first would incorrectly reject a retry of that same
        # request. Only caller-supplied fields are compared here; the persisted
        # judgement event/step/date remain server-authoritative.
        existing = self.judgements.get_by_request_id(session_id, payload.request_id)
        if existing is not None:
            same_payload = (
                existing["stock_id"] == payload.stock_id
                and existing["action"] == payload.action.value
                and float(existing["confidence"]) == float(payload.confidence)
                and existing["evidence_sources"] == json.dumps(payload.evidence_sources)
                and existing["rationale"] == payload.rationale
            )
            if not same_payload:
                raise IdempotencyConflictError(
                    "request_id was already used for a different formal judgement payload"
                )
            return _to_judgement(existing)

        state = self.orchestration.get(session_id)
        if state is None:
            raise SessionNotFoundError(session_id)
        stage = state["current_stage"]
        current_date = state["current_date"]
        if stage is None or current_date is None:
            raise JudgementStageError(
                "participant experiment orchestration is not initialized"
            )
        try:
            judgement_event = self.contract.expected_judgement_for_stage(stage)
            spec = self.contract.judgement_spec(judgement_event)
            self.contract.validate_checkpoint(int(state["current_step"]), current_date)
        except ExperimentOrchestrationError as exc:
            raise JudgementStageError(str(exc)) from exc
        if (
            int(state["current_step"]) != spec.experiment_step
            or current_date != spec.agent_world_date
        ):
            raise JudgementStageError(
                "current session checkpoint does not match the required formal judgement"
            )

        now = datetime.now(timezone.utc).isoformat()
        try:
            row = self.judgements.submit_idempotent(
                judgement_id=str(uuid4()),
                session_id=session_id,
                request_id=payload.request_id,
                judgement_event=spec.judgement_event,
                experiment_step=spec.experiment_step,
                agent_world_date=spec.agent_world_date,
                expected_stage=spec.required_stage.value,
                next_stage=spec.next_stage.value,
                stock_id=payload.stock_id,
                action=payload.action.value,
                confidence=payload.confidence,
                evidence_sources=payload.evidence_sources,
                rationale=payload.rationale,
                submitted_at=now,
            )
        except StoreSessionNotFoundError as exc:
            raise SessionNotFoundError(session_id) from exc
        except StoreIdempotencyConflictError as exc:
            raise IdempotencyConflictError(str(exc)) from exc
        except StoreJudgementAlreadySubmittedError as exc:
            raise JudgementAlreadySubmittedError(str(exc)) from exc
        except StoreJudgementStageError as exc:
            raise JudgementStageError(str(exc)) from exc
        return _to_judgement(row)
