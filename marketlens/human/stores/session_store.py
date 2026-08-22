from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from marketlens.persistence.database import Database
from marketlens.persistence.schema import participant_portfolios, sessions

from .errors import StoreIdempotencyConflictError


RowMapping = Mapping[str, Any]


class SessionStore:
    def __init__(self, db: Database):
        self.db = db

    def get(self, session_id: str) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(sessions).where(sessions.c.session_id == session_id)
            ).mappings().first()

    def get_by_request_id(self, request_id: str) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(sessions).where(sessions.c.request_id == request_id)
            ).mappings().first()

    def _ensure_portfolio(
        self,
        connection,
        *,
        session: RowMapping,
        initial_cash: float,
        updated_at: str,
    ) -> None:
        existing_portfolio = connection.execute(
            select(participant_portfolios.c.session_id).where(
                participant_portfolios.c.session_id == session["session_id"]
            )
        ).first()
        if existing_portfolio is not None:
            return
        connection.execute(
            insert(participant_portfolios).values(
                session_id=session["session_id"],
                initial_cash=initial_cash,
                cash=initial_cash,
                created_at=session["created_at"],
                updated_at=updated_at,
            )
        )

    def create_idempotent(
        self,
        *,
        session_id: str,
        participant_id: str,
        request_id: str,
        created_at: str,
        initial_cash: float,
    ) -> RowMapping:
        """Create the session and its participant-only account atomically.

        A session row is the lifecycle owner for its participant portfolio.
        SQLAlchemy supplies one transaction boundary for SQLite locally and
        PostgreSQL later. On PostgreSQL, ``FOR UPDATE`` serialises replays of an
        already-existing session; a unique request_id remains the final race
        guard for concurrent first creation.
        """

        try:
            with self.db.connect() as connection:
                existing = connection.execute(
                    select(sessions)
                    .where(sessions.c.request_id == request_id)
                    .with_for_update()
                ).mappings().first()
                if existing is not None:
                    if existing["participant_id"] != participant_id:
                        raise StoreIdempotencyConflictError(
                            "request_id was already used for a different participant_id"
                        )
                    self._ensure_portfolio(
                        connection,
                        session=existing,
                        initial_cash=initial_cash,
                        updated_at=created_at,
                    )
                    return existing

                connection.execute(
                    insert(sessions).values(
                        session_id=session_id,
                        participant_id=participant_id,
                        request_id=request_id,
                        created_at=created_at,
                        current_step=0,
                        current_date=None,
                        experiment_status="active",
                        completed=False,
                    )
                )
                connection.execute(
                    insert(participant_portfolios).values(
                        session_id=session_id,
                        initial_cash=initial_cash,
                        cash=initial_cash,
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
                row = connection.execute(
                    select(sessions).where(sessions.c.session_id == session_id)
                ).mappings().first()
                assert row is not None
                return row
        except IntegrityError:
            # A concurrent creator can win the unique request_id race. Resolve
            # that race by treating the committed winner as the idempotent row.
            existing = self.get_by_request_id(request_id)
            if existing is None:
                raise
            if existing["participant_id"] != participant_id:
                raise StoreIdempotencyConflictError(
                    "request_id was already used for a different participant_id"
                )
            with self.db.connect() as connection:
                locked = connection.execute(
                    select(sessions)
                    .where(sessions.c.session_id == existing["session_id"])
                    .with_for_update()
                ).mappings().first()
                assert locked is not None
                self._ensure_portfolio(
                    connection,
                    session=locked,
                    initial_cash=initial_cash,
                    updated_at=created_at,
                )
                return locked
