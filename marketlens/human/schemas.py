from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DecisionAction(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


class SessionCreate(BaseModel):
    participant_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    participant_id: str
    created_at: datetime
    current_step: int
    current_date: str | None
    experiment_status: str
    completed: bool


class SessionState(BaseModel):
    session_id: str
    current_step: int
    current_date: str | None
    experiment_status: str
    completed: bool


class DecisionCreate(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    step: int = Field(ge=0)
    stock_id: str = Field(min_length=1, max_length=64)
    action: DecisionAction
    confidence: float = Field(ge=0.0, le=100.0)
    evidence_sources: list[str] = Field(default_factory=list)
    rationale: str | None = Field(default=None, max_length=5000)


class DecisionRead(BaseModel):
    decision_id: str
    session_id: str
    request_id: str
    step: int
    stock_id: str
    action: DecisionAction
    confidence: float
    evidence_sources: list[str]
    rationale: str | None
    submitted_at: datetime


class RoundComplete(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    step: int = Field(ge=0)


class RoundCompletionRead(BaseModel):
    completion_id: str
    session_id: str
    request_id: str
    step: int
    next_step: int
    completed_at: datetime


class PortfolioAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class PortfolioOrderPreviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int = Field(ge=0)
    stock_id: str = Field(min_length=1, max_length=64)
    action: PortfolioAction
    amount: float = Field(gt=0)


class PortfolioOrderCreate(PortfolioOrderPreviewCreate):
    request_id: str = Field(min_length=1, max_length=128)


class PortfolioOrderPreviewRead(BaseModel):
    session_id: str
    step: int
    price_date: str
    stock_id: str
    action: PortfolioAction
    settlement_price: float
    requested_amount: float
    requested_units: float
    executable_units: int
    executed_notional: float
    fee: float
    cash_before: float
    cash_after: float
    holding_before: int
    holding_after: int
    portfolio_value_before: float
    portfolio_value_after: float
    weight_before: float
    weight_after: float
    valid: bool
    reason_code: str
    maximum_valid_amount: float | None


class PortfolioTransactionRead(BaseModel):
    transaction_id: str
    session_id: str
    request_id: str
    step: int
    stock_id: str
    action: PortfolioAction
    requested_amount: float
    requested_units: float
    executed_units: int
    executed_notional: float
    settlement_price: float
    price_date: str
    transaction_cost_bps: float
    fee: float
    cash_before: float
    cash_after: float
    holding_before: int
    holding_after: int
    portfolio_value_before: float
    portfolio_value_after: float
    weight_before: float
    weight_after: float
    submitted_at: datetime


class PortfolioHoldingRead(BaseModel):
    stock_id: str
    name: str
    quantity: int
    current_price: float
    market_value: float
    portfolio_weight: float


class PortfolioRead(BaseModel):
    session_id: str
    step: int
    price_date: str | None
    initial_cash: float
    cash: float
    total_value: float
    holdings: list[PortfolioHoldingRead]
