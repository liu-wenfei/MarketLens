from __future__ import annotations

from typing import Mapping

from marketlens.human.schemas import ParticipantBackgroundRead
from marketlens.human.services.background_service import ParticipantBackgroundUnavailableError
from marketlens.human.services.episode_assignment_service import EpisodeAssignmentService
from marketlens.human.services.session_service import SessionService
from marketlens.information.projection import (
    ParticipantBackgroundProjection,
    ParticipantInformationProjectionError,
)


class EpisodeAwareParticipantBackgroundService:
    """Resolve canonical background strictly from the session's episode binding."""

    def __init__(
        self,
        *,
        sessions: SessionService,
        assignments: EpisodeAssignmentService,
        projections: Mapping[str, ParticipantBackgroundProjection],
    ):
        self.sessions = sessions
        self.assignments = assignments
        self.projections = dict(projections)

    def get_current_background(self, session_id: str) -> ParticipantBackgroundRead:
        session = self.sessions.get(session_id)
        if session.current_date is None:
            raise ParticipantBackgroundUnavailableError(
                "participant background unavailable until session.current_date is set"
            )

        assignment = self.assignments.get(session_id)
        if assignment is None:
            raise ParticipantBackgroundUnavailableError(
                "participant session has no canonical episode assignment"
            )

        projection = self.projections.get(assignment.episode_id)
        if projection is None:
            raise ParticipantBackgroundUnavailableError(
                f"no participant background projection is bound for canonical episode {assignment.episode_id}"
            )

        bound_episode_id = getattr(getattr(projection, "episode", None), "episode_id", None)
        if bound_episode_id != assignment.episode_id:
            raise ParticipantBackgroundUnavailableError(
                "participant background projection episode identity disagrees with the authoritative assignment"
            )

        try:
            projected = projection.project(current_date=session.current_date)
        except ParticipantInformationProjectionError as exc:
            raise ParticipantBackgroundUnavailableError(str(exc)) from exc

        return ParticipantBackgroundRead(
            session_id=session.session_id,
            current_date=session.current_date,
            natural_news=projected["natural_news"],
            forum_posts=projected["forum_posts"],
        )
