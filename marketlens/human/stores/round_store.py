from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import insert, select, update

from marketlens.persistence.database import Database
from marketlens.persistence.schema import round_completions, sessions

from .errors import (
    StoreIdempotencyConflictError,
    StoreRoundAlreadyCompletedError,
    StoreSessionNotFoundError,
    StoreWrongExperimentStepError,
)
from .orchestration_store import (
    ExperimentOrchestrationStore,
    StoreExperimentStateConflictError,
)


RowMapping = Mapping[str, Any]


class StoreProtocolRoundStateConflictError(ValueError):
    pass


class RoundStore:
    def __init__(self, db: Database):
        self.db = db

    def get_by_request_id(self, session_id: str, request_id: str) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(round_completions).where(
                    round_completions.c.session_id == session_id,
                    round_completions.c.request_id == request_id,
                )
            ).mappings().first()

    def get_by_step(self, session_id: str, step: int) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(round_completions).where(
                    round_completions.c.session_id == session_id,
                    round_completions.c.step == step,
                )
            ).mappings().first()

    def list_for_session(self, session_id: str) -> tuple[RowMapping, ...]:
        with self.db.connect() as connection:
            rows = connection.execute(
                select(round_completions)
                .where(round_completions.c.session_id == session_id)
                .order_by(round_completions.c.step)
            ).mappings().all()
        return tuple(rows)

    def complete_idempotent(
        self,
        *,
        completion_id: str,
        session_id: str,
        request_id: str,
        step: int,
        completed_at: str,
    ) -> RowMapping:
        """Complete exactly one current round and advance the session atomically."""

        with self.db.connect() as connection:
            session = connection.execute(
                select(sessions)
                .where(sessions.c.session_id == session_id)
                .with_for_update()
            ).mappings().first()
            if session is None:
                raise StoreSessionNotFoundError(session_id)

            existing_request = connection.execute(
                select(round_completions).where(
                    round_completions.c.session_id == session_id,
                    round_completions.c.request_id == request_id,
                )
            ).mappings().first()
            if existing_request is not None:
                if int(existing_request["step"]) != step:
                    raise StoreIdempotencyConflictError(
                        "request_id was already used to complete a different step"
                    )
                return existing_request

            existing_step = connection.execute(
                select(round_completions).where(
                    round_completions.c.session_id == session_id,
                    round_completions.c.step == step,
                )
            ).mappings().first()
            if existing_step is not None:
                raise StoreRoundAlreadyCompletedError(f"Round {step} was already completed")

            current_step = int(session["current_step"])
            if step != current_step:
                raise StoreWrongExperimentStepError(
                    f"Round step {step} does not match current step {current_step}"
                )

            next_step = current_step + 1
            connection.execute(
                insert(round_completions).values(
                    completion_id=completion_id,
                    session_id=session_id,
                    request_id=request_id,
                    step=step,
                    next_step=next_step,
                    completed_at=completed_at,
                )
            )

            result = connection.execute(
                update(sessions)
                .where(
                    sessions.c.session_id == session_id,
                    sessions.c.current_step == current_step,
                    sessions.c.completed.is_(False),
                )
                .values(current_step=next_step)
            )
            if result.rowcount != 1:
                raise RuntimeError("Session step changed during round completion")

            row = connection.execute(
                select(round_completions).where(
                    round_completions.c.completion_id == completion_id
                )
            ).mappings().first()
            assert row is not None
            return row

    def complete_protocol_idempotent(
        self,
        *,
        completion_id: str,
        session_id: str,
        request_id: str,
        step: int,
        agent_world_date: str,
        expected_stage: str,
        next_step: int | None,
        next_date: str | None,
        next_stage: str,
        completed_at: str,
    ) -> RowMapping:
        """Record one participant checkpoint completion and advance protocol state atomically.

        Unlike the legacy ``complete_idempotent`` path, every participant-runtime
        date/stage target is supplied by the frozen orchestration contract. The
        terminal checkpoint stores ``next_step = NULL`` rather than inventing a
        non-protocol step 15.
        """

        with self.db.connect() as connection:
            session = connection.execute(
                select(sessions)
                .where(sessions.c.session_id == session_id)
                .with_for_update()
            ).mappings().first()
            if session is None:
                raise StoreSessionNotFoundError(session_id)

            existing_request = connection.execute(
                select(round_completions).where(
                    round_completions.c.session_id == session_id,
                    round_completions.c.request_id == request_id,
                )
            ).mappings().first()
            if existing_request is not None:
                same = (
                    int(existing_request["step"]) == int(step)
                    and (
                        None
                        if existing_request["next_step"] is None
                        else int(existing_request["next_step"])
                    )
                    == (None if next_step is None else int(next_step))
                )
                if not same:
                    raise StoreIdempotencyConflictError(
                        "request_id was already used for a different protocol round completion"
                    )
                return existing_request

            existing_step = connection.execute(
                select(round_completions).where(
                    round_completions.c.session_id == session_id,
                    round_completions.c.step == step,
                )
            ).mappings().first()
            if existing_step is not None:
                raise StoreRoundAlreadyCompletedError(f"Round {step} was already completed")

            if next_step is None:
                if next_date is not None:
                    raise StoreProtocolRoundStateConflictError(
                        "terminal protocol completion must not provide a next_date"
                    )
            elif int(next_step) <= int(step) or next_date is None:
                raise StoreProtocolRoundStateConflictError(
                    "non-terminal protocol completion requires a later next_step and next_date"
                )

            connection.execute(
                insert(round_completions).values(
                    completion_id=completion_id,
                    session_id=session_id,
                    request_id=request_id,
                    step=step,
                    next_step=next_step,
                    completed_at=completed_at,
                )
            )

            try:
                ExperimentOrchestrationStore.advance_checkpoint_on_connection(
                    connection,
                    session_id=session_id,
                    experiment_step=step,
                    agent_world_date=agent_world_date,
                    expected_stage=expected_stage,
                    next_step=next_step,
                    next_date=next_date,
                    next_stage=next_stage,
                )
            except StoreExperimentStateConflictError as exc:
                raise StoreProtocolRoundStateConflictError(str(exc)) from exc

            row = connection.execute(
                select(round_completions).where(
                    round_completions.c.completion_id == completion_id
                )
            ).mappings().first()
            assert row is not None
            return row
