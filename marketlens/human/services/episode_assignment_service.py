from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from random import SystemRandom
from typing import Callable, Sequence
from uuid import uuid4

from marketlens.episode.contract import (
    EPISODE_POOL_ID as DEFAULT_EPISODE_POOL_ID,
)
from marketlens.human.services.session_service import SessionNotFoundError
from marketlens.human.stores.episode_assignment_store import (
    EpisodeAssignmentStore,
    StoreEpisodeAssignmentConflictError,
    StoreEpisodeAssignmentValidationError,
)
from marketlens.human.stores.errors import StoreSessionNotFoundError


FORMAL_ASSIGNMENT_METHOD = "balanced_random_across_episode_pool"
ASSIGNMENT_BINDING_VERSION = "phase14b1-v1"
FORMAL_ALLOCATOR_VERSION = "phase15a2-balanced-random-v1"


class EpisodeAssignmentConflictError(ValueError):
    pass


class EpisodeAssignmentValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParticipantEpisodeAssignment:
    assignment_id: str
    session_id: str
    participant_id: str
    episode_pool_id: str
    episode_id: str
    assignment_method: str
    assignment_version: str
    assigned_at: str


def _to_assignment(row) -> ParticipantEpisodeAssignment:
    return ParticipantEpisodeAssignment(
        assignment_id=row["assignment_id"],
        session_id=row["session_id"],
        participant_id=row["participant_id"],
        episode_pool_id=row["episode_pool_id"],
        episode_id=row["episode_id"],
        assignment_method=row["assignment_method"],
        assignment_version=row["assignment_version"],
        assigned_at=row["assigned_at"],
    )


_SYSTEM_RANDOM = SystemRandom()


class EpisodeAssignmentService:
    """Persist explicit bindings and perform formal server-owned allocation."""

    def __init__(
        self,
        store: EpisodeAssignmentStore,
        *,
        episode_pool_id: str = DEFAULT_EPISODE_POOL_ID,
        formal_chooser: Callable[[Sequence[str]], str] | None = None,
    ):
        if not str(episode_pool_id).strip():
            raise EpisodeAssignmentValidationError(
                "episode_pool_id must be non-empty"
            )

        self.store = store
        self.episode_pool_id = str(episode_pool_id)
        self.formal_chooser = formal_chooser or _SYSTEM_RANDOM.choice

    def get(self, session_id: str) -> ParticipantEpisodeAssignment | None:
        row = self.store.get(session_id)
        return None if row is None else _to_assignment(row)

    def bind(
        self,
        session_id: str,
        episode_id: str,
        *,
        assignment_method: str = FORMAL_ASSIGNMENT_METHOD,
        assignment_version: str = ASSIGNMENT_BINDING_VERSION,
    ) -> ParticipantEpisodeAssignment:
        now = datetime.now(timezone.utc).isoformat()
        try:
            row = self.store.bind_idempotent(
                assignment_id=str(uuid4()),
                session_id=session_id,
                episode_pool_id=self.episode_pool_id,
                episode_id=episode_id,
                assignment_method=assignment_method,
                assignment_version=assignment_version,
                assigned_at=now,
            )
        except StoreSessionNotFoundError as exc:
            raise SessionNotFoundError(session_id) from exc
        except StoreEpisodeAssignmentConflictError as exc:
            raise EpisodeAssignmentConflictError(str(exc)) from exc
        except StoreEpisodeAssignmentValidationError as exc:
            raise EpisodeAssignmentValidationError(str(exc)) from exc
        return _to_assignment(row)

    def allocate_balanced_random(
        self,
        session_id: str,
    ) -> ParticipantEpisodeAssignment:
        """Allocate one frozen episode without accepting any client episode input."""

        now = datetime.now(timezone.utc).isoformat()
        try:
            row = self.store.allocate_balanced_idempotent(
                assignment_id=str(uuid4()),
                session_id=session_id,
                episode_pool_id=self.episode_pool_id,
                assignment_method=FORMAL_ASSIGNMENT_METHOD,
                assignment_version=FORMAL_ALLOCATOR_VERSION,
                assigned_at=now,
                chooser=self.formal_chooser,
            )
        except StoreSessionNotFoundError as exc:
            raise SessionNotFoundError(session_id) from exc
        except StoreEpisodeAssignmentConflictError as exc:
            raise EpisodeAssignmentConflictError(str(exc)) from exc
        except StoreEpisodeAssignmentValidationError as exc:
            raise EpisodeAssignmentValidationError(str(exc)) from exc
        return _to_assignment(row)
