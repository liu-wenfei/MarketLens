from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from marketlens.human.routers.decision import router as decision_router
from marketlens.human.routers.session import router as session_router
from marketlens.human.stores.database import Database


def create_app(db_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="MarketLens Human Backend", version="0.1.0")

    resolved_db_path = Path(
        db_path
        or os.environ.get(
            "MARKETLENS_DB_PATH",
            Path(__file__).resolve().parent
            / "human"
            / "data"
            / "marketlens_human.db",
        )
    )
    app.state.db = Database(resolved_db_path)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "marketlens-human-backend"}

    app.include_router(session_router)
    app.include_router(decision_router)
    return app


app = create_app()
