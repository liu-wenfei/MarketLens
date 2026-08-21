from __future__ import annotations

from marketlens.human.schemas import SessionState
from marketlens.human.services.session_service import SessionService


class StateService:
    def __init__(self, sessions: SessionService):
        self.sessions = sessions

    def get_current_state(self, session_id: str) -> SessionState:
        session = self.sessions.get(session_id)
        return SessionState(
            session_id=session.session_id,
            current_step=session.current_step,
            current_date=session.current_date,
            experiment_status=session.experiment_status,
            completed=session.completed,
        )
