from __future__ import annotations

import json

import pytest

from marketlens.stimulus import FormalUseStatus, StimulusValidationError, load_material
from marketlens.stimulus.manifest import stamp_hashes
from marketlens.stimulus.schema import StimulusMaterial


def test_development_material_is_immutable_valid_and_bound_to_protocol_v1_1():
    material = load_material()
    assert material.protocol_version == "1.1"
    assert material.formal_use_status is FormalUseStatus.DEVELOPMENT
    assert material.misinformation.stimulus_id == "MISINFO_DEV_001"
    assert material.correction.corrects_stimulus_id == material.misinformation.stimulus_id
    with pytest.raises(Exception):
        material.target_stock_id = "OTHER"  # type: ignore[misc]


def test_formal_mode_fails_closed_on_development_material():
    with pytest.raises(StimulusValidationError, match="formal_frozen"):
        load_material(formal=True)


def test_material_rejects_old_forum_injection_and_duplicate_timing_fields():
    raw = json.loads(load_material_path().read_text(encoding="utf-8"))
    raw["misinformation"]["poster_user_ids"] = ["123"]
    with pytest.raises(StimulusValidationError, match="forbidden"):
        StimulusMaterial.from_mapping(raw)

    raw = json.loads(load_material_path().read_text(encoding="utf-8"))
    raw["correction"]["release_date"] = "2023-06-30"
    with pytest.raises(StimulusValidationError, match="forbidden"):
        StimulusMaterial.from_mapping(raw)


def test_hash_tamper_is_rejected(tmp_path):
    raw = json.loads(load_material_path().read_text(encoding="utf-8"))
    raw["misinformation"]["body"] += " tampered"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(StimulusValidationError, match="content_sha256 mismatch"):
        load_material(path)


def test_formal_frozen_status_can_only_pass_when_hashes_are_recomputed(tmp_path):
    raw = json.loads(load_material_path().read_text(encoding="utf-8"))
    raw["formal_use_status"] = "formal_frozen"
    stamped = stamp_hashes(raw)
    path = tmp_path / "formal.json"
    path.write_text(json.dumps(stamped), encoding="utf-8")
    material = load_material(path, formal=True)
    assert material.formal_use_status is FormalUseStatus.FORMAL_FROZEN


def load_material_path():
    from marketlens.stimulus.material import default_development_material_path

    return default_development_material_path()


def test_material_rejects_unknown_phase12_or_legacy_fields_even_if_not_named_in_forbidden_list():
    raw = json.loads(load_material_path().read_text(encoding="utf-8"))
    raw["misinformation"]["source_logo_url"] = "https://example.invalid/logo.png"
    with pytest.raises(StimulusValidationError, match="unsupported Phase 11 fields"):
        StimulusMaterial.from_mapping(raw)
