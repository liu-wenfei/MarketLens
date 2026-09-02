from __future__ import annotations

from marketlens.human.routers.feedback import router as feedback_router
from marketlens.human.routers.journey import router as journey_router

from pathlib import Path
from typing import Mapping, Sequence

from fastapi import FastAPI

from marketlens.episode.contract import (
    EPISODE_IDS as DEFAULT_EPISODE_IDS,
    EPISODE_POOL_ID as DEFAULT_EPISODE_POOL_ID,
)

from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.portfolio.policy import PortfolioPolicy
from marketlens.human.routers.background import router as background_router
from marketlens.human.routers.decision import router as decision_router
from marketlens.human.routers.exposure import router as exposure_router
from marketlens.human.routers.judgement import router as judgement_router
from marketlens.human.routers.portfolio import router as portfolio_router
from marketlens.human.routers.market_overview import router as market_overview_router
from marketlens.human.routers.round import router as round_router
from marketlens.human.routers.session import router as session_router
from marketlens.human.runtime import build_participant_runtime
from marketlens.human.services.journey_provider_factory import (
    build_canonical_journey_price_providers,
)
from marketlens.information.projection import ParticipantBackgroundProjection
from marketlens.market.asset_catalog import AssetCatalog
from marketlens.market.price_provider import CsvClosePriceProvider
from marketlens.market.status import TradingCalendar
from marketlens.market.router import router as market_router
from marketlens.persistence.config import (
    resolve_auto_create_schema,
    resolve_database_url,
)
from marketlens.persistence.database import Database
from marketlens.stimulus.engine import StimulusEngine


def create_app(
    db_path: str | Path | None = None,
    *,
    database_url: str | None = None,
    initialize_database: bool | None = None,
    portfolio_policy: PortfolioPolicy | None = None,
    background_projection: ParticipantBackgroundProjection | None = None,
    participant_runtime_enabled: bool = False,
    participant_event_store: ParticipantEventStore | None = None,
    background_projections: Mapping[str, ParticipantBackgroundProjection] | None = None,
    stimulus_engine: StimulusEngine | None = None,
    journey_price_providers: Mapping[str, object] | None = None,
    participant_episode_pool_id: str = DEFAULT_EPISODE_POOL_ID,
    participant_episode_ids: Sequence[str] = DEFAULT_EPISODE_IDS,
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

    # Legacy/non-formal projection injection is preserved for the existing
    # read-only GET endpoint when participant runtime wiring is disabled.
    app.state.background_projection = background_projection

    app.state.participant_runtime = None
    if participant_runtime_enabled:
        if participant_event_store is None:
            raise ValueError(
                "participant_runtime_enabled requires an explicit ParticipantEventStore"
            )
        if background_projections is None:
            raise ValueError(
                "participant_runtime_enabled requires episode-keyed background_projections"
            )
        if stimulus_engine is None:
            raise ValueError(
                "participant_runtime_enabled requires an explicit formal StimulusEngine"
            )
        resolved_journey_price_providers = (
            dict(journey_price_providers)
            if journey_price_providers is not None
            else build_canonical_journey_price_providers(
                Path(__file__).resolve().parents[1]
            )
        )
        app.state.participant_runtime = build_participant_runtime(
            db=app.state.db,
            calendar=app.state.trading_calendar,
            events=participant_event_store,
            background_projections=background_projections,
            stimulus_engine=stimulus_engine,
            journey_price_providers=resolved_journey_price_providers,
            episode_pool_id=participant_episode_pool_id,
            expected_episode_ids=participant_episode_ids,
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "marketlens-human-backend"}

    app.include_router(market_router)
    app.include_router(background_router)
    app.include_router(exposure_router)
    app.include_router(session_router)
    app.include_router(decision_router)
    app.include_router(judgement_router)
    app.include_router(portfolio_router)
    app.include_router(market_overview_router)
    app.include_router(round_router)
    app.include_router(feedback_router)
    app.include_router(journey_router)

    return app


app = create_app()
