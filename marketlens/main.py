from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from marketlens.human.portfolio.policy import PortfolioPolicy
from marketlens.human.routers.decision import router as decision_router
from marketlens.human.routers.portfolio import router as portfolio_router
from marketlens.human.routers.round import router as round_router
from marketlens.human.routers.session import router as session_router
from marketlens.market.asset_catalog import AssetCatalog
from marketlens.market.price_provider import CsvClosePriceProvider
from marketlens.market.status import TradingCalendar
from marketlens.market.router import router as market_router
from marketlens.persistence.config import (
    resolve_auto_create_schema,
    resolve_database_url,
)
from marketlens.persistence.database import Database


def create_app(
    db_path: str | Path | None = None,
    *,
    database_url: str | None = None,
    initialize_database: bool | None = None,
    portfolio_policy: PortfolioPolicy | None = None,
) -> FastAPI:
    app = FastAPI(title="MarketLens Human Backend", version="0.2.1")

    resolved_database_url = resolve_database_url(
        explicit_url=database_url,
        legacy_path=db_path,
    )
    app.state.db = Database(
        resolved_database_url,
        initialize=resolve_auto_create_schema(initialize_database),
    )
    app.state.asset_catalog = AssetCatalog()
    app.state.price_provider = CsvClosePriceProvider()
    app.state.trading_calendar = TradingCalendar()
    app.state.portfolio_policy = portfolio_policy or PortfolioPolicy()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "marketlens-human-backend"}

    app.include_router(market_router)
    app.include_router(session_router)
    app.include_router(decision_router)
    app.include_router(portfolio_router)
    app.include_router(round_router)
    return app


app = create_app()
