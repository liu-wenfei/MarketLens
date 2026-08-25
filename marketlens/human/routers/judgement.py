from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from marketlens.human.measurement.event_store import (
    ParticipantEventIdempotencyConflict,
    ParticipantEventStoreError,
)
from marketlens.human.measurement.runtime_recorder import ParticipantRuntimeEventInvariantError
from marketlens.human.schemas import JudgementCreate, JudgementRead
from marketlens.human.services.judgement_service import (
    JudgementAlreadySubmittedError,
    JudgementStageError,
)
from marketlens.human.services.session_service import (
    IdempotencyConflictError,
    SessionNotFoundError,
)
from marketlens.human.services.trusted_context_service import (
    TrustedParticipantContextInvariantError,
    TrustedParticipantContextUnavailableError,
)

router = APIRouter()


def _runtime(request: Request):
    runtime = getattr(request.app.state, "participant_runtime", None)
    if runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Participant runtime is not configured",
        )
    return runtime


@router.post(
    "/session/{session_id}/judgement",
    response_model=JudgementRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_judgement(
    session_id: str,
    payload: JudgementCreate,
    request: Request,
) -> JudgementRead:
    runtime = _runtime(request)
    try:
        judgement = runtime.judgements.submit(session_id, payload)
        runtime.recorder.record_judgement(judgement)
        return judgement
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except ParticipantEventIdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ParticipantEventStoreError as exc:
        raise HTTPException(status_code=503, detail="Participant event ledger unavailable") from exc
    except (
        IdempotencyConflictError,
        JudgementAlreadySubmittedError,
        JudgementStageError,
        ParticipantRuntimeEventInvariantError,
        TrustedParticipantContextUnavailableError,
        TrustedParticipantContextInvariantError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
