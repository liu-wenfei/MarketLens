from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

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
from marketlens.human.stores.portfolio_store import PortfolioStore
from marketlens.market.asset_catalog import AssetNotFoundError

router = APIRouter()


def get_portfolio_service(request: Request) -> PortfolioService:
    return PortfolioService(
        store=PortfolioStore(request.app.state.db),
        assets=request.app.state.asset_catalog,
        prices=request.app.state.price_provider,
        policy=request.app.state.portfolio_policy,
        calendar=request.app.state.trading_calendar,
    )


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
    service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioOrderPreviewRead:
    try:
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
    service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioTransactionRead:
    try:
        return service.submit(session_id, payload)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown asset") from exc
    except (
        IdempotencyConflictError,
        WrongPortfolioStepError,
        MarketDateUnavailableError,
        MarketClosedError,
        InvalidPortfolioOrderError,
        PortfolioStateConflictError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
