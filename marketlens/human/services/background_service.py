from __future__ import annotations

from marketlens.human.schemas import ParticipantBackgroundRead
from marketlens.human.services.session_service import SessionService
from marketlens.information.projection import (
    ParticipantBackgroundProjection,
    ParticipantInformationProjectionError,
)


class ParticipantBackgroundUnavailableError(ValueError):
    pass


class ParticipantBackgroundService:
    def __init__(
        self,
        sessions: SessionService,
        projection: ParticipantBackgroundProjection | None,
    ):
        self.sessions = sessions
        self.projection = projection

    def get_current_background(self, session_id: str) -> ParticipantBackgroundRead:
        session = self.sessions.get(session_id)
        if session.current_date is None:
            raise ParticipantBackgroundUnavailableError(
                "participant background unavailable until session.current_date is set"
            )
        if self.projection is None:
            raise ParticipantBackgroundUnavailableError(
                "canonical participant background projection is not bound; fail closed rather than read a sample or legacy forum DB"
            )
        try:
            projected = self.projection.project(current_date=session.current_date)
        except ParticipantInformationProjectionError as exc:
            raise ParticipantBackgroundUnavailableError(str(exc)) from exc
        return ParticipantBackgroundRead(
            session_id=session.session_id,
            current_date=session.current_date,
            natural_news=projected["natural_news"],
            forum_posts=projected["forum_posts"],
        )
