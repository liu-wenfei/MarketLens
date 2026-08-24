"""Frozen participant-facing text mapping; no live translation is permitted."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Mapping

from marketlens.stimulus.manifest import sha256_json


class FrozenTextPackError(ValueError):
    """Raised when participant-facing display text is missing or not frozen."""


def source_text_sha256(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FrozenTextPack:
    pack_id: str
    version: str
    status: str
    translations: Mapping[str, str]
    expected_manifest_sha256: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "translations", MappingProxyType(dict(self.translations)))

    def manifest_payload(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "version": self.version,
            "status": self.status,
            "translations": dict(self.translations),
        }

    def manifest_sha256(self) -> str:
        return sha256_json(self.manifest_payload())

    def validate(self, *, formal: bool) -> None:
        if not self.pack_id.strip() or not self.version.strip():
            raise FrozenTextPackError("text-pack id/version must be non-empty")
        for key, value in self.translations.items():
            if len(key) != 64 or any(ch not in "0123456789abcdef" for ch in key):
                raise FrozenTextPackError(f"invalid source-text SHA-256 key: {key!r}")
            if not isinstance(value, str) or not value.strip():
                raise FrozenTextPackError("participant display translations must be non-empty strings")

        if formal:
            if self.status != "formal_frozen":
                raise FrozenTextPackError(
                    f"formal participant projection rejected: text pack status is {self.status!r}"
                )
            if not self.expected_manifest_sha256:
                raise FrozenTextPackError(
                    "formal participant projection requires an expected frozen text-pack hash"
                )
            if self.manifest_sha256() != self.expected_manifest_sha256:
                raise FrozenTextPackError("frozen participant text-pack hash mismatch")

    def display_text(self, source_text: str, *, formal: bool) -> str:
        self.validate(formal=formal)
        key = source_text_sha256(source_text)
        try:
            return self.translations[key]
        except KeyError as exc:
            raise FrozenTextPackError(
                "participant display text missing from frozen pack; live translation is forbidden"
            ) from exc
