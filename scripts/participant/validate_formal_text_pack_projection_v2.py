#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.episode.contract_v2 import (
    EPISODE_IDS,
    formal_episode_paths,
)
from marketlens.information.binding import (
    CanonicalEpisodeBinding,
)
from marketlens.information.projection import (
    ParticipantBackgroundProjection,
    strip_inherited_post_type_prefix,
)
from marketlens.information.text_pack import (
    FrozenTextPack,
    source_text_sha256,
)
from marketlens.market.runtime.news import load_daily_news
from util.ForumDB import get_all_users_posts_db


TEXT_PACK_PATH = (
    REPO_ROOT
    / "data/marketlens/information/"
    / "participant_text_pack_v2.formal.json"
)

NEWS_PICKLE = (
    REPO_ROOT
    / "data/sorted_impact_news.pkl"
)

EXPECTED_PACK_ID = (
    "marketlens-participant-text-pack-v2"
)

EXPECTED_VERSION = "2.0"

EXPECTED_MANIFEST_SHA256 = (
    "d3b1042876b94dc20577d2e685d9896d"
    "56c7be70f14ffc784ba91e55f0518189"
)

FORUM_ALLOWED_KEYS = {
    "post_id",
    "author_id",
    "source_label",
    "display_text",
    "created_at",
}

TOP_LEVEL_KEYS = {
    "current_date",
    "natural_news",
    "forum_posts",
}

CJK = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff]"
)


def load_text_pack() -> FrozenTextPack:
    payload = json.loads(
        TEXT_PACK_PATH.read_text(
            encoding="utf-8"
        )
    )

    assert payload["pack_id"] == EXPECTED_PACK_ID
    assert payload["version"] == EXPECTED_VERSION
    assert payload["status"] == "formal_frozen"

    assert (
        payload["expected_manifest_sha256"]
        == EXPECTED_MANIFEST_SHA256
    )

    translations = payload["translations"]

    assert isinstance(translations, dict)
    assert len(translations) == 681

    pack = FrozenTextPack(
        pack_id=payload["pack_id"],
        version=payload["version"],
        status=payload["status"],
        translations=translations,
        expected_manifest_sha256=(
            payload["expected_manifest_sha256"]
        ),
    )

    pack.validate(formal=True)

    assert (
        pack.manifest_sha256()
        == EXPECTED_MANIFEST_SHA256
    )

    return pack


def load_manifest(
    episode_id: str,
) -> tuple[dict, dict[str, str]]:
    paths = formal_episode_paths(episode_id)

    manifest_path = (
        REPO_ROOT / paths["episode_manifest"]
    )

    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    assert manifest["episode_id"] == episode_id
    assert manifest["status"] == "formal_frozen"

    outputs = manifest["outputs"]

    for key in (
        "agent_world_db",
        "forum_db",
    ):
        assert outputs[key]["path"] == paths[key]

        sha = outputs[key]["sha256"]

        assert isinstance(sha, str)
        assert re.fullmatch(
            r"[0-9a-f]{64}",
            sha,
        )

    return manifest, paths


def episode_dates(
    manifest: dict,
) -> list[str]:
    chain = manifest["daily_state_chain"]

    assert isinstance(chain, list)
    assert len(chain) == 27

    dates = []

    for row in chain:
        current_date = row["agent_world_date"]

        assert isinstance(current_date, str)
        assert current_date

        dates.append(current_date)

    assert len(dates) == 27
    assert len(set(dates)) == 27

    return dates


def build_binding(
    episode_id: str,
    manifest: dict,
    paths: dict[str, str],
) -> CanonicalEpisodeBinding:
    outputs = manifest["outputs"]

    binding = CanonicalEpisodeBinding(
        episode_id=episode_id,
        user_db_path=(
            REPO_ROOT
            / paths["agent_world_db"]
        ),
        forum_db_path=(
            REPO_ROOT
            / paths["forum_db"]
        ),
        status="formal_frozen",
        user_db_sha256=(
            outputs[
                "agent_world_db"
            ]["sha256"]
        ),
        forum_db_sha256=(
            outputs[
                "forum_db"
            ]["sha256"]
        ),
    )

    binding.validate(formal=True)

    return binding


