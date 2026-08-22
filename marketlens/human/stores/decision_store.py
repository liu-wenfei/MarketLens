from __future__ import annotations

import json
from typing import Any, Mapping

from sqlalchemy import insert, select

from marketlens.persistence.database import Database
from marketlens.persistence.schema import decisions, sessions

from .errors import (
    StoreDecisionAlreadySubmittedError,
    StoreIdempotencyConflictError,
    StoreSessionNotFoundError,
    StoreWrongExperimentStepError,
)


RowMapping = Mapping[str, Any]


class DecisionStore:
    def __init__(self, db: Database):
        self.db = db

    def get_by_request_id(self, session_id: str, request_id: str) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(decisions).where(
                    decisions.c.session_id == session_id,
                    decisions.c.request_id == request_id,
                )
            ).mappings().first()

    def get_by_step(self, session_id: str, step: int) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(decisions).where(
                    decisions.c.session_id == session_id,
                    decisions.c.step == step,
                )
            ).mappings().first()

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
    ) -> RowMapping:
        """Persist one decision for the current step without advancing the session."""

        with self.db.connect() as connection:
            session = connection.execute(
                select(sessions)
                .where(sessions.c.session_id == session_id)
                .with_for_update()
            ).mappings().first()
            if session is None:
                raise StoreSessionNotFoundError(session_id)

            existing_request = connection.execute(
                select(decisions).where(
                    decisions.c.session_id == session_id,
                    decisions.c.request_id == request_id,
                )
            ).mappings().first()
            if existing_request is not None:
                same_payload = (
                    int(existing_request["step"]) == step
                    and existing_request["stock_id"] == stock_id
                    and existing_request["action"] == action
                    and float(existing_request["confidence"]) == float(confidence)
                    and existing_request["evidence_sources"] == json.dumps(evidence_sources)
                    and existing_request["rationale"] == rationale
                )
                if not same_payload:
                    raise StoreIdempotencyConflictError(
                        "request_id was already used for a different decision payload"
                    )
                return existing_request

            existing_step = connection.execute(
                select(decisions).where(
                    decisions.c.session_id == session_id,
                    decisions.c.step == step,
                )
            ).mappings().first()
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
                insert(decisions).values(
                    decision_id=decision_id,
                    session_id=session_id,
                    request_id=request_id,
                    step=step,
                    stock_id=stock_id,
                    action=action,
                    confidence=confidence,
                    evidence_sources=json.dumps(evidence_sources),
                    rationale=rationale,
                    submitted_at=submitted_at,
                )
            )
            row = connection.execute(
                select(decisions).where(decisions.c.decision_id == decision_id)
            ).mappings().first()
            assert row is not None
            return row
