from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError

from marketlens.episode.contract import (
    EPISODE_IDS as DEFAULT_EPISODE_IDS,
    EPISODE_POOL_ID as DEFAULT_EPISODE_POOL_ID,
)
from marketlens.persistence.database import Database
from marketlens.persistence.schema import participant_episode_assignments, sessions

from .errors import StoreSessionNotFoundError


RowMapping = Mapping[str, Any]
EpisodeChooser = Callable[[Sequence[str]], str]


class StoreEpisodeAssignmentConflictError(ValueError):
    pass


class StoreEpisodeAssignmentValidationError(ValueError):
    pass


class EpisodeAssignmentStore:
    """Human-domain source of truth for session -> canonical episode binding.

    Explicit ``bind_idempotent`` remains available for bounded tests and legacy
    wiring. Formal participant bootstrap uses ``allocate_balanced_idempotent``
    so episode selection and persistence happen inside one database transaction.
    """

    def __init__(
        self,
        db: Database,
        *,
        episode_pool_id: str = DEFAULT_EPISODE_POOL_ID,
        episode_ids: Sequence[str] = DEFAULT_EPISODE_IDS,
    ):
        resolved_episode_ids = tuple(str(value) for value in episode_ids)

        if not str(episode_pool_id).strip():
            raise StoreEpisodeAssignmentValidationError(
                "episode_pool_id must be non-empty"
            )
        if not resolved_episode_ids:
            raise StoreEpisodeAssignmentValidationError(
                "episode_ids must be non-empty"
            )
        if len(set(resolved_episode_ids)) != len(resolved_episode_ids):
            raise StoreEpisodeAssignmentValidationError(
                "episode_ids must be unique"
            )
        if any(not value.strip() for value in resolved_episode_ids):
            raise StoreEpisodeAssignmentValidationError(
                "episode_ids must contain only non-empty values"
            )

        self.db = db
        self.episode_pool_id = str(episode_pool_id)
        self.episode_ids = resolved_episode_ids

    def get(self, session_id: str) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(participant_episode_assignments).where(
                    participant_episode_assignments.c.session_id == session_id
                )
            ).mappings().first()

    def _validate_identity(
        self,
        episode_pool_id: str,
        episode_id: str,
    ) -> None:
        if episode_pool_id != self.episode_pool_id:
            raise StoreEpisodeAssignmentValidationError(
                "episode_pool_id does not match the runtime canonical episode pool"
            )
        if episode_id not in self.episode_ids:
            raise StoreEpisodeAssignmentValidationError(
                f"unknown canonical episode_id: {episode_id}"
            )

    @staticmethod
    def _validate_assignment_metadata(
        *, assignment_method: str, assignment_version: str
    ) -> None:
        if not assignment_method.strip():
            raise StoreEpisodeAssignmentValidationError(
                "assignment_method must be non-empty"
            )
        if not assignment_version.strip():
            raise StoreEpisodeAssignmentValidationError(
                "assignment_version must be non-empty"
            )

    @staticmethod
    def _same_binding(
        existing: RowMapping,
        *,
        participant_id: str,
        episode_pool_id: str,
        episode_id: str,
        assignment_method: str,
        assignment_version: str,
    ) -> bool:
        return (
            existing["participant_id"] == participant_id
            and existing["episode_pool_id"] == episode_pool_id
            and existing["episode_id"] == episode_id
            and existing["assignment_method"] == assignment_method
            and existing["assignment_version"] == assignment_version
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
        self._validate_assignment_metadata(
            assignment_method=assignment_method,
            assignment_version=assignment_version,
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
                    if not self._same_binding(
                        existing,
                        participant_id=session["participant_id"],
                        episode_pool_id=episode_pool_id,
                        episode_id=episode_id,
                        assignment_method=assignment_method,
                        assignment_version=assignment_version,
                    ):
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
            if not self._same_binding(
                existing,
                participant_id=existing["participant_id"],
                episode_pool_id=episode_pool_id,
                episode_id=episode_id,
                assignment_method=assignment_method,
                assignment_version=assignment_version,
            ):
                raise StoreEpisodeAssignmentConflictError(
                    "session is already bound to a different canonical episode assignment"
                )
            return existing

    def _serialize_allocator(self, connection, *, session_id: str) -> RowMapping:
        """Acquire a database-level allocator serialization point.

        SQLite permits only one writer, so a no-op write to the authoritative
        session row acquires the write reservation before assignment counts are
        read. PostgreSQL uses an explicit table lock so concurrent sessions also
        serialize the count/choose/insert unit. Unsupported dialects fail closed.
        """

        if self.db.dialect_name == "sqlite":
            result = connection.execute(
                update(sessions)
                .where(sessions.c.session_id == session_id)
                .values(session_id=session_id)
            )
            if result.rowcount != 1:
                raise StoreSessionNotFoundError(session_id)
            session = connection.execute(
                select(sessions).where(sessions.c.session_id == session_id)
            ).mappings().first()
        elif self.db.dialect_name == "postgresql":
            connection.exec_driver_sql(
                "LOCK TABLE participant_episode_assignments IN SHARE ROW EXCLUSIVE MODE"
            )
            session = connection.execute(
                select(sessions)
                .where(sessions.c.session_id == session_id)
                .with_for_update()
            ).mappings().first()
        else:
            raise StoreEpisodeAssignmentValidationError(
                f"formal balanced allocation is unsupported for database dialect {self.db.dialect_name!r}"
            )

        if session is None:
            raise StoreSessionNotFoundError(session_id)
        return session

    def allocate_balanced_idempotent(
        self,
        *,
        assignment_id: str,
        session_id: str,
        episode_pool_id: str,
        assignment_method: str,
        assignment_version: str,
        assigned_at: str,
        chooser: EpisodeChooser,
    ) -> RowMapping:
        """Allocate from the least-used frozen episodes, then persist once.

        The entire existing-binding check, count read, random tie-break and insert
        runs inside one serialized transaction. This guarantees the formal
        balance invariant ``max(counts) - min(counts) <= 1`` under concurrent
        bootstrap requests on supported databases.
        """

        if episode_pool_id != self.episode_pool_id:
            raise StoreEpisodeAssignmentValidationError(
                "episode_pool_id does not match the frozen canonical episode pool"
            )
        self._validate_assignment_metadata(
            assignment_method=assignment_method,
            assignment_version=assignment_version,
        )

        with self.db.connect() as connection:
            session = self._serialize_allocator(connection, session_id=session_id)

            existing = connection.execute(
                select(participant_episode_assignments).where(
                    participant_episode_assignments.c.session_id == session_id
                )
            ).mappings().first()
            if existing is not None:
                if (
                    existing["participant_id"] != session["participant_id"]
                    or existing["episode_pool_id"] != episode_pool_id
                    or existing["episode_id"] not in self.episode_ids
                    or existing["assignment_method"] != assignment_method
                    or existing["assignment_version"] != assignment_version
                ):
                    raise StoreEpisodeAssignmentConflictError(
                        "session is already bound to a different canonical episode assignment"
                    )
                return existing

            counts = {episode_id: 0 for episode_id in self.episode_ids}
            rows = connection.execute(
                select(
                    participant_episode_assignments.c.episode_id,
                    func.count().label("assignment_count"),
                )
                .where(
                    participant_episode_assignments.c.episode_pool_id
                    == episode_pool_id
                )
                .group_by(participant_episode_assignments.c.episode_id)
            ).all()
            for episode_id, assignment_count in rows:
                if episode_id not in counts:
                    raise StoreEpisodeAssignmentValidationError(
                        f"stored assignment references unknown canonical episode_id: {episode_id}"
                    )
                counts[str(episode_id)] = int(assignment_count)

            minimum = min(counts.values())
            candidates = tuple(
                episode_id
                for episode_id in self.episode_ids
                if counts[episode_id] == minimum
            )
            selected = chooser(candidates)
            if selected not in candidates:
                raise StoreEpisodeAssignmentValidationError(
                    "server-side allocator chooser returned an episode outside the minimum-count set"
                )
            self._validate_identity(episode_pool_id, selected)

            connection.execute(
                insert(participant_episode_assignments).values(
                    assignment_id=assignment_id,
                    session_id=session_id,
                    participant_id=session["participant_id"],
                    episode_pool_id=episode_pool_id,
                    episode_id=selected,
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
