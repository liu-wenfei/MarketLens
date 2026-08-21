from __future__ import annotations

from pydantic import BaseModel


class AssetRead(BaseModel):
    stock_id: str
    market_weight: float
    name: str
    industry: str
    description: str
