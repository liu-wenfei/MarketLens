from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from marketlens.human.schemas import SessionCreate, SessionRead, SessionState
from marketlens.human.services.session_service import (
    IdempotencyConflictError,
    SessionNotFoundError,
    SessionService,
)
from marketlens.human.services.state_service import MarketStateUnavailableError, StateService
from marketlens.human.stores.session_store import SessionStore

router = APIRouter()


def get_session_service(request: Request) -> SessionService:
    return SessionService(SessionStore(request.app.state.db))


@router.post("/session", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    service: SessionService = Depends(get_session_service),
) -> SessionRead:
    try:
        return service.create(payload)
    except IdempotencyConflictError as exc:
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
