from __future__ import annotations

from pathlib import Path

import marketlens.main as main_module


def test_explicit_journey_price_providers_skip_factory(monkeypatch, tmp_path: Path):
    explicit = {"episode-a": object()}

    def fail_factory(*args, **kwargs):
        raise AssertionError("factory must not be called")

    captured = {}

    def fake_build_participant_runtime(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        main_module,
        "build_canonical_journey_price_providers",
        fail_factory,
    )
    monkeypatch.setattr(
        main_module,
        "build_participant_runtime",
        fake_build_participant_runtime,
    )

    app = main_module.create_app(
        tmp_path / "human.db",
        participant_runtime_enabled=True,
        participant_event_store=object(),
        background_projections={"episode-a": object()},
        stimulus_engine=object(),
        journey_price_providers=explicit,
    )

    assert app.state.participant_runtime is not None
    assert captured["journey_price_providers"] == explicit


def test_missing_explicit_providers_uses_canonical_factory(
    monkeypatch,
    tmp_path: Path,
):
    generated = {"episode-a": object()}
    captured = {}

    monkeypatch.setattr(
        main_module,
        "build_canonical_journey_price_providers",
        lambda repo_root: generated,
    )

    def fake_build_participant_runtime(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        main_module,
        "build_participant_runtime",
        fake_build_participant_runtime,
    )

    app = main_module.create_app(
        tmp_path / "human.db",
        participant_runtime_enabled=True,
        participant_event_store=object(),
        background_projections={"episode-a": object()},
        stimulus_engine=object(),
    )

    assert app.state.participant_runtime is not None
    assert captured["journey_price_providers"] == generated


def test_create_app_registers_participant_journey_get() -> None:
    app = main_module.create_app()

    paths = app.openapi()["paths"]

    assert "/session/{session_id}/journey" in paths
    assert "get" in paths["/session/{session_id}/journey"]
