"""Read-only binding contract for a sealed canonical TwinMarket episode.

Phase 13B deliberately does not create, copy, or mutate an Agent world.  It only
binds participant projection to an explicitly supplied pair of canonical working
DBs.  Formal use requires both DB files to be hash-pinned.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


class CanonicalEpisodeBindingError(ValueError):
    """Raised when canonical episode identity cannot be verified exactly."""


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class CanonicalEpisodeBinding:
    episode_id: str
    user_db_path: Path
    forum_db_path: Path
    status: str = "development"
    user_db_sha256: str | None = None
    forum_db_sha256: str | None = None

    def validate(self, *, formal: bool) -> None:
        user_db = Path(self.user_db_path).expanduser().resolve()
        forum_db = Path(self.forum_db_path).expanduser().resolve()
        if not self.episode_id.strip():
            raise CanonicalEpisodeBindingError("canonical episode_id must be non-empty")
        if not user_db.is_file():
            raise CanonicalEpisodeBindingError(f"canonical user DB not found: {user_db}")
        if not forum_db.is_file():
            raise CanonicalEpisodeBindingError(f"canonical forum DB not found: {forum_db}")

        if formal:
            if self.status != "formal_frozen":
                raise CanonicalEpisodeBindingError(
                    f"formal participant projection rejected: canonical episode status is {self.status!r}"
                )
            if not self.user_db_sha256 or not self.forum_db_sha256:
                raise CanonicalEpisodeBindingError(
                    "formal participant projection requires frozen user/forum DB SHA-256 values"
                )
            actual_user = _file_sha256(user_db)
            actual_forum = _file_sha256(forum_db)
            if actual_user != self.user_db_sha256:
                raise CanonicalEpisodeBindingError("canonical user DB SHA-256 mismatch")
            if actual_forum != self.forum_db_sha256:
                raise CanonicalEpisodeBindingError("canonical forum DB SHA-256 mismatch")

    @property
    def resolved_user_db_path(self) -> Path:
        return Path(self.user_db_path).expanduser().resolve()

    @property
    def resolved_forum_db_path(self) -> Path:
        return Path(self.forum_db_path).expanduser().resolve()
