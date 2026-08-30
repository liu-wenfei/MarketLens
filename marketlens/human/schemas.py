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


class ParticipantSessionCreate(BaseModel):
    """Formal participant bootstrap payload; episode allocation is server-owned."""

    model_config = ConfigDict(extra="forbid")

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
    market_open: bool
    market_status_reason: str
    current_market_date: str | None
    next_trading_date: str | None
    closure_start_date: str | None
    closure_end_date: str | None
    participant_trading_enabled: bool
    market_state_date: str | None


class ParticipantRequiredAction(str, Enum):
    LOAD_MARKET_INFORMATION = "LOAD_MARKET_INFORMATION"
    LOAD_INFORMATION_UPDATE = "LOAD_INFORMATION_UPDATE"
    SUBMIT_ASSESSMENT = "SUBMIT_ASSESSMENT"
    ROUND_ACTIVE = "ROUND_ACTIVE"
    COMPLETED = "COMPLETED"


class ParticipantAssessmentMode(str, Enum):
    PRE_UPDATE = "PRE_UPDATE"
    POST_UPDATE = "POST_UPDATE"
    LATER = "LATER"


class ParticipantAllowedActions(BaseModel):
    load_market_information: bool
    load_information_update: bool
    submit_assessment: bool
    view_portfolio: bool
    preview_trade: bool
    submit_trade: bool
    complete_round: bool


class ParticipantMarketView(BaseModel):
    market_open: bool
    market_status_reason: str
    current_market_date: str | None
    next_trading_date: str | None
    closure_start_date: str | None
    closure_end_date: str | None
    market_state_date: str | None
    trading_enabled_by_market: bool


class ParticipantViewState(BaseModel):
    contract_version: str
    session_id: str
    current_step_assertion: int
    period_number: int
    period_count: int
    current_date: str
    experiment_status: str
    completed: bool
    assessment_target_stock_id: str
    required_action: ParticipantRequiredAction
    assessment_mode: ParticipantAssessmentMode | None
    market: ParticipantMarketView
    allowed_actions: ParticipantAllowedActions


class ParticipantInformationUpdateRead(BaseModel):
    session_id: str
    current_date: str
    headline: str
    body: str
    source_label: str
    source_descriptor: str


class ParticipantAssessmentCreate(BaseModel):
    """Phase 15 participant-safe assessment payload; target/provenance are server-owned."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)
    action: DecisionAction
    confidence: float = Field(ge=0.0, le=100.0)
    evidence_sources: list[str] = Field(default_factory=list)
    rationale: str | None = Field(default=None, max_length=5000)


class ParticipantAssessmentRead(BaseModel):
    assessment_id: str
    session_id: str
    request_id: str
    assessment_target_stock_id: str
    assessment_mode: ParticipantAssessmentMode
    action: DecisionAction
    confidence: float
    evidence_sources: list[str]
    rationale: str | None
    submitted_at: datetime


class ParticipantForumPostRead(BaseModel):
    post_id: int
    author_id: str
    source_label: str
    display_text: str
    created_at: str


class ParticipantBackgroundRead(BaseModel):
    session_id: str
    current_date: str
    natural_news: list[str]
    forum_posts: list[ParticipantForumPostRead]


class ExposureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)


class ParticipantControlledStimulusRead(BaseModel):
    session_id: str
    current_date: str
    stimulus_id: str
    kind: str
    headline: str
    body: str
    corrects_stimulus_id: str | None
    source_label: str
    source_descriptor: str


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


class JudgementCreate(BaseModel):
    """Participant response payload; event/step/date/stage are server-derived."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)
    stock_id: str = Field(min_length=1, max_length=64)
    action: DecisionAction
    confidence: float = Field(ge=0.0, le=100.0)
    evidence_sources: list[str] = Field(default_factory=list)
    rationale: str | None = Field(default=None, max_length=5000)


class JudgementRead(BaseModel):
    judgement_id: str
    session_id: str
    participant_id: str
    request_id: str
    judgement_event: str
    experiment_step: int
    agent_world_date: str
    stock_id: str
    action: DecisionAction
    confidence: float
    evidence_sources: list[str]
    rationale: str | None
    submitted_at: datetime


class RoundComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)
    step: int = Field(ge=0)


class RoundCompletionRead(BaseModel):
    completion_id: str
    session_id: str
    request_id: str
    step: int
    next_step: int | None
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


class ParticipantFeedbackRead(BaseModel):
    """Participant-safe feedback projection.

    Internal checkpoint identity, hashes, prompt/model provenance and
    feedback IDs are deliberately not exposed.
    """

    model_config = ConfigDict(extra="forbid")

    feedback_kind: str
    statistics: dict[str, object]
    reflection: str


class ParticipantFeedbackContinueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=128)


class ParticipantFeedbackContinueRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    continued: bool


class ParticipantJourneyJudgementRead(BaseModel):
    """Participant-safe historical judgement projection."""

    model_config = ConfigDict(extra="forbid")

    sequence_within_period: int
    stock_id: str
    action: str
    confidence: float
    evidence_sources: tuple[str, ...]
    rationale: str | None
    submitted_at: str


class ParticipantJourneyTransactionRead(BaseModel):
    """Participant-safe settled transaction projection."""

    model_config = ConfigDict(extra="forbid")

    sequence_within_period: int
    transaction_id: str
    stock_id: str
    action: str

    requested_amount: float | None
    requested_units: float | None

    executed_units: int
    executed_notional: float
    settlement_price: float
    fee: float

    cash_before: float
    cash_after: float

    holding_before: int
    holding_after: int

    submitted_at: str


class ParticipantJourneyPortfolioSnapshotRead(BaseModel):
    """Participant-safe end-of-period portfolio projection."""

    model_config = ConfigDict(extra="forbid")

    cash: float
    holdings: dict[str, int]
    portfolio_value: float


class ParticipantJourneyPeriodRead(BaseModel):
    """Participant-safe historical Period projection."""

    model_config = ConfigDict(extra="forbid")

    period_number: int
    agent_world_date: str

    market_open: bool
    participant_trading_enabled: bool

    judgements: tuple[ParticipantJourneyJudgementRead, ...]
    transactions: tuple[ParticipantJourneyTransactionRead, ...]

    behaviour_summary: str
    holding_changes: dict[str, int]

    portfolio_end: ParticipantJourneyPortfolioSnapshotRead

    period_pnl: float
    cumulative_pnl: float
    pnl_direction: str

    feedback_boundary: str


class ParticipantDecisionJourneyRead(BaseModel):
    """Participant-safe accumulated decision-journey projection.

    Internal round-lock state, canonical close-price inputs, episode identity,
    provider provenance and formal artifact paths are deliberately not exposed.
    """

    model_config = ConfigDict(extra="forbid")

    journey_version: str
    target_stock_id: str

    initial_cash: float
    initial_holdings: dict[str, int]
    initial_portfolio_value: float

    periods: tuple[ParticipantJourneyPeriodRead, ...]
