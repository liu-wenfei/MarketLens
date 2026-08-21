from __future__ import annotations

import json
from sqlite3 import Row

from .database import Database
from .errors import (
    StoreDecisionAlreadySubmittedError,
    StoreIdempotencyConflictError,
    StoreSessionNotFoundError,
    StoreWrongExperimentStepError,
)


class DecisionStore:
    def __init__(self, db: Database):
        self.db = db

    def get_by_request_id(self, session_id: str, request_id: str) -> Row | None:
        with self.db.connect() as connection:
            return connection.execute(
                """
                SELECT * FROM decisions
                WHERE session_id = ? AND request_id = ?
                """,
                (session_id, request_id),
            ).fetchone()

    def get_by_step(self, session_id: str, step: int) -> Row | None:
        with self.db.connect() as connection:
            return connection.execute(
                """
                SELECT * FROM decisions
                WHERE session_id = ? AND step = ?
                """,
                (session_id, step),
            ).fetchone()

    def submit_idempotent(
        self,
        *,
        decision_id: str,
        session_id: str,
        request_id: str,
        step: int,
        stock_id: str,
        action: str,
        confidence: float,
        evidence_sources: list[str],
        rationale: str | None,
        submitted_at: str,
    ) -> Row:
        """Persist one decision for the current step without advancing the session."""
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
                SELECT * FROM decisions
                WHERE session_id = ? AND request_id = ?
                """,
                (session_id, request_id),
            ).fetchone()
            if existing_request is not None:
                same_payload = (
                    int(existing_request["step"]) == step
                    and existing_request["stock_id"] == stock_id
                    and existing_request["action"] == action
                    and float(existing_request["confidence"]) == float(confidence)
                    and existing_request["evidence_sources"]
                    == json.dumps(evidence_sources)
                    and existing_request["rationale"] == rationale
                )
                if not same_payload:
                    raise StoreIdempotencyConflictError(
                        "request_id was already used for a different decision payload"
                    )
                return existing_request

            existing_step = connection.execute(
                """
                SELECT * FROM decisions
                WHERE session_id = ? AND step = ?
                """,
                (session_id, step),
            ).fetchone()
            if existing_step is not None:
                raise StoreDecisionAlreadySubmittedError(
                    f"A decision already exists for step {step}"
                )

            current_step = int(session["current_step"])
            if step != current_step:
                raise StoreWrongExperimentStepError(
                    f"Decision step {step} does not match current step {current_step}"
                )

            connection.execute(
                """
                INSERT INTO decisions (
                    decision_id, session_id, request_id, step, stock_id,
                    action, confidence, evidence_sources, rationale, submitted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    session_id,
                    request_id,
                    step,
                    stock_id,
                    action,
                    confidence,
                    json.dumps(evidence_sources),
                    rationale,
                    submitted_at,
                ),
            )

            row = connection.execute(
                "SELECT * FROM decisions WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
            assert row is not None
            return row
