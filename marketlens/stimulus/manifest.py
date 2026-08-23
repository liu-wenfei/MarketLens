"""Deterministic content and manifest hashing for Phase 11 material."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .schema import StimulusItem, StimulusMaterial, StimulusValidationError


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def item_content_payload(item: StimulusItem) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stimulus_id": item.stimulus_id,
        "kind": item.kind.value,
        "headline": item.headline,
        "body": item.body,
        "release_event": item.release_event,
    }
    if item.corrects_stimulus_id is not None:
        payload["corrects_stimulus_id"] = item.corrects_stimulus_id
    return payload


def expected_item_hash(item: StimulusItem) -> str:
    return sha256_json(item_content_payload(item))


def material_manifest_payload(material: StimulusMaterial) -> dict[str, Any]:
    return {
        "stimulus_set_id": material.stimulus_set_id,
        "material_version": material.material_version,
        "protocol_version": material.protocol_version,
        "target_stock_id": material.target_stock_id,
        "formal_use_status": material.formal_use_status.value,
        "misinformation": {
            "stimulus_id": material.misinformation.stimulus_id,
            "content_sha256": material.misinformation.content_sha256,
        },
        "correction": {
            "stimulus_id": material.correction.stimulus_id,
            "content_sha256": material.correction.content_sha256,
            "corrects_stimulus_id": material.correction.corrects_stimulus_id,
        },
    }


def expected_manifest_hash(material: StimulusMaterial) -> str:
    return sha256_json(material_manifest_payload(material))


def verify_hashes(material: StimulusMaterial) -> None:
    expected_mis = expected_item_hash(material.misinformation)
    expected_corr = expected_item_hash(material.correction)
    expected_manifest = expected_manifest_hash(material)
    if material.misinformation.content_sha256 != expected_mis:
        raise StimulusValidationError("misinformation content_sha256 mismatch")
    if material.correction.content_sha256 != expected_corr:
        raise StimulusValidationError("correction content_sha256 mismatch")
    if material.manifest_sha256 != expected_manifest:
        raise StimulusValidationError("manifest_sha256 mismatch")


def stamp_hashes(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-serializable copy with deterministic hashes filled in.

    Intended for development/material-freeze tooling, not runtime mutation.
    """
    data = json.loads(json.dumps(raw))
    for key in ("misinformation", "correction"):
        item = dict(data[key])
        payload = {k: v for k, v in item.items() if k != "content_sha256"}
        item["content_sha256"] = sha256_json(payload)
        data[key] = item
    material = StimulusMaterial.from_mapping({**data, "manifest_sha256": "0" * 64})
    data["manifest_sha256"] = expected_manifest_hash(material)
    return data
