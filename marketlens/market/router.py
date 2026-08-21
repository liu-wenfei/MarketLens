from __future__ import annotations

from fastapi import APIRouter, Request

from marketlens.market.schemas import AssetRead

router = APIRouter()


@router.get("/assets", response_model=list[AssetRead])
def list_assets(request: Request) -> list[AssetRead]:
    return [
        AssetRead(
            stock_id=asset.stock_id,
            market_weight=asset.market_weight,
            name=asset.name,
            industry=asset.industry,
            description=asset.description,
        )
        for asset in request.app.state.asset_catalog.all()
    ]
