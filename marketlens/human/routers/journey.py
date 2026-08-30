from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from marketlens.human.feedback.journey import (
    ParticipantDecisionJourneyError,
)
from marketlens.human.feedback.journey_source import (
    JourneySourceError,
)
from marketlens.human.schemas import (
    ParticipantDecisionJourneyRead,
)
from marketlens.human.services.journey_service import (
    ParticipantJourneyConfigurationError,
    ParticipantJourneyUnavailableError,
)
from marketlens.human.services.session_service import (
    SessionNotFoundError,
)


router = APIRouter()


def _runtime(request: Request):
    runtime = getattr(
        request.app.state,
        "participant_runtime",
        None,
    )
    if runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Participant runtime is not configured",
        )
    return runtime


@router.get(
    "/session/{session_id}/journey",
    response_model=ParticipantDecisionJourneyRead,
)
def get_participant_journey(
    session_id: str,
    request: Request,
) -> ParticipantDecisionJourneyRead:
    runtime = _runtime(request)

    try:
        journey = runtime.journey.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Unknown session",
        ) from exc
    except (
        ParticipantJourneyUnavailableError,
        ParticipantJourneyConfigurationError,
        JourneySourceError,
        ParticipantDecisionJourneyError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return ParticipantDecisionJourneyRead.model_validate(
        journey.to_dict()
    )
