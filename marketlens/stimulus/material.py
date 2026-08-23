"""Load immutable Phase 11 controlled-stimulus material."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from marketlens.experiment.protocol import load_protocol

from .manifest import verify_hashes
from .schema import FormalUseStatus, StimulusMaterial, StimulusValidationError


def default_development_material_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "marketlens" / "stimuli" / "stimulus_v1.development.json"


def load_material(
    path: str | Path | None = None,
    *,
    formal: bool = False,
    protocol: dict[str, Any] | None = None,
) -> StimulusMaterial:
    source = Path(path) if path is not None else default_development_material_path()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StimulusValidationError(f"cannot load stimulus material: {source}") from exc
    if not isinstance(raw, dict):
        raise StimulusValidationError("stimulus material root must be an object")
    material = StimulusMaterial.from_mapping(raw)
    verify_hashes(material)

    protocol_data = protocol if protocol is not None else load_protocol()
    if material.protocol_version != protocol_data.get("protocol_version"):
        raise StimulusValidationError("stimulus material protocol_version does not match frozen Phase 10 protocol")

    if formal and material.formal_use_status is not FormalUseStatus.FORMAL_FROZEN:
        raise StimulusValidationError(
            "formal mode requires formal_frozen material; development material must fail closed"
        )
    return material
