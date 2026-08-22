from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import Connection
from sqlalchemy.pool import StaticPool

from .config import sqlite_url_from_path
from .schema import metadata


class Database:
    """Small SQLAlchemy database boundary shared by MarketLens subsystems.

    The existing application can still construct this class with a filesystem
    path. A SQLAlchemy URL can also be supplied, including
    ``postgresql+psycopg://...`` for a future Azure PostgreSQL deployment.
    """

    def __init__(
        self,
        target: str | Path,
        *,
        initialize: bool = True,
    ):
        if isinstance(target, Path):
            url = sqlite_url_from_path(target)
        else:
            target_text = str(target)
            if "://" in target_text or target_text.startswith("sqlite:"):
                url = target_text
            else:
                url = sqlite_url_from_path(target_text)

        engine_kwargs: dict = {
            "future": True,
            "pool_pre_ping": True,
        }
        if url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if url.endswith(":memory:"):
                engine_kwargs["poolclass"] = StaticPool

        self.engine: Engine = create_engine(url, **engine_kwargs)
        self._enable_sqlite_foreign_keys()
        if initialize:
            self.initialize()

    @property
    def dialect_name(self) -> str:
        return self.engine.dialect.name

    @property
    def url(self) -> str:
        return self.engine.url.render_as_string(hide_password=True)

    def _enable_sqlite_foreign_keys(self) -> None:
        if self.dialect_name != "sqlite":
            return

        @event.listens_for(self.engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    @contextmanager
    def connect(self) -> Iterator[Connection]:
        """Open a transaction and commit on success / roll back on failure."""

        with self.engine.begin() as connection:
            yield connection

    def initialize(self) -> None:
        metadata.create_all(self.engine)

    def dispose(self) -> None:
        self.engine.dispose()
