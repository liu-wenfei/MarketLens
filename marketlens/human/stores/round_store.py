from __future__ import annotations

from sqlite3 import Row

from .database import Database
from .errors import (
    StoreIdempotencyConflictError,
    StoreRoundAlreadyCompletedError,
    StoreSessionNotFoundError,
    StoreWrongExperimentStepError,
)


class RoundStore:
    def __init__(self, db: Database):
        self.db = db

    def get_by_request_id(self, session_id: str, request_id: str) -> Row | None:
        with self.db.connect() as connection:
            return connection.execute(
                """
                SELECT * FROM round_completions
                WHERE session_id = ? AND request_id = ?
                """,
                (session_id, request_id),
            ).fetchone()

    def complete_idempotent(
        self,
        *,
        completion_id: str,
        session_id: str,
        request_id: str,
        step: int,
        completed_at: str,
    ) -> Row:
        """Complete exactly one current round and advance the session atomically."""
        with self.db.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            session = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session is None:
                raise StoreSessionNotFoundError(session_id)

            existing_request = connection.execute(
                """
                SELECT * FROM round_completions
                WHERE session_id = ? AND request_id = ?
                """,
                (session_id, request_id),
            ).fetchone()
            if existing_request is not None:
                if int(existing_request["step"]) != step:
                    raise StoreIdempotencyConflictError(
                        "request_id was already used to complete a different step"
                    )
                return existing_request

            existing_step = connection.execute(
                """
                SELECT * FROM round_completions
                WHERE session_id = ? AND step = ?
                """,
                (session_id, step),
            ).fetchone()
            if existing_step is not None:
                raise StoreRoundAlreadyCompletedError(
                    f"Round {step} was already completed"
                )

            current_step = int(session["current_step"])
            if step != current_step:
                raise StoreWrongExperimentStepError(
                    f"Round step {step} does not match current step {current_step}"
                )

            next_step = current_step + 1
            connection.execute(
                """
                INSERT INTO round_completions (
                    completion_id, session_id, request_id, step, next_step, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    completion_id,
                    session_id,
                    request_id,
                    step,
                    next_step,
                    completed_at,
                ),
            )

            cursor = connection.execute(
                """
                UPDATE sessions
                SET current_step = ?
                WHERE session_id = ? AND current_step = ? AND completed = 0
                """,
                (next_step, session_id, current_step),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Session step changed during round completion")

            row = connection.execute(
                "SELECT * FROM round_completions WHERE completion_id = ?",
                (completion_id,),
            ).fetchone()
            assert row is not None
            return row
