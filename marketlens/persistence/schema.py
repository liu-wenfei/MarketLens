from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)


metadata = MetaData()

sessions = Table(
    "sessions",
    metadata,
    Column("session_id", String, primary_key=True),
    Column("participant_id", String, nullable=False),
    Column("request_id", String, nullable=False, unique=True),
    Column("created_at", String, nullable=False),
    Column("current_step", Integer, nullable=False, default=0),
    Column("current_date", String, nullable=True),
    Column("current_stage", String, nullable=True),
    Column("experiment_status", String, nullable=False, default="active"),
    Column("completed", Boolean, nullable=False, default=False),
    CheckConstraint("current_step >= 0", name="ck_sessions_current_step_nonnegative"),
)

participant_episode_assignments = Table(
    "participant_episode_assignments",
    metadata,
    Column("assignment_id", String, primary_key=True),
    Column(
        "session_id",
        String,
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("participant_id", String, nullable=False),
    Column("episode_pool_id", String, nullable=False),
    Column("episode_id", String, nullable=False),
    Column("assignment_method", String, nullable=False),
    Column("assignment_version", String, nullable=False),
    Column("assigned_at", String, nullable=False),
    UniqueConstraint(
        "session_id", name="uq_participant_episode_assignments_session"
    ),
)

decisions = Table(
    "decisions",
    metadata,
    Column("decision_id", String, primary_key=True),
    Column(
        "session_id",
        String,
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("request_id", String, nullable=False),
    Column("step", Integer, nullable=False),
    Column("stock_id", String, nullable=False),
    Column("action", String, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("evidence_sources", Text, nullable=False),
    Column("rationale", Text, nullable=True),
    Column("submitted_at", String, nullable=False),
    CheckConstraint("step >= 0", name="ck_decisions_step_nonnegative"),
    CheckConstraint(
        "action IN ('BUY', 'HOLD', 'SELL')",
        name="ck_decisions_action",
    ),
    CheckConstraint(
        "confidence >= 0 AND confidence <= 100",
        name="ck_decisions_confidence_range",
    ),
    UniqueConstraint("session_id", "request_id", name="uq_decisions_session_request"),
    UniqueConstraint("session_id", "step", name="uq_decisions_session_step"),
)

participant_judgements = Table(
    "participant_judgements",
    metadata,
    Column("judgement_id", String, primary_key=True),
    Column(
        "session_id",
        String,
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("participant_id", String, nullable=False),
    Column("request_id", String, nullable=False),
    Column("judgement_event", String, nullable=False),
    Column("experiment_step", Integer, nullable=False),
    Column("agent_world_date", String, nullable=False),
    Column("stock_id", String, nullable=False),
    Column("action", String, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("evidence_sources", Text, nullable=False),
    Column("rationale", Text, nullable=True),
    Column("submitted_at", String, nullable=False),
    CheckConstraint(
        "judgement_event IN ('J0', 'J1', 'J2', 'J3', 'J4')",
        name="ck_participant_judgements_event",
    ),
    CheckConstraint(
        "experiment_step >= 0",
        name="ck_participant_judgements_step_nonnegative",
    ),
    CheckConstraint(
        "action IN ('BUY', 'HOLD', 'SELL')",
        name="ck_participant_judgements_action",
    ),
    CheckConstraint(
        "confidence >= 0 AND confidence <= 100",
        name="ck_participant_judgements_confidence_range",
    ),
    UniqueConstraint(
        "session_id", "request_id", name="uq_participant_judgements_session_request"
    ),
    UniqueConstraint(
        "session_id", "judgement_event", name="uq_participant_judgements_session_event"
    ),
)

round_completions = Table(
    "round_completions",
    metadata,
    Column("completion_id", String, primary_key=True),
    Column(
        "session_id",
        String,
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("request_id", String, nullable=False),
    Column("step", Integer, nullable=False),
    Column("next_step", Integer, nullable=True),
    Column("completed_at", String, nullable=False),
    CheckConstraint("step >= 0", name="ck_round_completions_step_nonnegative"),
    CheckConstraint(
        "next_step IS NULL OR next_step > step",
        name="ck_round_completions_next_step",
    ),
    UniqueConstraint(
        "session_id", "request_id", name="uq_round_completions_session_request"
    ),
    UniqueConstraint("session_id", "step", name="uq_round_completions_session_step"),
)

participant_portfolios = Table(
    "participant_portfolios",
    metadata,
    Column(
        "session_id",
        String,
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("initial_cash", Float, nullable=False),
    Column("cash", Float, nullable=False),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
    CheckConstraint("initial_cash >= 0", name="ck_portfolios_initial_cash_nonnegative"),
    CheckConstraint("cash >= 0", name="ck_portfolios_cash_nonnegative"),
)

portfolio_holdings = Table(
    "portfolio_holdings",
    metadata,
    Column(
        "session_id",
        String,
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("stock_id", String, primary_key=True),
    Column("quantity", Integer, nullable=False),
    Column("updated_at", String, nullable=False),
    CheckConstraint("quantity >= 0", name="ck_holdings_quantity_nonnegative"),
)

portfolio_transactions = Table(
    "portfolio_transactions",
    metadata,
    Column("transaction_id", String, primary_key=True),
    Column(
        "session_id",
        String,
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("request_id", String, nullable=False),
    Column("step", Integer, nullable=False),
    Column("stock_id", String, nullable=False),
    Column("action", String, nullable=False),
    Column("requested_amount", Float, nullable=False),
    Column("requested_units", Float, nullable=False),
    Column("executed_units", Integer, nullable=False),
    Column("executed_notional", Float, nullable=False),
    Column("settlement_price", Float, nullable=False),
    Column("price_date", String, nullable=False),
    Column("transaction_cost_bps", Float, nullable=False),
    Column("fee", Float, nullable=False),
    Column("cash_before", Float, nullable=False),
    Column("cash_after", Float, nullable=False),
    Column("holding_before", Integer, nullable=False),
    Column("holding_after", Integer, nullable=False),
    Column("portfolio_value_before", Float, nullable=False),
    Column("portfolio_value_after", Float, nullable=False),
    Column("weight_before", Float, nullable=False),
    Column("weight_after", Float, nullable=False),
    Column("submitted_at", String, nullable=False),
    CheckConstraint("step >= 0", name="ck_transactions_step_nonnegative"),
    CheckConstraint("action IN ('BUY', 'SELL')", name="ck_transactions_action"),
    CheckConstraint("requested_amount > 0", name="ck_transactions_requested_amount"),
    CheckConstraint("requested_units > 0", name="ck_transactions_requested_units"),
    CheckConstraint("executed_units > 0", name="ck_transactions_executed_units"),
    CheckConstraint("executed_notional > 0", name="ck_transactions_executed_notional"),
    CheckConstraint("settlement_price > 0", name="ck_transactions_settlement_price"),
    CheckConstraint(
        "transaction_cost_bps >= 0", name="ck_transactions_cost_bps_nonnegative"
    ),
    CheckConstraint("fee >= 0", name="ck_transactions_fee_nonnegative"),
    CheckConstraint("cash_before >= 0", name="ck_transactions_cash_before_nonnegative"),
    CheckConstraint("cash_after >= 0", name="ck_transactions_cash_after_nonnegative"),
    CheckConstraint(
        "holding_before >= 0", name="ck_transactions_holding_before_nonnegative"
    ),
    CheckConstraint(
        "holding_after >= 0", name="ck_transactions_holding_after_nonnegative"
    ),
    CheckConstraint(
        "portfolio_value_before >= 0",
        name="ck_transactions_value_before_nonnegative",
    ),
    CheckConstraint(
        "portfolio_value_after >= 0",
        name="ck_transactions_value_after_nonnegative",
    ),
    CheckConstraint("weight_before >= 0", name="ck_transactions_weight_before_nonnegative"),
    CheckConstraint("weight_after >= 0", name="ck_transactions_weight_after_nonnegative"),
    UniqueConstraint(
        "session_id", "request_id", name="uq_transactions_session_request"
    ),
)
