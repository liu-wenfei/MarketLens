"""Allow terminal protocol round completion without inventing a next step.

Revision ID: 0004_protocol_round_completion
Revises: 0003_participant_experiment_orchestration
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_protocol_round_completion"
down_revision: str | None = "0003_participant_experiment_orchestration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _upgrade_sqlite() -> None:
    with op.batch_alter_table("round_completions", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "ck_round_completions_next_step",
            type_="check",
        )
        batch_op.alter_column(
            "next_step",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.create_check_constraint(
            "ck_round_completions_next_step",
            "next_step IS NULL OR next_step > step",
        )


def _downgrade_sqlite() -> None:
    op.execute(
        sa.text(
            "UPDATE round_completions "
            "SET next_step = step + 1 "
            "WHERE next_step IS NULL"
        )
    )
    with op.batch_alter_table("round_completions", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "ck_round_completions_next_step",
            type_="check",
        )
        batch_op.alter_column(
            "next_step",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_round_completions_next_step",
            "next_step > step",
        )


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        _upgrade_sqlite()
        return

    op.drop_constraint(
        "ck_round_completions_next_step",
        "round_completions",
        type_="check",
    )
    op.alter_column(
        "round_completions",
        "next_step",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_round_completions_next_step",
        "round_completions",
        "next_step IS NULL OR next_step > step",
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        _downgrade_sqlite()
        return

    op.execute(
        sa.text(
            "UPDATE round_completions "
            "SET next_step = step + 1 "
            "WHERE next_step IS NULL"
        )
    )
    op.drop_constraint(
        "ck_round_completions_next_step",
        "round_completions",
        type_="check",
    )
    op.alter_column(
        "round_completions",
        "next_step",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_round_completions_next_step",
        "round_completions",
        "next_step > step",
    )
