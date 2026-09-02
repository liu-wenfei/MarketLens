from __future__ import annotations

from types import SimpleNamespace

import pytest

import marketlens.formal_study_startup as startup


def test_formal_data_paths_are_exact_and_separate(tmp_path):
    root, runtime_db, event_db = startup.resolve_formal_data_paths(
        tmp_path
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


def test_formal_startup_rejects_generic_database_override(tmp_path):
    with pytest.raises(
        startup.FormalStudyStartupConfigurationError,
        match="MARKETLENS_DATABASE_URL",
    ):
        startup.create_persistent_formal_participant_app(
            repo_root=tmp_path,
            environ={
                "MARKETLENS_DATABASE_URL": "sqlite:///unexpected.db"
            },
        )


def test_persistent_formal_factory_injects_paths_and_live_feedback(
    monkeypatch,
    tmp_path,
):
    calls: dict[str, object] = {}
    fake_generator = object()
    fake_app = SimpleNamespace(state=SimpleNamespace())

    def fake_generator_factory(**kwargs):
        calls["generator_kwargs"] = kwargs
        return fake_generator

    def fake_formal_factory(**kwargs):
        calls["formal_factory_kwargs"] = kwargs
        return fake_app

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
    expected_runtime = expected_dir / "participant_runtime.db"
    expected_events = expected_dir / "participant_events.db"

    assert app is fake_app
    assert expected_dir.is_dir()
    assert calls["generator_kwargs"] == {"environ": {}}

    kwargs = calls["formal_factory_kwargs"]
    assert kwargs == {
        "repo_root": tmp_path.resolve(),
        "db_path": expected_runtime,
        "participant_event_db_path": expected_events,
        "feedback_generator": fake_generator,
    }

    assert app.state.formal_study_runtime_db_path == str(
        expected_runtime
    )
    assert app.state.formal_study_event_db_path == str(
        expected_events
    )
    assert (
        app.state.formal_study_startup_mode
        == "persistent_local_preauth"
    )


def test_preauth_entrypoint_is_loopback_only():
    assert startup.LOCAL_PREAUTH_HOST == "127.0.0.1"
    assert startup.LOCAL_PREAUTH_PORT == 8000
