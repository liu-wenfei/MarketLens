from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import select, update

from marketlens.persistence.database import Database
from marketlens.persistence.schema import sessions
from marketlens.human.stores.errors import StoreSessionNotFoundError


RowMapping = Mapping[str, Any]


class StoreExperimentStateConflictError(ValueError):
    pass


class ExperimentOrchestrationStore:
    """Persist only server-authoritative participant execution state."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _locked_session(connection, session_id: str) -> RowMapping:
        row = connection.execute(
            select(sessions)
            .where(sessions.c.session_id == session_id)
            .with_for_update()
        ).mappings().first()
        if row is None:
            raise StoreSessionNotFoundError(session_id)
        return row

    def get(self, session_id: str) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(sessions).where(sessions.c.session_id == session_id)
            ).mappings().first()

    def initialize_idempotent(
        self,
        *,
        session_id: str,
        initial_step: int,
        initial_date: str,
        initial_stage: str,
    ) -> RowMapping:
        with self.db.connect() as connection:
            session = self._locked_session(connection, session_id)
            if bool(session["completed"]):
                raise StoreExperimentStateConflictError(
                    "completed session cannot be initialized for participant orchestration"
                )
            same = (
                int(session["current_step"]) == int(initial_step)
                and session["current_date"] == initial_date
                and session["current_stage"] == initial_stage
            )
            if same:
                return session
            if session["current_date"] is not None or session["current_stage"] is not None:
                raise StoreExperimentStateConflictError(
                    "session already contains a different experiment date/stage binding"
                )
            result = connection.execute(
                update(sessions)
                .where(
                    sessions.c.session_id == session_id,
                    sessions.c.current_step == initial_step,
                    sessions.c.current_date.is_(None),
                    sessions.c.current_stage.is_(None),
                    sessions.c.completed.is_(False),
                )
                .values(current_date=initial_date, current_stage=initial_stage)
            )
            if result.rowcount != 1:
                raise StoreExperimentStateConflictError(
                    "session changed during orchestration initialization"
                )
            return self._locked_session(connection, session_id)

    def transition_stage(
        self,
        *,
        session_id: str,
        experiment_step: int,
        agent_world_date: str,
        expected_stage: str,
        next_stage: str,
    ) -> RowMapping:
        with self.db.connect() as connection:
            session = self._locked_session(connection, session_id)
            if (
                int(session["current_step"]) != int(experiment_step)
                or session["current_date"] != agent_world_date
                or session["current_stage"] != expected_stage
                or bool(session["completed"])
            ):
                raise StoreExperimentStateConflictError(
                    "session step/date/stage does not match the required orchestration transition"
                )
            result = connection.execute(
                update(sessions)
                .where(
                    sessions.c.session_id == session_id,
                    sessions.c.current_step == experiment_step,
                    sessions.c.current_date == agent_world_date,
                    sessions.c.current_stage == expected_stage,
                    sessions.c.completed.is_(False),
                )
                .values(current_stage=next_stage)
            )
            if result.rowcount != 1:
                raise StoreExperimentStateConflictError(
                    "session changed during stage transition"
                )
            return self._locked_session(connection, session_id)

    def advance_checkpoint(
        self,
        *,
        session_id: str,
        experiment_step: int,
        agent_world_date: str,
        expected_stage: str,
        next_step: int | None,
        next_date: str | None,
        next_stage: str,
    ) -> RowMapping:
        with self.db.connect() as connection:
            session = self._locked_session(connection, session_id)
            if (
                int(session["current_step"]) != int(experiment_step)
                or session["current_date"] != agent_world_date
                or session["current_stage"] != expected_stage
                or bool(session["completed"])
            ):
                raise StoreExperimentStateConflictError(
                    "session is not at the required completed-round state"
                )
            if next_step is None:
                values = {
                    "current_stage": next_stage,
                    "experiment_status": "completed",
                    "completed": True,
                }
            else:
                if next_date is None:
                    raise StoreExperimentStateConflictError(
                        "next_date is required for a non-final checkpoint advance"
                    )
                values = {
                    "current_step": int(next_step),
                    "current_date": next_date,
                    "current_stage": next_stage,
                }
            result = connection.execute(
                update(sessions)
                .where(
                    sessions.c.session_id == session_id,
                    sessions.c.current_step == experiment_step,
                    sessions.c.current_date == agent_world_date,
                    sessions.c.current_stage == expected_stage,
                    sessions.c.completed.is_(False),
                )
                .values(**values)
            )
            if result.rowcount != 1:
                raise StoreExperimentStateConflictError(
                    "session changed during checkpoint advance"
                )
            return self._locked_session(connection, session_id)
