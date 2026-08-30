from __future__ import annotations

import json
from pathlib import Path

from marketlens.episode.contract_v2 import (
    EPISODE_IDS,
    FORMAL_POOL_MANIFEST,
    formal_episode_paths,
    validate_formal_episode_pool_manifest,
)
from marketlens.market.price_provider import (
    CanonicalStockDataClosePriceProvider,
)


class CanonicalJourneyProviderConfigurationError(ValueError):
    pass


def build_canonical_journey_price_providers(
    repo_root: str | Path,
) -> dict[str, CanonicalStockDataClosePriceProvider]:
    root = Path(repo_root).resolve()
    pool_manifest_path = root / FORMAL_POOL_MANIFEST

    if not pool_manifest_path.is_file():
        raise CanonicalJourneyProviderConfigurationError(
            f"formal canonical episode pool manifest not found: "
            f"{pool_manifest_path}"
        )

    try:
        pool_manifest = json.loads(
            pool_manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalJourneyProviderConfigurationError(
            "cannot load formal canonical episode pool manifest"
        ) from exc

    try:
        validate_formal_episode_pool_manifest(
            pool_manifest,
            repo_root=root,
            verify_files=True,
        )
    except Exception as exc:
        raise CanonicalJourneyProviderConfigurationError(
            "formal canonical episode pool failed validation"
        ) from exc

    providers: dict[str, CanonicalStockDataClosePriceProvider] = {}

    for episode_id in EPISODE_IDS:
        paths = formal_episode_paths(episode_id)
        providers[episode_id] = CanonicalStockDataClosePriceProvider(
            root / paths["agent_world_db"]
        )

    return providers
