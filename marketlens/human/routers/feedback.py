from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from marketlens.human.schemas import (
    ParticipantFeedbackContinueCreate,
    ParticipantFeedbackContinueRead,
    ParticipantFeedbackRead,
)
from marketlens.human.services.feedback_delivery_service import (
    ParticipantFeedbackConflictError,
    ParticipantFeedbackNotPreparedError,
    ParticipantFeedbackStateError,
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
    "/session/{session_id}/feedback/current",
    response_model=ParticipantFeedbackRead,
)
def get_current_feedback(
    session_id: str,
    request: Request,
) -> ParticipantFeedbackRead:
    runtime = _runtime(request)

    try:
        feedback = runtime.feedback.get_current(
            session_id
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Unknown session",
        ) from exc
    except (
        ParticipantFeedbackStateError,
        ParticipantFeedbackNotPreparedError,
        ParticipantFeedbackConflictError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return ParticipantFeedbackRead(
        feedback_kind=feedback.feedback_kind,
        statistics=feedback.statistics,
        reflection=feedback.reflection,
    )


@router.post(
    "/session/{session_id}/feedback/current/continue",
    response_model=ParticipantFeedbackContinueRead,
)
def continue_current_feedback(
    session_id: str,
    payload: ParticipantFeedbackContinueCreate,
    request: Request,
) -> ParticipantFeedbackContinueRead:
    runtime = _runtime(request)

    try:
        continued = runtime.feedback.continue_current(
            session_id,
            payload.request_id,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Unknown session",
        ) from exc
    except (
        ParticipantFeedbackStateError,
        ParticipantFeedbackNotPreparedError,
        ParticipantFeedbackConflictError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return ParticipantFeedbackContinueRead(
        continued=continued
    )
