"""Add formal participant judgement and orchestration state.

Revision ID: 0003_participant_experiment_orchestration
Revises: 0002_participant_episode_assignment
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_participant_experiment_orchestration"
down_revision: str | None = "0002_participant_episode_assignment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("current_stage", sa.String(), nullable=True))
    op.create_table(
        "participant_judgements",
        sa.Column("judgement_id", sa.String(), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("participant_id", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("judgement_event", sa.String(), nullable=False),
        sa.Column("experiment_step", sa.Integer(), nullable=False),
        sa.Column("agent_world_date", sa.String(), nullable=False),
        sa.Column("stock_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_sources", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "judgement_event IN ('J0', 'J1', 'J2', 'J3', 'J4')",
            name="ck_participant_judgements_event",
        ),
        sa.CheckConstraint(
            "experiment_step >= 0",
            name="ck_participant_judgements_step_nonnegative",
        ),
        sa.CheckConstraint(
            "action IN ('BUY', 'HOLD', 'SELL')",
            name="ck_participant_judgements_action",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 100",
            name="ck_participant_judgements_confidence_range",
        ),
        sa.UniqueConstraint(
            "session_id", "request_id",
            name="uq_participant_judgements_session_request",
        ),
        sa.UniqueConstraint(
            "session_id", "judgement_event",
            name="uq_participant_judgements_session_event",
        ),
    )


def downgrade() -> None:
    op.drop_table("participant_judgements")
    op.drop_column("sessions", "current_stage")
