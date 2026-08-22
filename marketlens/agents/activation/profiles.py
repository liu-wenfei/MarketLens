"""Read the minimal inherited persona fields needed by Phase 4 activation.

Phase 4 consumes the bounded TwinMarket-compatible runtime database produced by
Phase 3B.  Only ``user_id`` and ``trade_count_category`` are read.  Source
status (``user_type``), network prominence, strategy, performance, participant
state and trading outcomes are deliberately not activation inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


ALLOWED_ACTIVITY_CATEGORIES = frozenset({"低", "中", "高"})


class ActivationProfileError(RuntimeError):
    """Raised when a bounded runtime database cannot supply unambiguous profiles."""


@dataclass(frozen=True)
class AgentActivationProfile:
    """Minimal stable persona view required by the Phase 4 policy."""

    user_id: str
    activity_category: str


def _connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise ActivationProfileError(f"runtime population database does not exist: {path}")
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def load_activation_profiles(runtime_db: str | Path) -> tuple[AgentActivationProfile, ...]:
    """Load Phase 4 profiles from the Phase 3B bounded runtime database.

    The query intentionally names only the two allowed fields instead of using
    ``SELECT *``.  This keeps ``user_type`` and other persona attributes outside
    the activation data path by construction.
    """

    path = Path(runtime_db).resolve()
    connection = _connect_read_only(path)
    try:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Profiles'"
        ).fetchone()
        if table is None:
            raise ActivationProfileError("runtime population database is missing Profiles")

        rows = connection.execute(
            """
            SELECT CAST(user_id AS TEXT) AS user_id,
                   CAST(trade_count_category AS TEXT) AS activity_category
            FROM Profiles
            ORDER BY CAST(user_id AS TEXT)
            """
        ).fetchall()
    except sqlite3.Error as exc:
        raise ActivationProfileError(
            "runtime Profiles must contain user_id and trade_count_category"
        ) from exc
    finally:
        connection.close()

    if not rows:
        raise ActivationProfileError("runtime Profiles contains no Agents")

    profiles: list[AgentActivationProfile] = []
    seen: set[str] = set()
    for row in rows:
        user_id = str(row["user_id"]).strip()
        category = str(row["activity_category"]).strip()
        if not user_id:
            raise ActivationProfileError("runtime Profiles contains an empty user_id")
        if user_id in seen:
            raise ActivationProfileError(f"duplicate Agent user_id in runtime Profiles: {user_id}")
        if category not in ALLOWED_ACTIVITY_CATEGORIES:
            raise ActivationProfileError(
                f"Agent {user_id} has unsupported trade_count_category {category!r}"
            )
        seen.add(user_id)
        profiles.append(AgentActivationProfile(user_id=user_id, activity_category=category))

    return tuple(profiles)
