from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.engine import URL


DEFAULT_SQLITE_PATH = (
    Path(__file__).resolve().parents[1]
    / "human"
    / "data"
    / "marketlens_human.db"
)


def sqlite_url_from_path(path: str | Path) -> str:
    path_text = str(path)
    if path_text == ":memory:":
        return "sqlite+pysqlite:///:memory:"
    resolved = Path(path).expanduser().resolve()
    return URL.create("sqlite+pysqlite", database=str(resolved)).render_as_string(
        hide_password=False
    )


def resolve_database_url(
    *,
    explicit_url: str | None = None,
    legacy_path: str | Path | None = None,
) -> str:
    """Resolve the database connection target without changing old local callers.

    Preferred order:
      1. explicit ``database_url``
      2. ``MARKETLENS_DATABASE_URL``
      3. explicit legacy path supplied to ``create_app``
      4. ``MARKETLENS_DB_PATH``
      5. the existing local SQLite development path
    """

    if explicit_url:
        return explicit_url

    environment_url = os.environ.get("MARKETLENS_DATABASE_URL")
    if environment_url:
        return environment_url

    if legacy_path is not None:
        return sqlite_url_from_path(legacy_path)

    environment_path = os.environ.get("MARKETLENS_DB_PATH")
    if environment_path:
        return sqlite_url_from_path(environment_path)

    return sqlite_url_from_path(DEFAULT_SQLITE_PATH)


def resolve_auto_create_schema(explicit: bool | None = None) -> bool:
    """Return whether application startup may create missing tables.

    Local development defaults to True for backwards compatibility. Formal or
    production deployments should run Alembic first and set
    ``MARKETLENS_AUTO_CREATE_SCHEMA=0``.
    """

    if explicit is not None:
        return explicit

    value = os.environ.get("MARKETLENS_AUTO_CREATE_SCHEMA")
    if value is None:
        return True

    normalised = value.strip().lower()
    if normalised in {"1", "true", "yes", "on"}:
        return True
    if normalised in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        "MARKETLENS_AUTO_CREATE_SCHEMA must be one of: 1/0, true/false, yes/no, on/off"
    )
