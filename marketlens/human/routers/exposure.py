from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from marketlens.human.measurement.event_store import (
    ParticipantEventIdempotencyConflict,
    ParticipantEventStoreError,
)
from marketlens.human.schemas import (
    ExposureRequest,
    ParticipantBackgroundRead,
    ParticipantControlledStimulusRead,
)
from marketlens.human.services.background_service import ParticipantBackgroundUnavailableError
from marketlens.human.services.exposure_service import (
    ParticipantExposureInvariantError,
    ParticipantExposureUnavailableError,
)
from marketlens.human.services.orchestration_service import ExperimentStateConflictError
from marketlens.human.services.session_service import SessionNotFoundError
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
    "/session/{session_id}/exposure/background",
    response_model=ParticipantBackgroundRead,
)
def deliver_background(
    session_id: str,
    payload: ExposureRequest,
    request: Request,
) -> ParticipantBackgroundRead:
    try:
        return _runtime(request).exposure.deliver_background(
            session_id,
            payload.request_id,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except ParticipantEventIdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ParticipantEventStoreError as exc:
        raise HTTPException(status_code=503, detail="Participant event ledger unavailable") from exc
    except (
        ParticipantBackgroundUnavailableError,
        ParticipantExposureUnavailableError,
        ParticipantExposureInvariantError,
        ExperimentStateConflictError,
        TrustedParticipantContextUnavailableError,
        TrustedParticipantContextInvariantError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/session/{session_id}/exposure/stimulus",
    response_model=ParticipantControlledStimulusRead,
)
def deliver_controlled_stimulus(
    session_id: str,
    payload: ExposureRequest,
    request: Request,
) -> ParticipantControlledStimulusRead:
    try:
        delivery = _runtime(request).exposure.deliver_controlled_stimulus(
            session_id,
            payload.request_id,
        )
        return ParticipantControlledStimulusRead(**delivery.participant_payload())
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except ParticipantEventIdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ParticipantEventStoreError as exc:
        raise HTTPException(status_code=503, detail="Participant event ledger unavailable") from exc
    except (
        ParticipantExposureUnavailableError,
        ParticipantExposureInvariantError,
        ExperimentStateConflictError,
        TrustedParticipantContextUnavailableError,
        TrustedParticipantContextInvariantError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
