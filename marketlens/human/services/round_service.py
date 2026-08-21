from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from marketlens.human.schemas import RoundComplete, RoundCompletionRead
from marketlens.human.services.session_service import (
    IdempotencyConflictError,
    SessionNotFoundError,
)
from marketlens.human.stores.errors import (
    StoreIdempotencyConflictError,
    StoreRoundAlreadyCompletedError,
    StoreSessionNotFoundError,
    StoreWrongExperimentStepError,
)
from marketlens.human.stores.round_store import RoundStore


class RoundAlreadyCompletedError(ValueError):
    pass


class WrongExperimentStepError(ValueError):
    pass


def _to_completion(row) -> RoundCompletionRead:
    return RoundCompletionRead(
        completion_id=row["completion_id"],
        session_id=row["session_id"],
        request_id=row["request_id"],
        step=row["step"],
        next_step=row["next_step"],
        completed_at=row["completed_at"],
    )


class RoundService:
    def __init__(self, rounds: RoundStore):
        self.rounds = rounds

    def complete(self, session_id: str, payload: RoundComplete) -> RoundCompletionRead:
        now = datetime.now(timezone.utc).isoformat()
        try:
            row = self.rounds.complete_idempotent(
                completion_id=str(uuid4()),
                session_id=session_id,
                request_id=payload.request_id,
                step=payload.step,
                completed_at=now,
            )
        except StoreSessionNotFoundError as exc:
            raise SessionNotFoundError(session_id) from exc
        except StoreIdempotencyConflictError as exc:
            raise IdempotencyConflictError(str(exc)) from exc
        except StoreRoundAlreadyCompletedError as exc:
            raise RoundAlreadyCompletedError(str(exc)) from exc
        except StoreWrongExperimentStepError as exc:
            raise WrongExperimentStepError(str(exc)) from exc
        return _to_completion(row)
