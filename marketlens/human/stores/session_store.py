from __future__ import annotations

from sqlite3 import Row

from .database import Database
from .errors import StoreIdempotencyConflictError


class SessionStore:
    def __init__(self, db: Database):
        self.db = db

    def get(self, session_id: str) -> Row | None:
        with self.db.connect() as connection:
            return connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()

    def get_by_request_id(self, request_id: str) -> Row | None:
        with self.db.connect() as connection:
            return connection.execute(
                "SELECT * FROM sessions WHERE request_id = ?",
                (request_id,),
            ).fetchone()

    def create_idempotent(
        self,
        *,
        session_id: str,
        participant_id: str,
        request_id: str,
        created_at: str,
    ) -> Row:
        with self.db.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM sessions WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if existing is not None:
                if existing["participant_id"] != participant_id:
                    raise StoreIdempotencyConflictError(
                        "request_id was already used for a different participant_id"
                    )
                return existing

            connection.execute(
                """
                INSERT INTO sessions (
                    session_id, participant_id, request_id, created_at,
                    current_step, current_date, experiment_status, completed
                ) VALUES (?, ?, ?, ?, 0, NULL, 'active', 0)
                """,
                (session_id, participant_id, request_id, created_at),
            )
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            assert row is not None
            return row