def collect_visible_source_hashes(
    *,
    forum_db: Path,
    dates: list[str],
) -> tuple[
    set[str],
    Counter,
]:
    seen: set[str] = set()
    kinds = Counter()

    seen_news: set[str] = set()
    seen_forum: set[str] = set()

    for current_date in dates:
        news_items = load_daily_news(
            NEWS_PICKLE,
            current_date=current_date,
        )

        for source in news_items:
            digest = source_text_sha256(source)

            seen.add(digest)
            seen_news.add(digest)

        cutoff = pd.Timestamp(
            f"{current_date} 23:59:59"
        )

        grouped = get_all_users_posts_db(
            end_date=cutoff,
            db_path=str(
                forum_db.resolve()
            ),
        )

        assert isinstance(grouped, dict)

        for posts in grouped.values():
            for post in posts:
                created_at = post["created_at"]

                if created_at[:10] > current_date:
                    raise AssertionError(
                        "future forum post returned"
                    )

                if post.get("type") == "repost":
                    raise AssertionError(
                        "participant-visible repost "
                        "returned"
                    )

                source = (
                    strip_inherited_post_type_prefix(
                        post["content"]
                    )
                )

                digest = source_text_sha256(source)

                seen.add(digest)
                seen_forum.add(digest)

    kinds["natural_news"] = len(
        seen_news
    )
    kinds["forum_post"] = len(
        seen_forum
    )

    return seen, kinds


def validate_projected_payload(
    projected: dict,
    *,
    expected_date: str,
) -> None:
    assert set(projected) == TOP_LEVEL_KEYS

    assert (
        projected["current_date"]
        == expected_date
    )

    news = projected["natural_news"]
    posts = projected["forum_posts"]

    assert isinstance(news, list)
    assert isinstance(posts, list)

    for text in news:
        assert isinstance(text, str)
        assert text.strip()

        if CJK.search(text):
            raise AssertionError(
                "participant natural-news "
                "display contains CJK"
            )

    previous_key = None

    for post in posts:
        assert isinstance(post, dict)
        assert set(post) == FORUM_ALLOWED_KEYS

        assert isinstance(
            post["post_id"],
            int,
        )

        assert isinstance(
            post["author_id"],
            str,
        )

        assert isinstance(
            post["source_label"],
            str,
        )
        assert post["source_label"].strip()

        assert isinstance(
            post["display_text"],
            str,
        )
        assert post["display_text"].strip()

        assert isinstance(
            post["created_at"],
            str,
        )

        ts = pd.Timestamp(
            post["created_at"]
        )

        assert (
            ts.date().isoformat()
            <= expected_date
        )

        current_key = (
            ts,
            post["post_id"],
        )

        if previous_key is not None:
            assert (
                current_key <= previous_key
            )

        previous_key = current_key


