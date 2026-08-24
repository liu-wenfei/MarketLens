from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from marketlens.human.schemas import ParticipantBackgroundRead
from marketlens.human.services.background_service import (
    ParticipantBackgroundService,
    ParticipantBackgroundUnavailableError,
)
from marketlens.human.services.session_service import SessionNotFoundError, SessionService
from marketlens.human.routers.session import get_session_service

router = APIRouter()


@router.get("/session/{session_id}/background", response_model=ParticipantBackgroundRead)
def get_participant_background(
    session_id: str,
    request: Request,
    sessions: SessionService = Depends(get_session_service),
) -> ParticipantBackgroundRead:
    try:
        return ParticipantBackgroundService(
            sessions,
            getattr(request.app.state, "background_projection", None),
        ).get_current_background(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except ParticipantBackgroundUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
