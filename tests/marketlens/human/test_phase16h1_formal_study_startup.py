from __future__ import annotations

from types import SimpleNamespace

import pytest

import marketlens.formal_study_startup as startup


def test_formal_data_paths_are_exact_and_separate(
    tmp_path,
):
    root, runtime_db, event_db = (
        startup.resolve_formal_data_paths(
            tmp_path
        )
    )

    assert root == tmp_path.resolve()
    assert runtime_db == (
        root
        / "data"
        / "marketlens"
        / "human"
        / "formal"
        / "participant_runtime.db"
    )
    assert event_db == (
        root
        / "data"
        / "marketlens"
        / "human"
        / "formal"
        / "participant_events.db"
    )
    assert runtime_db != event_db


def test_formal_auth_path_is_separate(
    tmp_path,
):
    root, runtime_db, event_db = (
        startup.resolve_formal_data_paths(
            tmp_path
        )
    )
    auth_db = startup.resolve_formal_auth_db_path(
        tmp_path
    )

    assert auth_db == (
        root
        / "data"
        / "marketlens"
        / "human"
        / "formal"
        / "participant_auth.db"
    )
    assert auth_db not in {
        runtime_db,
        event_db,
    }


def test_formal_startup_rejects_generic_database_override(
    tmp_path,
):
    with pytest.raises(
        startup.FormalStudyStartupConfigurationError,
        match="MARKETLENS_DATABASE_URL",
    ):
        startup.create_persistent_formal_participant_app(
            repo_root=tmp_path,
            environ={
                "MARKETLENS_DATABASE_URL": (
                    "sqlite:///unexpected.db"
                )
            },
        )


def test_persistent_formal_factory_injects_all_paths_and_auth(
    monkeypatch,
    tmp_path,
):
    calls: dict[str, object] = {}
    fake_generator = object()
    fake_inner = SimpleNamespace(
        state=SimpleNamespace()
    )
    fake_gateway = SimpleNamespace(
        state=SimpleNamespace()
    )
    fake_auth_store = object()

    def fake_generator_factory(**kwargs):
        calls["generator_kwargs"] = kwargs
        return fake_generator

    def fake_formal_factory(**kwargs):
        calls["formal_factory_kwargs"] = kwargs
        return fake_inner

    def fake_auth_store_factory(path):
        calls["auth_store_path"] = path
        return fake_auth_store

    def fake_gateway_factory(**kwargs):
        calls["gateway_kwargs"] = kwargs
        return fake_gateway

    def fake_permission_enforcer(*paths):
        calls["permission_paths"] = paths

    monkeypatch.setattr(
        startup,
        "create_formal_openai_feedback_generator",
        fake_generator_factory,
    )
    monkeypatch.setattr(
        startup,
        "create_formal_participant_app",
        fake_formal_factory,
    )
    monkeypatch.setattr(
        startup,
        "FormalAuthStore",
        fake_auth_store_factory,
    )
    monkeypatch.setattr(
        startup,
        "create_authenticated_formal_gateway",
        fake_gateway_factory,
    )
    monkeypatch.setattr(
        startup,
        "_enforce_private_formal_db_permissions",
        fake_permission_enforcer,
    )

    app = startup.create_persistent_formal_participant_app(
        repo_root=tmp_path,
        environ={},
    )

    expected_dir = (
        tmp_path.resolve()
        / "data"
        / "marketlens"
        / "human"
        / "formal"
    )
    expected_runtime = (
        expected_dir / "participant_runtime.db"
    )
    expected_events = (
        expected_dir / "participant_events.db"
    )
    expected_auth = (
        expected_dir / "participant_auth.db"
    )

    assert app is fake_gateway
    assert expected_dir.is_dir()
    assert calls["generator_kwargs"] == {
        "environ": {}
    }

    assert calls["formal_factory_kwargs"] == {
        "repo_root": tmp_path.resolve(),
        "db_path": expected_runtime,
        "participant_event_db_path": (
            expected_events
        ),
        "allowed_origins": (
            "http://localhost:5173",
        ),
        "feedback_generator": fake_generator,
    }
    assert calls["auth_store_path"] == (
        expected_auth
    )
    assert calls["permission_paths"] == (
        expected_runtime,
        expected_events,
        expected_auth,
    )
    assert calls["gateway_kwargs"] == {
        "inner_app": fake_inner,
        "auth_store": fake_auth_store,
        "allowed_origins": (
            "http://localhost:5173",
        ),
    }

    assert (
        app.state.formal_study_runtime_db_path
        == str(expected_runtime)
    )
    assert (
        app.state.formal_study_event_db_path
        == str(expected_events)
    )
    assert (
        app.state.formal_study_auth_db_path
        == str(expected_auth)
    )
    assert (
        app.state.formal_study_startup_mode
        == "persistent_local_authenticated"
    )


def test_acceptance_entrypoint_remains_loopback_only():
    assert startup.LOCAL_PREAUTH_HOST == "127.0.0.1"
    assert startup.LOCAL_PREAUTH_PORT == 8000


def test_private_formal_db_permissions_are_enforced(
    tmp_path,
):
    paths = (
        tmp_path / "participant_runtime.db",
        tmp_path / "participant_events.db",
        tmp_path / "participant_auth.db",
    )

    for path in paths:
        path.write_bytes(b"sqlite-placeholder")
        path.chmod(0o644)

    startup._enforce_private_formal_db_permissions(
        *paths
    )

    assert {
        path.stat().st_mode & 0o777
        for path in paths
    } == {0o600}


def test_private_formal_db_permissions_fail_closed_when_missing(
    tmp_path,
):
    missing = tmp_path / "missing.db"

    with pytest.raises(
        startup.FormalStudyStartupConfigurationError,
        match="was not created as expected",
    ):
        startup._enforce_private_formal_db_permissions(
            missing
        )
