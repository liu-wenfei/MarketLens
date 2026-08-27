"""Frozen MarketLens v2.1 entity-name registry for final English forum posts.

The registry is a generation glossary only. It does not translate or rewrite
stored posts. Unknown entities fall back to stable ticker/index codes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from marketlens.stimulus.manifest import sha256_json


class EntityNameRegistryError(ValueError):
    """Raised when the frozen v2.1 entity-name registry drifts."""


REGISTRY_ID = "marketlens-entity-name-registry-v2.1"
REGISTRY_VERSION = "2.1"
REGISTRY_STATUS = "formal_v2_entity_name_registry_frozen"
EXPECTED_ENTITY_REGISTRY_SHA256 = "0bdf5dfc9851e21440496dfdf220de512965efeed33f6ee67ef68ec91a65ad5b"
EXPECTED_COUNTS = {"sectors": 10, "indices": 10, "companies": 50, "total_entities": 70}


def default_registry_path() -> Path:
    return Path(__file__).with_name("entity_name_registry_v2_1.json")


def entity_registry_sha256(registry: Mapping[str, Any]) -> str:
    return sha256_json(dict(registry))


def validate_entity_registry(registry: Mapping[str, Any]) -> None:
    if entity_registry_sha256(registry) != EXPECTED_ENTITY_REGISTRY_SHA256:
        raise EntityNameRegistryError("MarketLens v2.1 entity-name registry SHA-256 drifted")
    if registry.get("registry_schema_version") != "marketlens-entity-name-registry/2.1":
        raise EntityNameRegistryError("entity-name registry schema drifted")
    if registry.get("registry_id") != REGISTRY_ID:
        raise EntityNameRegistryError("entity-name registry identity drifted")
    if registry.get("registry_version") != REGISTRY_VERSION:
        raise EntityNameRegistryError("entity-name registry version drifted")
    if registry.get("status") != REGISTRY_STATUS:
        raise EntityNameRegistryError("entity-name registry status drifted")
    if registry.get("simulation_reference_date") != "2023-06-15":
        raise EntityNameRegistryError("entity-name registry temporal anchor drifted")
    if registry.get("counts") != EXPECTED_COUNTS:
        raise EntityNameRegistryError("entity-name registry coverage drifted")

    entities = registry.get("entities")
    if not isinstance(entities, list) or len(entities) != EXPECTED_COUNTS["total_entities"]:
        raise EntityNameRegistryError("entity-name registry entity list drifted")
    keys = [str(item.get("canonical_key", "")) for item in entities if isinstance(item, Mapping)]
    if len(keys) != len(set(keys)) or not all(keys):
        raise EntityNameRegistryError("entity-name registry keys are not unique/non-empty")
    if any(not str(item.get("canonical_display_en", "")).strip() for item in entities):
        raise EntityNameRegistryError("entity-name registry contains empty English display name")

    policy = registry.get("policy", {})
    if policy.get("free_model_translation_or_transliteration") is not False:
        raise EntityNameRegistryError("free entity translation/transliteration must remain disabled")
    if policy.get("post_generation_entity_rewriting") is not False:
        raise EntityNameRegistryError("post-generation entity rewriting must remain disabled")
    if policy.get("missing_company_mapping_fallback") != "stock ticker/code":
        raise EntityNameRegistryError("unknown-company fallback policy drifted")


def load_entity_registry(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path is not None else default_registry_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EntityNameRegistryError(f"cannot load v2.1 entity-name registry: {source}") from exc
    if not isinstance(payload, dict):
        raise EntityNameRegistryError("entity-name registry root must be an object")
    validate_entity_registry(payload)
    return payload


def forum_entity_glossary() -> str:
    """Return the frozen compact glossary injected only into the final post call."""
    registry = load_entity_registry()
    groups = (("sector", "Sectors"), ("index", "Indices"), ("company", "Companies"))
    lines: list[str] = []
    for entity_type, heading in groups:
        lines.append(f"{heading}:")
        for item in registry["entities"]:
            if item["entity_type"] != entity_type:
                continue
            key = item["canonical_key"]
            source_zh = item["source_zh"]
            display_en = item["canonical_display_en"]
            lines.append(f"- {key} | {source_zh} => {display_en}")
    return "\n".join(lines)


def registry_summary(path: str | Path | None = None) -> dict[str, Any]:
    registry = load_entity_registry(path)
    return {
        "registry_id": registry["registry_id"],
        "registry_version": registry["registry_version"],
        "status": registry["status"],
        "sha256": EXPECTED_ENTITY_REGISTRY_SHA256,
        "simulation_reference_date": registry["simulation_reference_date"],
        "counts": dict(registry["counts"]),
        "unknown_entity_fallback": "ticker_or_index_code",
        "free_model_translation_or_transliteration": False,
        "post_generation_entity_rewriting": False,
    }
