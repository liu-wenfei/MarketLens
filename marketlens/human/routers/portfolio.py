from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from marketlens.human.measurement.event_store import (
    ParticipantEventIdempotencyConflict,
    ParticipantEventStoreError,
)
from marketlens.human.measurement.runtime_recorder import ParticipantRuntimeEventInvariantError
from marketlens.human.orchestration import ParticipantStage
from marketlens.human.schemas import (
    PortfolioOrderCreate,
    PortfolioOrderPreviewCreate,
    PortfolioOrderPreviewRead,
    PortfolioRead,
    PortfolioTransactionRead,
)
from marketlens.human.services.portfolio_service import (
    InvalidPortfolioOrderError,
    MarketClosedError,
    MarketDateUnavailableError,
    PortfolioService,
    PortfolioStateConflictError,
    WrongPortfolioStepError,
)
from marketlens.human.services.session_service import IdempotencyConflictError, SessionNotFoundError
from marketlens.human.services.trusted_context_service import (
    TrustedParticipantContextInvariantError,
    TrustedParticipantContextUnavailableError,
)
from marketlens.human.stores.portfolio_store import PortfolioStore
from marketlens.market.asset_catalog import AssetNotFoundError

router = APIRouter()


def get_portfolio_service(
    request: Request,
    session_id: str,
) -> PortfolioService:
    """Resolve the authoritative price source for this participant session.

    Legacy/non-participant routes retain the inherited CSV provider.

    Participant runtime settlement is episode-aware: the participant is a
    price-taking investor in the assigned canonical episode, so settlement and
    portfolio mark-to-market must use the same episode-specific exact-date
    canonical close-price provider used by Decision Journey.
    """

    prices = request.app.state.price_provider
    runtime = getattr(request.app.state, "participant_runtime", None)

    if runtime is not None:
        try:
            trusted = runtime.context.resolve(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail="Unknown session",
            ) from exc
        except (
            TrustedParticipantContextUnavailableError,
            TrustedParticipantContextInvariantError,
        ) as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

        prices = runtime.journey.price_providers.get(
            trusted.episode_id
        )
        if prices is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "No canonical close-price provider is bound for "
                    "the participant's assigned episode"
                ),
            )

    return PortfolioService(
        store=PortfolioStore(request.app.state.db),
        assets=request.app.state.asset_catalog,
        prices=prices,
        policy=request.app.state.portfolio_policy,
        calendar=request.app.state.trading_calendar,
    )


def _participant_runtime_for_trade(request: Request, session_id: str):
    runtime = getattr(request.app.state, "participant_runtime", None)
    if runtime is None:
        return None

    try:
        runtime.context.resolve(session_id)
        state = runtime.orchestration.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except (
        TrustedParticipantContextUnavailableError,
        TrustedParticipantContextInvariantError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if state.current_stage != ParticipantStage.ROUND_ACTIVE.value:
        raise HTTPException(
            status_code=409,
            detail="Participant trading is not authorised before the current protocol checkpoint reaches ROUND_ACTIVE",
        )
    return runtime


@router.get("/session/{session_id}/portfolio", response_model=PortfolioRead)
def get_portfolio(
    session_id: str,
    service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioRead:
    try:
        return service.get_portfolio(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except MarketDateUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/session/{session_id}/portfolio/preview",
    response_model=PortfolioOrderPreviewRead,
)
def preview_portfolio_order(
    session_id: str,
    payload: PortfolioOrderPreviewCreate,
    request: Request,
    service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioOrderPreviewRead:
    try:
        _participant_runtime_for_trade(request, session_id)
        return service.preview(session_id, payload)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown asset") from exc
    except (WrongPortfolioStepError, MarketDateUnavailableError, MarketClosedError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/session/{session_id}/portfolio/order",
    response_model=PortfolioTransactionRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_portfolio_order(
    session_id: str,
    payload: PortfolioOrderCreate,
    request: Request,
    service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioTransactionRead:
    try:
        runtime = _participant_runtime_for_trade(request, session_id)
        transaction = service.submit(session_id, payload)
        if runtime is not None:
            runtime.recorder.record_transaction(transaction)
        return transaction
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown asset") from exc
    except ParticipantEventIdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ParticipantEventStoreError as exc:
        raise HTTPException(status_code=503, detail="Participant event ledger unavailable") from exc
    except (
        ParticipantRuntimeEventInvariantError,
        TrustedParticipantContextUnavailableError,
        TrustedParticipantContextInvariantError,
        IdempotencyConflictError,
        WrongPortfolioStepError,
        MarketDateUnavailableError,
        MarketClosedError,
        InvalidPortfolioOrderError,
        PortfolioStateConflictError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
