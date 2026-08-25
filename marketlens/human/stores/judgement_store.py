from __future__ import annotations

import json
from typing import Any, Mapping

from sqlalchemy import insert, select, update

from marketlens.persistence.database import Database
from marketlens.persistence.schema import participant_judgements, sessions
from marketlens.human.stores.errors import (
    StoreIdempotencyConflictError,
    StoreSessionNotFoundError,
)


RowMapping = Mapping[str, Any]


class StoreJudgementAlreadySubmittedError(ValueError):
    pass


class StoreJudgementStageError(ValueError):
    pass


class JudgementStore:
    """Authoritative persistence for formal J0..J4 judgement measurements."""

    def __init__(self, db: Database):
        self.db = db

    def get_by_request_id(self, session_id: str, request_id: str) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(participant_judgements).where(
                    participant_judgements.c.session_id == session_id,
                    participant_judgements.c.request_id == request_id,
                )
            ).mappings().first()

    def list_for_session(self, session_id: str) -> tuple[RowMapping, ...]:
        with self.db.connect() as connection:
            rows = connection.execute(
                select(participant_judgements)
                .where(participant_judgements.c.session_id == session_id)
                .order_by(participant_judgements.c.judgement_event)
            ).mappings().all()
        return tuple(rows)

    def submit_idempotent(
        self,
        *,
        judgement_id: str,
        session_id: str,
        request_id: str,
        judgement_event: str,
        experiment_step: int,
        agent_world_date: str,
        expected_stage: str,
        next_stage: str,
        stock_id: str,
        action: str,
        confidence: float,
        evidence_sources: list[str],
        rationale: str | None,
        submitted_at: str,
    ) -> RowMapping:
        encoded_evidence = json.dumps(evidence_sources)
        with self.db.connect() as connection:
            session = connection.execute(
                select(sessions)
                .where(sessions.c.session_id == session_id)
                .with_for_update()
            ).mappings().first()
            if session is None:
                raise StoreSessionNotFoundError(session_id)

            existing_request = connection.execute(
                select(participant_judgements).where(
                    participant_judgements.c.session_id == session_id,
                    participant_judgements.c.request_id == request_id,
                )
            ).mappings().first()
            if existing_request is not None:
                same_payload = (
                    existing_request["judgement_event"] == judgement_event
                    and int(existing_request["experiment_step"]) == int(experiment_step)
                    and existing_request["agent_world_date"] == agent_world_date
                    and existing_request["stock_id"] == stock_id
                    and existing_request["action"] == action
                    and float(existing_request["confidence"]) == float(confidence)
                    and existing_request["evidence_sources"] == encoded_evidence
                    and existing_request["rationale"] == rationale
                )
                if not same_payload:
                    raise StoreIdempotencyConflictError(
                        "request_id was already used for a different formal judgement payload"
                    )
                return existing_request

            existing_event = connection.execute(
                select(participant_judgements).where(
                    participant_judgements.c.session_id == session_id,
                    participant_judgements.c.judgement_event == judgement_event,
                )
            ).mappings().first()
            if existing_event is not None:
                raise StoreJudgementAlreadySubmittedError(
                    f"formal judgement {judgement_event} already exists for this session"
                )

            if (
                bool(session["completed"])
                or int(session["current_step"]) != int(experiment_step)
                or session["current_date"] != agent_world_date
                or session["current_stage"] != expected_stage
            ):
                raise StoreJudgementStageError(
                    "session step/date/stage does not authorise this formal judgement"
                )

            connection.execute(
                insert(participant_judgements).values(
                    judgement_id=judgement_id,
                    session_id=session_id,
                    participant_id=session["participant_id"],
                    request_id=request_id,
                    judgement_event=judgement_event,
                    experiment_step=experiment_step,
                    agent_world_date=agent_world_date,
                    stock_id=stock_id,
                    action=action,
                    confidence=confidence,
                    evidence_sources=encoded_evidence,
                    rationale=rationale,
                    submitted_at=submitted_at,
                )
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
                raise RuntimeError("Session stage changed during formal judgement submission")

            row = connection.execute(
                select(participant_judgements).where(
                    participant_judgements.c.judgement_id == judgement_id
                )
            ).mappings().first()
            assert row is not None
            return row
