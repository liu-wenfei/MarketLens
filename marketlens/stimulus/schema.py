"""Phase 11 controlled-stimulus schema.

The schema is intentionally participant-only. It contains no Agent, forum,
matching, price-formation, or source-cue presentation fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class StimulusValidationError(ValueError):
    """Raised when Phase 11 controlled-stimulus material is invalid."""


class StimulusKind(str, Enum):
    MISINFORMATION = "misinformation"
    AUTHORITATIVE_CORRECTION = "authoritative_correction"


class FormalUseStatus(str, Enum):
    DEVELOPMENT = "development"
    FORMAL_FROZEN = "formal_frozen"


MISINFORMATION_RELEASE_EVENT = "after_J0_before_J1"
CORRECTION_RELEASE_EVENT = "after_J2_before_J3"

# Fields from the abandoned forum-injection/source-cue routes are rejected so
# they cannot silently re-enter Phase 11 material.
TOP_LEVEL_KEYS = frozenset({
    "stimulus_set_id", "material_version", "protocol_version", "target_stock_id",
    "formal_use_status", "misinformation", "correction", "manifest_sha256",
})
ITEM_BASE_KEYS = frozenset({"stimulus_id", "kind", "headline", "body", "release_event", "content_sha256"})

FORBIDDEN_MATERIAL_KEYS = frozenset(
    {
        "poster_user_id",
        "poster_user_ids",
        "forum_post_id",
        "forum_post_ids",
        "account_count",
        "rumor_day_offset",
        "debunk_day_offset",
        "release_date",
        "agent_id",
        "agent_ids",
        "source_name",
        "source_type",
        "verified",
        "authority_label",
    }
)


def _require_nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StimulusValidationError(f"{field} must be a non-empty string")
    return value.strip()


def reject_forbidden_keys(value: object, path: str = "material") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in FORBIDDEN_MATERIAL_KEYS:
                raise StimulusValidationError(
                    f"{path}.{key} is forbidden in Phase 11; timing comes from Phase 10 and source cues belong to Phase 12"
                )
            reject_forbidden_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_forbidden_keys(child, f"{path}[{index}]")


@dataclass(frozen=True, slots=True)
class StimulusItem:
    stimulus_id: str
    kind: StimulusKind
    headline: str
    body: str
    release_event: str
    content_sha256: str
    corrects_stimulus_id: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, field: str) -> "StimulusItem":
        allowed = ITEM_BASE_KEYS | ({"corrects_stimulus_id"} if field == "correction" else set())
        unknown = set(raw) - set(allowed)
        if unknown:
            raise StimulusValidationError(f"{field} contains unsupported Phase 11 fields: {sorted(unknown)}")
        stimulus_id = _require_nonempty_string(raw.get("stimulus_id"), f"{field}.stimulus_id")
        try:
            kind = StimulusKind(raw.get("kind"))
        except ValueError as exc:
            raise StimulusValidationError(f"{field}.kind is invalid") from exc
        headline = _require_nonempty_string(raw.get("headline"), f"{field}.headline")
        body = _require_nonempty_string(raw.get("body"), f"{field}.body")
        release_event = _require_nonempty_string(raw.get("release_event"), f"{field}.release_event")
        content_sha256 = _require_nonempty_string(raw.get("content_sha256"), f"{field}.content_sha256")
        if len(content_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in content_sha256):
            raise StimulusValidationError(f"{field}.content_sha256 must be lowercase SHA-256 hex")
        corrects = raw.get("corrects_stimulus_id")
        if corrects is not None:
            corrects = _require_nonempty_string(corrects, f"{field}.corrects_stimulus_id")
        return cls(
            stimulus_id=stimulus_id,
            kind=kind,
            headline=headline,
            body=body,
            release_event=release_event,
            content_sha256=content_sha256,
            corrects_stimulus_id=corrects,
        )


@dataclass(frozen=True, slots=True)
class StimulusMaterial:
    stimulus_set_id: str
    material_version: str
    protocol_version: str
    target_stock_id: str
    formal_use_status: FormalUseStatus
    misinformation: StimulusItem
    correction: StimulusItem
    manifest_sha256: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "StimulusMaterial":
        reject_forbidden_keys(raw)
        unknown = set(raw) - set(TOP_LEVEL_KEYS)
        if unknown:
            raise StimulusValidationError(f"material contains unsupported Phase 11 fields: {sorted(unknown)}")
        try:
            formal_use_status = FormalUseStatus(raw.get("formal_use_status"))
        except ValueError as exc:
            raise StimulusValidationError("formal_use_status is invalid") from exc
        misinformation_raw = raw.get("misinformation")
        correction_raw = raw.get("correction")
        if not isinstance(misinformation_raw, Mapping) or not isinstance(correction_raw, Mapping):
            raise StimulusValidationError("misinformation and correction objects are required")
        material = cls(
            stimulus_set_id=_require_nonempty_string(raw.get("stimulus_set_id"), "stimulus_set_id"),
            material_version=_require_nonempty_string(raw.get("material_version"), "material_version"),
            protocol_version=_require_nonempty_string(raw.get("protocol_version"), "protocol_version"),
            target_stock_id=_require_nonempty_string(raw.get("target_stock_id"), "target_stock_id"),
            formal_use_status=formal_use_status,
            misinformation=StimulusItem.from_mapping(misinformation_raw, field="misinformation"),
            correction=StimulusItem.from_mapping(correction_raw, field="correction"),
            manifest_sha256=_require_nonempty_string(raw.get("manifest_sha256"), "manifest_sha256"),
        )
        if len(material.manifest_sha256) != 64 or any(
            ch not in "0123456789abcdef" for ch in material.manifest_sha256
        ):
            raise StimulusValidationError("manifest_sha256 must be lowercase SHA-256 hex")
        if material.misinformation.kind is not StimulusKind.MISINFORMATION:
            raise StimulusValidationError("misinformation.kind must be misinformation")
        if material.correction.kind is not StimulusKind.AUTHORITATIVE_CORRECTION:
            raise StimulusValidationError("correction.kind must be authoritative_correction")
        if material.misinformation.release_event != MISINFORMATION_RELEASE_EVENT:
            raise StimulusValidationError("misinformation release_event must be after_J0_before_J1")
        if material.correction.release_event != CORRECTION_RELEASE_EVENT:
            raise StimulusValidationError("correction release_event must be after_J2_before_J3")
        if material.misinformation.corrects_stimulus_id is not None:
            raise StimulusValidationError("misinformation cannot correct another stimulus")
        if material.correction.corrects_stimulus_id != material.misinformation.stimulus_id:
            raise StimulusValidationError("correction must explicitly correct the misinformation stimulus_id")
        if material.correction.stimulus_id == material.misinformation.stimulus_id:
            raise StimulusValidationError("misinformation and correction stimulus_ids must differ")
        return material
