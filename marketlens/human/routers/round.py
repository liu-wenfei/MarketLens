from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from marketlens.human.schemas import RoundComplete, RoundCompletionRead
from marketlens.human.services.round_service import (
    RoundAlreadyCompletedError,
    RoundService,
    WrongExperimentStepError,
)
from marketlens.human.services.session_service import (
    IdempotencyConflictError,
    SessionNotFoundError,
)
from marketlens.human.stores.round_store import RoundStore

router = APIRouter()


def get_round_service(request: Request) -> RoundService:
    return RoundService(rounds=RoundStore(request.app.state.db))


@router.post(
    "/session/{session_id}/round/complete",
    response_model=RoundCompletionRead,
    status_code=status.HTTP_201_CREATED,
)
def complete_round(
    session_id: str,
    payload: RoundComplete,
    service: RoundService = Depends(get_round_service),
) -> RoundCompletionRead:
    try:
        return service.complete(session_id, payload)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except (
        IdempotencyConflictError,
        RoundAlreadyCompletedError,
        WrongExperimentStepError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