def main() -> int:
    print("=" * 72)
    print(
        "MARKETLENS F4C — FORMAL TEXT PACK "
        "PROJECTION VALIDATION"
    )
    print(
        "ZERO LLM / READ ONLY / "
        "NO DB WRITES"
    )
    print("=" * 72)

    pack = load_text_pack()

    pack_hashes = set(
        pack.translations
    )

    assert len(pack_hashes) == 681

    all_visible_hashes: set[str] = set()

    total_projection_calls = 0
    total_news_items = 0
    total_forum_items = 0

    for episode_id in EPISODE_IDS:
        print()
        print(
            f"=== {episode_id} ==="
        )

        manifest, paths = load_manifest(
            episode_id
        )

        dates = episode_dates(
            manifest
        )

        binding = build_binding(
            episode_id,
            manifest,
            paths,
        )

        projection = (
            ParticipantBackgroundProjection(
                episode=binding,
                text_pack=pack,
                news_pickle=NEWS_PICKLE,
                formal=True,
            )
        )

        # Explicit formal binding validation.
        projection.validate_binding()

        episode_visible, kinds = (
            collect_visible_source_hashes(
                forum_db=(
                    REPO_ROOT
                    / paths["forum_db"]
                ),
                dates=dates,
            )
        )

        missing_from_pack = (
            episode_visible
            - pack_hashes
        )

        assert not missing_from_pack, (
            f"{episode_id}: "
            "participant-visible source "
            "missing from formal pack"
        )

        all_visible_hashes.update(
            episode_visible
        )

        for current_date in dates:
            projected = projection.project(
                current_date=current_date
            )

            validate_projected_payload(
                projected,
                expected_date=current_date,
            )

            total_projection_calls += 1
            total_news_items += len(
                projected[
                    "natural_news"
                ]
            )
            total_forum_items += len(
                projected[
                    "forum_posts"
                ]
            )

        print(
            "dates_projected:",
            len(dates),
        )
        print(
            "visible_unique_sources:",
            len(episode_visible),
        )
        print(
            "visible_unique_news:",
            kinds["natural_news"],
        )
        print(
            "visible_unique_forum:",
            kinds["forum_post"],
        )
        print(
            "missing_pack_mappings:",
            len(missing_from_pack),
        )
        print(
            "PASS: formal episode binding"
        )
        print(
            "PASS: all 27 canonical dates"
        )
        print(
            "PASS: participant-safe "
            "projection allow-list"
        )

    missing_global = (
        all_visible_hashes
        - pack_hashes
    )

    unused_pack = (
        pack_hashes
        - all_visible_hashes
    )

    assert not missing_global

    # F2 established that the 681-record
    # inventory is exactly the participant-visible
    # source universe. Therefore every frozen
    # mapping must be exercised by the formal
    # canonical pool.
    assert not unused_pack, (
        "formal pack contains mappings not "
        "exercised by canonical pool: "
        f"{len(unused_pack)}"
    )

    assert len(all_visible_hashes) == 681

    print()
    print(
        "=== GLOBAL FORMAL POOL RESULT ==="
    )
    print(
        "episodes:",
        len(EPISODE_IDS),
    )
    print(
        "projection_calls:",
        total_projection_calls,
    )
    print(
        "unique_visible_source_hashes:",
        len(all_visible_hashes),
    )
    print(
        "formal_pack_mappings:",
        len(pack_hashes),
    )
    print(
        "missing_pack_mappings:",
        len(missing_global),
    )
    print(
        "unused_pack_mappings:",
        len(unused_pack),
    )
    print(
        "projected_news_occurrences:",
        total_news_items,
    )
    print(
        "projected_forum_occurrences:",
        total_forum_items,
    )
    print(
        "manifest_sha256:",
        pack.manifest_sha256(),
    )

    print()
    print(
        "PASS: E01/E02/E03 formal "
        "binding hashes"
    )
    print(
        "PASS: 81 canonical-date "
        "formal projections"
    )
    print(
        "PASS: 681/681 mappings "
        "exercised"
    )
    print(
        "PASS: zero missing mappings"
    )
    print(
        "PASS: zero unused mappings"
    )
    print(
        "PASS: no future forum leakage"
    )
    print(
        "PASS: no repost leakage"
    )
    print(
        "PASS: participant-safe "
        "forum allow-list"
    )
    print(
        "PASS: frozen text-pack hash "
        "validated on every projection"
    )

    print()
    print(
        "F4C_FORMAL_PROJECTION_VALIDATION_PASS"
    )
    print(
        "ZERO LLM"
    )
    print(
        "NO DB WRITES"
    )
    print(
        "COMMITTED: NO"
    )
    print(
        "PUSHED: NO"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
