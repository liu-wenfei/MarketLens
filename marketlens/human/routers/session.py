from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from marketlens.human.schemas import ParticipantViewState, SessionCreate, SessionRead, SessionState
from marketlens.human.services.orchestration_service import ExperimentStateConflictError
from marketlens.human.services.session_service import (
    IdempotencyConflictError,
    SessionNotFoundError,
    SessionService,
)
from marketlens.human.services.state_service import MarketStateUnavailableError, StateService
from marketlens.human.services.trusted_context_service import (
    TrustedParticipantContextInvariantError,
    TrustedParticipantContextUnavailableError,
)
from marketlens.human.services.view_state_service import (
    ParticipantViewStateInvariantError,
    ParticipantViewStateUnavailableError,
)
from marketlens.human.stores.session_store import SessionStore

router = APIRouter()


def get_session_service(request: Request) -> SessionService:
    return SessionService(SessionStore(request.app.state.db))


@router.post("/session", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    request: Request,
    service: SessionService = Depends(get_session_service),
) -> SessionRead:
    try:
        created = service.create(payload)
        runtime = getattr(request.app.state, "participant_runtime", None)
        if runtime is not None:
            runtime.orchestration.initialize(created.session_id)
            return service.get(created.session_id)
        return created
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ExperimentStateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/session/{session_id}", response_model=SessionRead)
def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> SessionRead:
    try:
        return service.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc


@router.get("/session/{session_id}/state", response_model=SessionState)
def get_session_state(
    session_id: str,
    request: Request,
    service: SessionService = Depends(get_session_service),
) -> SessionState:
    try:
        return StateService(service, request.app.state.trading_calendar).get_current_state(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except MarketStateUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/session/{session_id}/view", response_model=ParticipantViewState)
def get_participant_view_state(
    session_id: str,
    request: Request,
) -> ParticipantViewState:
    runtime = getattr(request.app.state, "participant_runtime", None)
    if runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Participant runtime is not configured",
        )
    try:
        return runtime.view_state.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except (
        TrustedParticipantContextUnavailableError,
        TrustedParticipantContextInvariantError,
        ParticipantViewStateUnavailableError,
        ParticipantViewStateInvariantError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
