from __future__ import annotations

from math import isclose, isfinite

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
from marketlens.human.services.market_overview_service import (
    ParticipantMarketOverviewInvariantError,
    ParticipantMarketOverviewService,
    ParticipantMarketOverviewUnavailableError,
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


class PortfolioPeriodPnlUnavailableError(ValueError):
    """A safe previous-Period portfolio baseline is unavailable."""


def _previous_locked_portfolio_value(
    *,
    session_id: str,
    current_step: int,
    runtime: object,
    overview: object,
) -> float:
    """Reconstruct the previous locked Period's portfolio end value.

    This deliberately does NOT build the current full Decision Journey.

    Historical participant cash/holdings are reconstructed only from
    settled transactions in already-completed steps. Those positions
    are then marked to the immediately previous participant-visible
    canonical market checkpoint.

    Current-step transactions are ignored for the historical baseline.
    """

    if current_step <= 0:
        raise PortfolioPeriodPnlUnavailableError(
            "P1 has no previous Period portfolio baseline"
        )

    portfolios = runtime.journey.portfolios
    rounds = runtime.journey.rounds

    portfolio_row = portfolios.get_portfolio(
        session_id
    )

    if portfolio_row is None:
        raise PortfolioPeriodPnlUnavailableError(
            "authoritative participant portfolio is missing"
        )

    initial_cash = float(
        portfolio_row["initial_cash"]
    )

    if (
        not isfinite(initial_cash)
        or initial_cash < 0.0
    ):
        raise PortfolioPeriodPnlUnavailableError(
            "participant initial cash is invalid"
        )

    locked_rows = tuple(
        rounds.list_for_session(
            session_id
        )
    )

    locked_steps = {
        int(row["step"])
        for row in locked_rows
    }

    required_locked_steps = set(
        range(current_step)
    )

    if not required_locked_steps.issubset(
        locked_steps
    ):
        raise PortfolioPeriodPnlUnavailableError(
            "previous participant Periods are not "
            "contiguously behaviour-locked"
        )

    cash = initial_cash
    positions: dict[str, int] = {}

    transactions = tuple(
        portfolios.list_transactions_for_session(
            session_id
        )
    )

    for transaction in transactions:
        transaction_step = int(
            transaction["step"]
        )

        if transaction_step < 0:
            raise PortfolioPeriodPnlUnavailableError(
                "transaction step is invalid"
            )

        if transaction_step > current_step:
            raise PortfolioPeriodPnlUnavailableError(
                "authoritative transaction exists "
                "beyond the current participant step"
            )

        # Current-period transactions are real and remain in the
        # current PortfolioRead, but they must never contaminate
        # the previous Period baseline.
        if transaction_step == current_step:
            continue

        if transaction_step not in required_locked_steps:
            raise PortfolioPeriodPnlUnavailableError(
                "historical transaction does not belong "
                "to a locked participant Period"
            )

        stock_id = str(
            transaction["stock_id"]
        ).strip()

        if not stock_id:
            raise PortfolioPeriodPnlUnavailableError(
                "historical transaction stock_id is empty"
            )

        cash_before = float(
            transaction["cash_before"]
        )

        cash_after = float(
            transaction["cash_after"]
        )

        if (
            not isfinite(cash_before)
            or not isfinite(cash_after)
        ):
            raise PortfolioPeriodPnlUnavailableError(
                "historical transaction cash is invalid"
            )

        if not isclose(
            cash,
            cash_before,
            rel_tol=1e-9,
            abs_tol=1e-6,
        ):
            raise PortfolioPeriodPnlUnavailableError(
                "historical transaction cash continuity mismatch"
            )

        holding_before = int(
            transaction["holding_before"]
        )

        holding_after = int(
            transaction["holding_after"]
        )

        current_holding = positions.get(
            stock_id,
            0,
        )

        if (
            current_holding
            != holding_before
        ):
            raise PortfolioPeriodPnlUnavailableError(
                "historical transaction holding continuity mismatch"
            )

        cash = cash_after

        if holding_after == 0:
            positions.pop(
                stock_id,
                None,
            )
        else:
            positions[
                stock_id
            ] = holding_after

    previous_closes: dict[
        str,
        float,
    ] = {}

    previous_participant_dates: set[
        str
    ] = set()

    previous_price_dates: set[
        str
    ] = set()

    for asset in overview.assets:
        history = tuple(
            asset.price_history
        )

        if len(history) < 2:
            raise PortfolioPeriodPnlUnavailableError(
                "previous participant-visible market "
                "checkpoint is unavailable"
            )

        current_point = history[-1]
        previous_point = history[-2]

        if (
            str(current_point.participant_date)
            != str(overview.current_date)
            or str(current_point.price_date)
            != str(overview.price_date)
        ):
            raise PortfolioPeriodPnlUnavailableError(
                "current market overview history is misaligned"
            )

        previous_close = float(
            previous_point.close
        )

        if (
            not isfinite(previous_close)
            or previous_close <= 0.0
        ):
            raise PortfolioPeriodPnlUnavailableError(
                "previous canonical close price is invalid"
            )

        stock_id = str(
            asset.stock_id
        )

        previous_closes[
            stock_id
        ] = previous_close

        previous_participant_dates.add(
            str(
                previous_point.participant_date
            )
        )

        previous_price_dates.add(
            str(
                previous_point.price_date
            )
        )

    if (
        len(previous_participant_dates) != 1
        or len(previous_price_dates) != 1
    ):
        raise PortfolioPeriodPnlUnavailableError(
            "previous market checkpoint is not aligned "
            "across the investable asset universe"
        )

    previous_value = cash

    for stock_id, quantity in (
        positions.items()
    ):
        try:
            close = previous_closes[
                stock_id
            ]
        except KeyError as exc:
            raise PortfolioPeriodPnlUnavailableError(
                "previous canonical close is missing "
                f"for held asset {stock_id!r}"
            ) from exc

        previous_value += (
            int(quantity)
            * close
        )

    if (
        not isfinite(previous_value)
        or previous_value < 0.0
    ):
        raise PortfolioPeriodPnlUnavailableError(
            "previous locked Period portfolio value is invalid"
        )

    return previous_value


def _current_period_pnl(
    portfolio: PortfolioRead,
    previous_value: float | None,
) -> tuple[float | None, float | None]:
    """Return descriptive current Period P/L from an authoritative baseline."""

    if int(portfolio.step) <= 0:
        return None, None

    if previous_value is None:
        raise PortfolioPeriodPnlUnavailableError(
            "previous locked Period portfolio value is unavailable"
        )

    previous_value = float(
        previous_value
    )

    current_value = float(
        portfolio.total_value
    )

    if (
        not isfinite(previous_value)
        or not isfinite(current_value)
        or previous_value < 0.0
        or current_value < 0.0
    ):
        raise PortfolioPeriodPnlUnavailableError(
            "portfolio value is invalid for Period P/L"
        )

    period_pnl = (
        current_value
        - previous_value
    )

    period_pnl_pct = (
        None
        if previous_value == 0.0
        else (
            period_pnl
            / previous_value
            * 100.0
        )
    )

    return (
        period_pnl,
        period_pnl_pct,
    )


@router.get(
    "/session/{session_id}/portfolio",
    response_model=PortfolioRead,
)
def get_portfolio(
    session_id: str,
    request: Request,
    service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioRead:
    try:
        portfolio = service.get_portfolio(
            session_id
        )

        runtime = getattr(
            request.app.state,
            "participant_runtime",
            None,
        )

        if runtime is None:
            return portfolio

        if int(portfolio.step) <= 0:
            return portfolio.model_copy(
                update={
                    "period_pnl": None,
                    "period_pnl_pct": None,
                }
            )

        overview_service = (
            ParticipantMarketOverviewService(
                context=runtime.context,
                orchestration=runtime.orchestration,
                assets=request.app.state.asset_catalog,
                price_providers=runtime.journey.price_providers,
                calendar=request.app.state.trading_calendar,
            )
        )

        overview = overview_service.get(
            session_id
        )

        previous_value = (
            _previous_locked_portfolio_value(
                session_id=session_id,
                current_step=int(
                    portfolio.step
                ),
                runtime=runtime,
                overview=overview,
            )
        )

        (
            period_pnl,
            period_pnl_pct,
        ) = _current_period_pnl(
            portfolio,
            previous_value,
        )

        return portfolio.model_copy(
            update={
                "period_pnl": period_pnl,
                "period_pnl_pct": period_pnl_pct,
            }
        )

    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Unknown session",
        ) from exc

    except (
        MarketDateUnavailableError,
        PortfolioPeriodPnlUnavailableError,
        ParticipantMarketOverviewUnavailableError,
        ParticipantMarketOverviewInvariantError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

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
