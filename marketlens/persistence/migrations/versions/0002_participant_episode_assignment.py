"""Add participant-to-canonical-episode assignment binding.

Revision ID: 0002_participant_episode_assignment
Revises: 0001_human_portfolio
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_participant_episode_assignment"
down_revision: str | None = "0001_human_portfolio"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "participant_episode_assignments",
        sa.Column("assignment_id", sa.String(), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(),
            sa.ForeignKey("sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("participant_id", sa.String(), nullable=False),
        sa.Column("episode_pool_id", sa.String(), nullable=False),
        sa.Column("episode_id", sa.String(), nullable=False),
        sa.Column("assignment_method", sa.String(), nullable=False),
        sa.Column("assignment_version", sa.String(), nullable=False),
        sa.Column("assigned_at", sa.String(), nullable=False),
        sa.UniqueConstraint(
            "session_id", name="uq_participant_episode_assignments_session"
        ),
    )


def downgrade() -> None:
    op.drop_table("participant_episode_assignments")
