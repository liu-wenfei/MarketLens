#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.information.text_pack import (
    FrozenTextPack,
    source_text_sha256,
)


INVENTORY = (
    REPO_ROOT
    / "data/marketlens/information/"
    / "participant_source_text_inventory_v2.json"
)

REVIEW = (
    REPO_ROOT
    / "data/marketlens/information/"
    / "participant_natural_news_translation_review_v2.csv"
)

OUTPUT = (
    REPO_ROOT
    / "data/marketlens/information/"
    / "participant_text_pack_v2.formal.json"
)

PACK_ID = "marketlens-participant-text-pack-v2"
VERSION = "2.0"
STATUS = "formal_frozen"

EXPECTED_INVENTORY_SCHEMA = (
    "marketlens-participant-source-text-inventory/1.0"
)

EXPECTED_POOL = "marketlens-canonical-episode-pool-v2"


def load_inventory() -> list[dict]:
    payload = json.loads(
        INVENTORY.read_text(encoding="utf-8")
    )

    if (
        payload.get("inventory_schema_version")
        != EXPECTED_INVENTORY_SCHEMA
    ):
        raise RuntimeError(
            "unexpected source inventory schema"
        )

    if payload.get("canonical_episode_pool") != EXPECTED_POOL:
        raise RuntimeError(
            "source inventory is not bound to canonical pool v2"
        )

    if payload.get("record_count") != 681:
        raise RuntimeError(
            "source inventory must contain exactly 681 records"
        )

    records = payload.get("records")

    if not isinstance(records, list) or len(records) != 681:
        raise RuntimeError(
            "source inventory records malformed"
        )

    return records


def load_review() -> dict[str, dict]:
    with REVIEW.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))

    if len(rows) != 102:
        raise RuntimeError(
            "natural-news review must contain exactly 102 records"
        )

    output: dict[str, dict] = {}

    for row in rows:
        digest = row["source_text_sha256"]
        source = row["source_text_zh"]
        display = row["display_text_en"]
        status = row["review_status"]

        if digest in output:
            raise RuntimeError(
                f"duplicate review SHA: {digest}"
            )

        if source_text_sha256(source) != digest:
            raise RuntimeError(
                f"review source SHA mismatch: {digest}"
            )

        if status != "REVIEWED":
            raise RuntimeError(
                f"unreviewed natural-news record: {digest}"
            )

        if not display.strip():
            raise RuntimeError(
                f"blank reviewed translation: {digest}"
            )

        output[digest] = row

    return output


def build_translations(
    inventory: list[dict],
    review: dict[str, dict],
) -> dict[str, str]:
    translations: dict[str, str] = {}
    kinds = Counter()
    natural_news_hashes: set[str] = set()

    for row in inventory:
        digest = row.get("source_text_sha256")
        kind = row.get("source_kind")
        source = row.get("source_text")

        if not isinstance(digest, str):
            raise RuntimeError(
                "inventory SHA must be text"
            )

        if not isinstance(source, str) or not source.strip():
            raise RuntimeError(
                f"invalid inventory source: {digest}"
            )

        if source_text_sha256(source) != digest:
            raise RuntimeError(
                f"inventory source SHA mismatch: {digest}"
            )

        if digest in translations:
            raise RuntimeError(
                f"duplicate inventory SHA: {digest}"
            )

        kinds[kind] += 1

        if kind == "natural_news":
            natural_news_hashes.add(digest)

            try:
                reviewed = review[digest]
            except KeyError as exc:
                raise RuntimeError(
                    "natural-news source missing reviewed "
                    f"translation: {digest}"
                ) from exc

            if reviewed["source_text_zh"] != source:
                raise RuntimeError(
                    "natural-news exact source mismatch "
                    f"for SHA: {digest}"
                )

            translations[digest] = (
                reviewed["display_text_en"]
            )

        elif kind == "forum_post":
            # Formal forum source texts are already English.
            # Preserve exact participant-visible source text.
            translations[digest] = source

        else:
            raise RuntimeError(
                f"unexpected source kind: {kind!r}"
            )

    if kinds != Counter(
        {
            "natural_news": 102,
            "forum_post": 579,
        }
    ):
        raise RuntimeError(
            f"unexpected inventory composition: {dict(kinds)}"
        )

    if set(review) != natural_news_hashes:
        missing = natural_news_hashes - set(review)
        extra = set(review) - natural_news_hashes

        raise RuntimeError(
            "review/inventory natural-news SHA set mismatch: "
            f"missing={len(missing)} extra={len(extra)}"
        )

    if len(translations) != 681:
        raise RuntimeError(
            "formal text pack must contain exactly 681 mappings"
        )

    return translations


def main() -> int:
    print("=" * 68)
    print("MARKETLENS F4B — BUILD FORMAL PARTICIPANT TEXT PACK V2")
    print("ZERO LLM / DETERMINISTIC / SHA-BOUND")
    print("=" * 68)

    inventory = load_inventory()
    review = load_review()

    translations = build_translations(
        inventory,
        review,
    )

    # Sort explicitly so the serialized artifact is deterministic.
    translations = dict(sorted(translations.items()))

    base = FrozenTextPack(
        pack_id=PACK_ID,
        version=VERSION,
        status=STATUS,
        translations=translations,
    )

    manifest_sha256 = base.manifest_sha256()

    formal = FrozenTextPack(
        pack_id=PACK_ID,
        version=VERSION,
        status=STATUS,
        translations=translations,
        expected_manifest_sha256=manifest_sha256,
    )

    formal.validate(formal=True)

    artifact = {
        **formal.manifest_payload(),
        "expected_manifest_sha256": manifest_sha256,
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(
            artifact,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    # Reload from disk and validate independently.
    loaded = json.loads(
        OUTPUT.read_text(encoding="utf-8")
    )

    reloaded = FrozenTextPack(
        pack_id=loaded["pack_id"],
        version=loaded["version"],
        status=loaded["status"],
        translations=loaded["translations"],
        expected_manifest_sha256=(
            loaded["expected_manifest_sha256"]
        ),
    )

    reloaded.validate(formal=True)

    if (
        reloaded.manifest_sha256()
        != manifest_sha256
    ):
        raise RuntimeError(
            "reloaded formal text-pack hash mismatch"
        )

    if len(reloaded.translations) != 681:
        raise RuntimeError(
            "reloaded mapping count mismatch"
        )

    print("inventory_records:", len(inventory))
    print("reviewed_natural_news:", len(review))
    print("forum_identity_mappings:", 579)
    print("natural_news_translations:", 102)
    print(
        "formal_translation_mappings:",
        len(reloaded.translations),
    )
    print("pack_id:", PACK_ID)
    print("version:", VERSION)
    print("status:", STATUS)
    print(
        "manifest_sha256:",
        manifest_sha256,
    )
    print(
        "artifact:",
        OUTPUT.relative_to(REPO_ROOT),
    )

    print()
    print("PASS: inventory contract")
    print("PASS: 102 reviewed natural-news SHA joins")
    print("PASS: exact natural-news source equality")
    print("PASS: 579 forum identity mappings")
    print("PASS: 681 unique SHA-bound mappings")
    print("PASS: deterministic sorted serialization")
    print("PASS: formal FrozenTextPack validation")
    print("PASS: artifact reload validation")
    print("PASS: manifest SHA pinned")

    print()
    print("F4B_FORMAL_TEXT_PACK_BUILD_PASS")
    print("PROJECTION VALIDATION: NOT RUN YET")
    print("COMMITTED: NO")
    print("PUSHED: NO")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
