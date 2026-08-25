from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from marketlens.human.schemas import DecisionCreate, DecisionRead
from marketlens.human.services.decision_service import (
    DecisionAlreadySubmittedError,
    DecisionService,
    WrongExperimentStepError,
)
from marketlens.human.services.session_service import (
    IdempotencyConflictError,
    SessionNotFoundError,
)
from marketlens.human.stores.decision_store import DecisionStore

router = APIRouter()


def get_decision_service(request: Request) -> DecisionService:
    return DecisionService(decisions=DecisionStore(request.app.state.db))


@router.post(
    "/session/{session_id}/decision",
    response_model=DecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_decision(
    session_id: str,
    payload: DecisionCreate,
    request: Request,
    service: DecisionService = Depends(get_decision_service),
) -> DecisionRead:
    if getattr(request.app.state, "participant_runtime", None) is not None:
        raise HTTPException(
            status_code=409,
            detail="Legacy decision submission is disabled in participant runtime; use /session/{session_id}/judgement",
        )
    try:
        return service.submit(session_id, payload)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DecisionAlreadySubmittedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WrongExperimentStepError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
