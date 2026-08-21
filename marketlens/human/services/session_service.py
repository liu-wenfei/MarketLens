from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from marketlens.human.portfolio.models import DEFAULT_DEV_INITIAL_CASH, round_currency
from marketlens.human.schemas import SessionCreate, SessionRead
from marketlens.human.stores.errors import StoreIdempotencyConflictError
from marketlens.human.stores.session_store import SessionStore


class SessionNotFoundError(LookupError):
    pass


class IdempotencyConflictError(ValueError):
    pass


def _to_session(row) -> SessionRead:
    return SessionRead(
        session_id=row["session_id"],
        participant_id=row["participant_id"],
        created_at=row["created_at"],
        current_step=row["current_step"],
        current_date=row["current_date"],
        experiment_status=row["experiment_status"],
        completed=bool(row["completed"]),
    )


class SessionService:
    def __init__(
        self,
        store: SessionStore,
        initial_cash: float = DEFAULT_DEV_INITIAL_CASH,
    ):
        self.store = store
        self.initial_cash = round_currency(initial_cash)

    def create(self, payload: SessionCreate) -> SessionRead:
        now = datetime.now(timezone.utc).isoformat()
        try:
            row = self.store.create_idempotent(
                session_id=str(uuid4()),
                participant_id=payload.participant_id,
                request_id=payload.request_id,
                created_at=now,
                initial_cash=self.initial_cash,
            )
        except StoreIdempotencyConflictError as exc:
            raise IdempotencyConflictError(str(exc)) from exc
        return _to_session(row)

    def get(self, session_id: str) -> SessionRead:
        row = self.store.get(session_id)
        if row is None:
            raise SessionNotFoundError(session_id)
        return _to_session(row)
