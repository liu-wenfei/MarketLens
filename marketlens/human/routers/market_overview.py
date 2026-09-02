from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from marketlens.human.schemas import (
    ParticipantMarketOverviewRead,
)
from marketlens.human.services.market_overview_service import (
    ParticipantMarketOverviewInvariantError,
    ParticipantMarketOverviewService,
    ParticipantMarketOverviewUnavailableError,
)
from marketlens.human.services.session_service import (
    SessionNotFoundError,
)
from marketlens.human.services.trusted_context_service import (
    TrustedParticipantContextInvariantError,
    TrustedParticipantContextUnavailableError,
)


router = APIRouter()


def _service(
    request: Request,
) -> ParticipantMarketOverviewService:
    runtime = getattr(
        request.app.state,
        "participant_runtime",
        None,
    )

    if runtime is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "participant market overview requires "
                "the participant runtime"
            ),
        )

    return ParticipantMarketOverviewService(
        context=runtime.context,
        orchestration=runtime.orchestration,
        assets=request.app.state.asset_catalog,
        price_providers=(
            runtime.journey.price_providers
        ),
        calendar=runtime.journey.calendar,
    )


@router.get(
    "/session/{session_id}/market-overview",
    response_model=ParticipantMarketOverviewRead,
)
def get_market_overview(
    session_id: str,
    request: Request,
) -> ParticipantMarketOverviewRead:
    try:
        return _service(
            request
        ).get(
            session_id
        )

    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Unknown session",
        ) from exc

    except (
        TrustedParticipantContextUnavailableError,
        TrustedParticipantContextInvariantError,
        ParticipantMarketOverviewUnavailableError,
        ParticipantMarketOverviewInvariantError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
