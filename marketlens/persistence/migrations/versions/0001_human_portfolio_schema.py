"""Initial MarketLens human and participant-portfolio schema.

Revision ID: 0001_human_portfolio
Revises:
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_human_portfolio"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(), primary_key=True),
        sa.Column("participant_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("current_date", sa.String(), nullable=True),
        sa.Column("experiment_status", sa.String(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "current_step >= 0", name="ck_sessions_current_step_nonnegative"
        ),
    )

    op.create_table(
        "decisions",
        sa.Column("decision_id", sa.String(), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_sources", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.String(), nullable=False),
        sa.CheckConstraint("step >= 0", name="ck_decisions_step_nonnegative"),
        sa.CheckConstraint(
            "action IN ('BUY', 'HOLD', 'SELL')", name="ck_decisions_action"
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 100",
            name="ck_decisions_confidence_range",
        ),
        sa.UniqueConstraint(
            "session_id", "request_id", name="uq_decisions_session_request"
        ),
        sa.UniqueConstraint("session_id", "step", name="uq_decisions_session_step"),
    )

    op.create_table(
        "round_completions",
        sa.Column("completion_id", sa.String(), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("next_step", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.String(), nullable=False),
        sa.CheckConstraint("step >= 0", name="ck_round_completions_step_nonnegative"),
        sa.CheckConstraint("next_step > step", name="ck_round_completions_next_step"),
        sa.UniqueConstraint(
            "session_id", "request_id", name="uq_round_completions_session_request"
        ),
        sa.UniqueConstraint(
            "session_id", "step", name="uq_round_completions_session_step"
        ),
    )

    op.create_table(
        "participant_portfolios",
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("sessions.session_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("initial_cash", sa.Float(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "initial_cash >= 0", name="ck_portfolios_initial_cash_nonnegative"
        ),
        sa.CheckConstraint("cash >= 0", name="ck_portfolios_cash_nonnegative"),
    )

    op.create_table(
        "portfolio_holdings",
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("sessions.session_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("stock_id", sa.String(), primary_key=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "quantity >= 0", name="ck_holdings_quantity_nonnegative"
        ),
    )

    op.create_table(
        "portfolio_transactions",
        sa.Column("transaction_id", sa.String(), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("requested_amount", sa.Float(), nullable=False),
        sa.Column("requested_units", sa.Float(), nullable=False),
        sa.Column("executed_units", sa.Integer(), nullable=False),
        sa.Column("executed_notional", sa.Float(), nullable=False),
        sa.Column("settlement_price", sa.Float(), nullable=False),
        sa.Column("price_date", sa.String(), nullable=False),
        sa.Column("transaction_cost_bps", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column("cash_before", sa.Float(), nullable=False),
        sa.Column("cash_after", sa.Float(), nullable=False),
        sa.Column("holding_before", sa.Integer(), nullable=False),
        sa.Column("holding_after", sa.Integer(), nullable=False),
        sa.Column("portfolio_value_before", sa.Float(), nullable=False),
        sa.Column("portfolio_value_after", sa.Float(), nullable=False),
        sa.Column("weight_before", sa.Float(), nullable=False),
        sa.Column("weight_after", sa.Float(), nullable=False),
        sa.Column("submitted_at", sa.String(), nullable=False),
        sa.CheckConstraint("step >= 0", name="ck_transactions_step_nonnegative"),
        sa.CheckConstraint("action IN ('BUY', 'SELL')", name="ck_transactions_action"),
        sa.CheckConstraint(
            "requested_amount > 0", name="ck_transactions_requested_amount"
        ),
        sa.CheckConstraint(
            "requested_units > 0", name="ck_transactions_requested_units"
        ),
        sa.CheckConstraint(
            "executed_units > 0", name="ck_transactions_executed_units"
        ),
        sa.CheckConstraint(
            "executed_notional > 0", name="ck_transactions_executed_notional"
        ),
        sa.CheckConstraint(
            "settlement_price > 0", name="ck_transactions_settlement_price"
        ),
        sa.CheckConstraint(
            "transaction_cost_bps >= 0",
            name="ck_transactions_cost_bps_nonnegative",
        ),
        sa.CheckConstraint("fee >= 0", name="ck_transactions_fee_nonnegative"),
        sa.CheckConstraint(
            "cash_before >= 0", name="ck_transactions_cash_before_nonnegative"
        ),
        sa.CheckConstraint(
            "cash_after >= 0", name="ck_transactions_cash_after_nonnegative"
        ),
        sa.CheckConstraint(
            "holding_before >= 0", name="ck_transactions_holding_before_nonnegative"
        ),
        sa.CheckConstraint(
            "holding_after >= 0", name="ck_transactions_holding_after_nonnegative"
        ),
        sa.CheckConstraint(
            "portfolio_value_before >= 0",
            name="ck_transactions_value_before_nonnegative",
        ),
        sa.CheckConstraint(
            "portfolio_value_after >= 0",
            name="ck_transactions_value_after_nonnegative",
        ),
        sa.CheckConstraint(
            "weight_before >= 0", name="ck_transactions_weight_before_nonnegative"
        ),
        sa.CheckConstraint(
            "weight_after >= 0", name="ck_transactions_weight_after_nonnegative"
        ),
        sa.UniqueConstraint(
            "session_id", "request_id", name="uq_transactions_session_request"
        ),
    )


def downgrade() -> None:
    op.drop_table("portfolio_transactions")
    op.drop_table("portfolio_holdings")
    op.drop_table("participant_portfolios")
    op.drop_table("round_completions")
    op.drop_table("decisions")
    op.drop_table("sessions")
