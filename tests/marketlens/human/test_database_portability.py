from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from marketlens.main import create_app
from marketlens.persistence.config import sqlite_url_from_path
from marketlens.persistence.database import Database
from marketlens.persistence.schema import metadata


def test_create_app_accepts_database_url_without_changing_existing_api(tmp_path):
    database_url = sqlite_url_from_path(tmp_path / "url-config.db")
    with TestClient(create_app(database_url=database_url)) as client:
        response = client.post(
            "/session",
            json={"participant_id": "P001", "request_id": "url-session"},
        )
        assert response.status_code == 201
        assert client.app.state.db.dialect_name == "sqlite"


def test_marketlens_database_url_environment_is_preferred(monkeypatch, tmp_path):
    database_url = sqlite_url_from_path(tmp_path / "environment.db")
    monkeypatch.setenv("MARKETLENS_DATABASE_URL", database_url)
    monkeypatch.setenv("MARKETLENS_DB_PATH", str(tmp_path / "legacy-ignored.db"))

    with TestClient(create_app()) as client:
        assert client.app.state.db.url == database_url
        assert client.post(
            "/session",
            json={"participant_id": "P001", "request_id": "environment-session"},
        ).status_code == 201

    assert (tmp_path / "environment.db").exists()
    assert not (tmp_path / "legacy-ignored.db").exists()


def test_schema_compiles_for_postgresql_without_a_live_server():
    dialect = postgresql.dialect()
    compiled = {
        table.name: str(CreateTable(table).compile(dialect=dialect))
        for table in metadata.sorted_tables
    }
    assert set(compiled) == {
        "sessions",
        "decisions",
        "round_completions",
        "participant_episode_assignments",
        "participant_judgements",
        "participant_portfolios",
        "portfolio_holdings",
        "portfolio_transactions",
    }
    assert all("CREATE TABLE" in ddl for ddl in compiled.values())


def test_initial_alembic_migration_builds_current_schema(tmp_path, monkeypatch):
    database_path = tmp_path / "migration.db"
    monkeypatch.setenv("MARKETLENS_DATABASE_URL", sqlite_url_from_path(database_path))

    repo_root = Path(__file__).resolve().parents[3]
    config = Config(str(repo_root / "alembic.ini"))
    command.upgrade(config, "head")

    db = Database(sqlite_url_from_path(database_path), initialize=False)
    try:
        table_names = set(inspect(db.engine).get_table_names())
    finally:
        db.dispose()

    assert {
        "alembic_version",
        "sessions",
        "decisions",
        "round_completions",
        "participant_episode_assignments",
        "participant_judgements",
        "participant_portfolios",
        "portfolio_holdings",
        "portfolio_transactions",
    }.issubset(table_names)
