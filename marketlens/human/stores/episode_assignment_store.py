from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from marketlens.episode.contract import EPISODE_IDS, EPISODE_POOL_ID
from marketlens.persistence.database import Database
from marketlens.persistence.schema import participant_episode_assignments, sessions

from .errors import StoreSessionNotFoundError


RowMapping = Mapping[str, Any]


class StoreEpisodeAssignmentConflictError(ValueError):
    pass


class StoreEpisodeAssignmentValidationError(ValueError):
    pass


class EpisodeAssignmentStore:
    """Human-domain source of truth for session -> canonical episode binding.

    This store does not choose an episode.  A future allocator may choose one;
    this store only persists the resulting binding exactly once per session.
    """

    def __init__(self, db: Database):
        self.db = db

    def get(self, session_id: str) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(participant_episode_assignments).where(
                    participant_episode_assignments.c.session_id == session_id
                )
            ).mappings().first()

    @staticmethod
    def _validate_identity(episode_pool_id: str, episode_id: str) -> None:
        if episode_pool_id != EPISODE_POOL_ID:
            raise StoreEpisodeAssignmentValidationError(
                "episode_pool_id does not match the frozen canonical episode pool"
            )
        if episode_id not in EPISODE_IDS:
            raise StoreEpisodeAssignmentValidationError(
                f"unknown canonical episode_id: {episode_id}"
            )

    def bind_idempotent(
        self,
        *,
        assignment_id: str,
        session_id: str,
        episode_pool_id: str,
        episode_id: str,
        assignment_method: str,
        assignment_version: str,
        assigned_at: str,
    ) -> RowMapping:
        self._validate_identity(episode_pool_id, episode_id)
        if not assignment_method.strip():
            raise StoreEpisodeAssignmentValidationError(
                "assignment_method must be non-empty"
            )
        if not assignment_version.strip():
            raise StoreEpisodeAssignmentValidationError(
                "assignment_version must be non-empty"
            )

        try:
            with self.db.connect() as connection:
                session = connection.execute(
                    select(sessions)
                    .where(sessions.c.session_id == session_id)
                    .with_for_update()
                ).mappings().first()
                if session is None:
                    raise StoreSessionNotFoundError(session_id)

                existing = connection.execute(
                    select(participant_episode_assignments)
                    .where(participant_episode_assignments.c.session_id == session_id)
                    .with_for_update()
                ).mappings().first()
                if existing is not None:
                    same_binding = (
                        existing["participant_id"] == session["participant_id"]
                        and existing["episode_pool_id"] == episode_pool_id
                        and existing["episode_id"] == episode_id
                        and existing["assignment_method"] == assignment_method
                        and existing["assignment_version"] == assignment_version
                    )
                    if not same_binding:
                        raise StoreEpisodeAssignmentConflictError(
                            "session is already bound to a different canonical episode assignment"
                        )
                    return existing

                connection.execute(
                    insert(participant_episode_assignments).values(
                        assignment_id=assignment_id,
                        session_id=session_id,
                        participant_id=session["participant_id"],
                        episode_pool_id=episode_pool_id,
                        episode_id=episode_id,
                        assignment_method=assignment_method,
                        assignment_version=assignment_version,
                        assigned_at=assigned_at,
                    )
                )
                row = connection.execute(
                    select(participant_episode_assignments).where(
                        participant_episode_assignments.c.assignment_id == assignment_id
                    )
                ).mappings().first()
                assert row is not None
                return row
        except IntegrityError:
            existing = self.get(session_id)
            if existing is None:
                raise
            same_binding = (
                existing["episode_pool_id"] == episode_pool_id
                and existing["episode_id"] == episode_id
                and existing["assignment_method"] == assignment_method
                and existing["assignment_version"] == assignment_version
            )
            if not same_binding:
                raise StoreEpisodeAssignmentConflictError(
                    "session is already bound to a different canonical episode assignment"
                )
            return existing
