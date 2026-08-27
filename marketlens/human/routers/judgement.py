from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from marketlens.human.measurement.event_store import (
    ParticipantEventIdempotencyConflict,
    ParticipantEventStoreError,
)
from marketlens.human.measurement.runtime_recorder import ParticipantRuntimeEventInvariantError
from marketlens.human.schemas import (
    JudgementCreate,
    JudgementRead,
    ParticipantAssessmentCreate,
    ParticipantAssessmentRead,
)
from marketlens.human.services.judgement_service import (
    JudgementAlreadySubmittedError,
    JudgementStageError,
    JudgementTargetError,
)
from marketlens.human.services.session_service import (
    IdempotencyConflictError,
    SessionNotFoundError,
)
from marketlens.human.services.trusted_context_service import (
    TrustedParticipantContextInvariantError,
    TrustedParticipantContextUnavailableError,
)
from marketlens.human.services.view_state_service import assessment_mode_for_judgement_event

router = APIRouter()


def _runtime(request: Request):
    runtime = getattr(request.app.state, "participant_runtime", None)
    if runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Participant runtime is not configured",
        )
    return runtime


def _submit_judgement(session_id: str, payload: JudgementCreate, request: Request) -> JudgementRead:
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
        JudgementTargetError,
        ParticipantRuntimeEventInvariantError,
        TrustedParticipantContextUnavailableError,
        TrustedParticipantContextInvariantError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/session/{session_id}/judgement",
    response_model=JudgementRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def submit_judgement(
    session_id: str,
    payload: JudgementCreate,
    request: Request,
) -> JudgementRead:
    """Phase 14 compatibility route; not part of the Phase 15 frontend contract."""

    return _submit_judgement(session_id, payload, request)


@router.post(
    "/session/{session_id}/assessment",
    response_model=ParticipantAssessmentRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_participant_assessment(
    session_id: str,
    payload: ParticipantAssessmentCreate,
    request: Request,
) -> ParticipantAssessmentRead:
    """Participant-safe formal assessment; target and provenance are server-owned."""

    runtime = _runtime(request)
    judgement = _submit_judgement(
        session_id,
        JudgementCreate(
            request_id=payload.request_id,
            stock_id=runtime.target_stock_id,
            action=payload.action,
            confidence=payload.confidence,
            evidence_sources=payload.evidence_sources,
            rationale=payload.rationale,
        ),
        request,
    )
    return ParticipantAssessmentRead(
        assessment_id=judgement.judgement_id,
        session_id=judgement.session_id,
        request_id=judgement.request_id,
        assessment_target_stock_id=judgement.stock_id,
        assessment_mode=assessment_mode_for_judgement_event(judgement.judgement_event),
        action=judgement.action,
        confidence=judgement.confidence,
        evidence_sources=judgement.evidence_sources,
        rationale=judgement.rationale,
        submitted_at=judgement.submitted_at,
    )
