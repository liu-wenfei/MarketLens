from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from marketlens.human.schemas import DecisionCreate, DecisionRead
from marketlens.human.services.session_service import SessionNotFoundError
from marketlens.human.stores.decision_store import DecisionStore
from marketlens.human.stores.errors import (
    StoreDecisionAlreadySubmittedError,
    StoreSessionNotFoundError,
    StoreWrongExperimentStepError,
)


class DecisionAlreadySubmittedError(ValueError):
    pass


class WrongExperimentStepError(ValueError):
    pass


def _to_decision(row) -> DecisionRead:
    return DecisionRead(
        decision_id=row["decision_id"],
        session_id=row["session_id"],
        request_id=row["request_id"],
        step=row["step"],
        stock_id=row["stock_id"],
        action=row["action"],
        confidence=row["confidence"],
        evidence_sources=json.loads(row["evidence_sources"]),
        rationale=row["rationale"],
        submitted_at=row["submitted_at"],
    )


class DecisionService:
    def __init__(self, decisions: DecisionStore):
        self.decisions = decisions

    def submit(self, session_id: str, payload: DecisionCreate) -> DecisionRead:
        now = datetime.now(timezone.utc).isoformat()
        try:
            row = self.decisions.submit_idempotent(
                decision_id=str(uuid4()),
                session_id=session_id,
                request_id=payload.request_id,
                step=payload.step,
                stock_id=payload.stock_id,
                action=payload.action.value,
                confidence=payload.confidence,
                evidence_sources=payload.evidence_sources,
                rationale=payload.rationale,
                submitted_at=now,
            )
        except StoreSessionNotFoundError as exc:
            raise SessionNotFoundError(session_id) from exc
        except StoreDecisionAlreadySubmittedError as exc:
            raise DecisionAlreadySubmittedError(str(exc)) from exc
        except StoreWrongExperimentStepError as exc:
            raise WrongExperimentStepError(str(exc)) from exc
        return _to_decision(row)
