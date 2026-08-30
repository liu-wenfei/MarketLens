from __future__ import annotations

import json
from pathlib import Path

import pytest

import marketlens.human.services.journey_provider_factory as factory_module
from marketlens.human.services.journey_provider_factory import (
    CanonicalJourneyProviderConfigurationError,
    build_canonical_journey_price_providers,
)


def test_builds_episode_keyed_canonical_providers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pool_manifest = tmp_path / "pool_manifest.json"
    pool_manifest.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        factory_module,
        "FORMAL_POOL_MANIFEST",
        "pool_manifest.json",
    )
    monkeypatch.setattr(
        factory_module,
        "EPISODE_IDS",
        ("episode-a", "episode-b"),
    )
    monkeypatch.setattr(
        factory_module,
        "formal_episode_paths",
        lambda episode_id: {
            "agent_world_db": f"{episode_id}.db",
        },
    )

    for episode_id in ("episode-a", "episode-b"):
        (tmp_path / f"{episode_id}.db").write_bytes(b"db")

    validated = []

    def fake_validate(manifest, *, repo_root, verify_files):
        validated.append(
            (manifest, Path(repo_root), verify_files)
        )

    monkeypatch.setattr(
        factory_module,
        "validate_formal_episode_pool_manifest",
        fake_validate,
    )

    created = {}

    class FakeProvider:
        def __init__(self, runtime_db):
            self.runtime_db = Path(runtime_db)
            created[self.runtime_db.name] = self

    monkeypatch.setattr(
        factory_module,
        "CanonicalStockDataClosePriceProvider",
        FakeProvider,
    )

    providers = build_canonical_journey_price_providers(
        tmp_path
    )

    assert set(providers) == {"episode-a", "episode-b"}
    assert providers["episode-a"].runtime_db == (
        tmp_path / "episode-a.db"
    )
    assert providers["episode-b"].runtime_db == (
        tmp_path / "episode-b.db"
    )

    assert validated == [
        ({}, tmp_path.resolve(), True)
    ]


def test_missing_pool_manifest_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        factory_module,
        "FORMAL_POOL_MANIFEST",
        "missing.json",
    )

    with pytest.raises(
        CanonicalJourneyProviderConfigurationError,
        match="formal canonical episode pool manifest not found",
    ):
        build_canonical_journey_price_providers(tmp_path)


def test_invalid_pool_manifest_fails_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pool_manifest = tmp_path / "pool_manifest.json"
    pool_manifest.write_text(
        json.dumps({"status": "invalid"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        factory_module,
        "FORMAL_POOL_MANIFEST",
        "pool_manifest.json",
    )

    def fail_validation(*args, **kwargs):
        raise ValueError("invalid formal pool")

    monkeypatch.setattr(
        factory_module,
        "validate_formal_episode_pool_manifest",
        fail_validation,
    )

    with pytest.raises(
        CanonicalJourneyProviderConfigurationError,
        match="formal canonical episode pool failed validation",
    ):
        build_canonical_journey_price_providers(tmp_path)
