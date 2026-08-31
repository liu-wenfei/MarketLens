#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.episode.contract_v2 import EPISODE_IDS, formal_episode_paths
from marketlens.information.text_pack import source_text_sha256
from marketlens.information.projection import strip_inherited_post_type_prefix
from marketlens.market.runtime.news import load_daily_news
from util.ForumDB import get_all_users_posts_db


NEWS_PICKLE = REPO_ROOT / "data" / "sorted_impact_news.pkl"
OUTPUT_DIR = REPO_ROOT / "data" / "marketlens" / "information"
CSV_OUTPUT = OUTPUT_DIR / "participant_source_text_inventory_v2.csv"
JSON_OUTPUT = OUTPUT_DIR / "participant_source_text_inventory_v2.json"


def load_episode_manifest(episode_id: str) -> dict:
    paths = formal_episode_paths(episode_id)
    path = REPO_ROOT / paths["episode_manifest"]
    payload = json.loads(path.read_text(encoding="utf-8"))

    if payload.get("episode_id") != episode_id:
        raise RuntimeError(
            f"episode manifest identity mismatch for {episode_id}: "
            f"{payload.get('episode_id')!r}"
        )

    if payload.get("status") != "formal_frozen":
        raise RuntimeError(
            f"episode {episode_id} is not formal_frozen"
        )

    return payload


def episode_dates(manifest: dict) -> list[str]:
    chain = manifest.get("daily_state_chain")
    if not isinstance(chain, list) or not chain:
        raise RuntimeError(
            f"{manifest.get('episode_id')} has no usable daily_state_chain"
        )

    dates: list[str] = []

    for row in chain:
        if not isinstance(row, dict):
            raise RuntimeError("daily_state_chain row must be an object")

        candidate = None
        for key in (
            "date",
            "current_date",
            "simulated_date",
            "market_date",
            "agent_world_date",
        ):
            value = row.get(key)
            if isinstance(value, str) and value:
                candidate = value
                break

        if candidate is None:
            raise RuntimeError(
                "Unable to resolve simulated date from daily_state_chain row: "
                + json.dumps(row, ensure_ascii=False, sort_keys=True)
            )

        dates.append(candidate)

    return sorted(set(dates))


def collect_inventory() -> list[dict]:
    records: dict[str, dict] = {}
    occurrences: dict[str, list[dict]] = defaultdict(list)

    for episode_id in EPISODE_IDS:
        manifest = load_episode_manifest(episode_id)
        paths = formal_episode_paths(episode_id)

        forum_db = REPO_ROOT / paths["forum_db"]

        if not forum_db.is_file():
            raise FileNotFoundError(
                f"canonical forum DB missing: {forum_db}"
            )

        dates = episode_dates(manifest)

        for current_date in dates:
            news_items = load_daily_news(
                NEWS_PICKLE,
                current_date=current_date,
            )

            for index, item in enumerate(news_items):
                if not isinstance(item, str) or not item.strip():
                    raise RuntimeError(
                        f"non-text natural news for {episode_id} "
                        f"{current_date} index={index}"
                    )

                digest = source_text_sha256(item)

                records.setdefault(
                    digest,
                    {
                        "source_text_sha256": digest,
                        "source_kind": "natural_news",
                        "source_text": item,
                    },
                )

                if records[digest]["source_text"] != item:
                    raise RuntimeError(
                        f"SHA-256 collision detected for {digest}"
                    )

                occurrences[digest].append(
                    {
                        "episode_id": episode_id,
                        "date": current_date,
                        "source_kind": "natural_news",
                    }
                )

            cutoff = pd.Timestamp(f"{current_date} 23:59:59")

            grouped = get_all_users_posts_db(
                end_date=cutoff,
                db_path=str(forum_db.resolve()),
            )

            if not isinstance(grouped, dict):
                raise RuntimeError(
                    "Inherited forum reader did not return a mapping"
                )

            for posts in grouped.values():
                for post in posts:
                    created_at = post.get("created_at")
                    if not isinstance(created_at, str):
                        raise RuntimeError(
                            "Forum post created_at must be text"
                        )

                    post_date = created_at[:10]

                    # get_all_users_posts_db is cumulative. Inventory each
                    # canonical forum source text once at its own creation date,
                    # rather than duplicating it for every later cutoff.
                    if post_date != current_date:
                        continue

                    raw_content = post.get("content")
                    if not isinstance(raw_content, str) or not raw_content.strip():
                        raise RuntimeError(
                            "Forum post content must be non-empty text"
                        )

                    source_text = strip_inherited_post_type_prefix(raw_content)
                    digest = source_text_sha256(source_text)

                    records.setdefault(
                        digest,
                        {
                            "source_text_sha256": digest,
                            "source_kind": "forum_post",
                            "source_text": source_text,
                        },
                    )

                    if records[digest]["source_text"] != source_text:
                        raise RuntimeError(
                            f"SHA-256 collision detected for {digest}"
                        )

                    occurrences[digest].append(
                        {
                            "episode_id": episode_id,
                            "date": current_date,
                            "source_kind": "forum_post",
                            "post_id": post.get("id"),
                            "author_id": str(post.get("user_id")),
                        }
                    )

    output: list[dict] = []

    for digest in sorted(records):
        row = dict(records[digest])
        row["occurrence_count"] = len(occurrences[digest])
        row["occurrences"] = occurrences[digest]
        output.append(row)

    return output


def write_outputs(rows: list[dict]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    JSON_OUTPUT.write_text(
        json.dumps(
            {
                "inventory_schema_version": "marketlens-participant-source-text-inventory/1.0",
                "canonical_episode_pool": "marketlens-canonical-episode-pool-v2",
                "translation_status": "NOT_TRANSLATED",
                "llm_api_calls": 0,
                "live_translation_used": False,
                "record_count": len(rows),
                "records": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with CSV_OUTPUT.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_text_sha256",
                "source_kind",
                "source_text",
                "occurrence_count",
            ],
        )
        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    "source_text_sha256": row["source_text_sha256"],
                    "source_kind": row["source_kind"],
                    "source_text": row["source_text"],
                    "occurrence_count": row["occurrence_count"],
                }
            )


def main() -> int:
    print(
        "MARKETLENS PARTICIPANT SOURCE TEXT INVENTORY V2 "
        "/ ZERO LLM / NO TRANSLATION"
    )

    rows = collect_inventory()
    write_outputs(rows)

    kinds: dict[str, int] = defaultdict(int)
    for row in rows:
        kinds[row["source_kind"]] += 1

    print(f"records={len(rows)}")
    print(f"natural_news={kinds['natural_news']}")
    print(f"forum_post={kinds['forum_post']}")
    print(f"json={JSON_OUTPUT.relative_to(REPO_ROOT)}")
    print(f"csv={CSV_OUTPUT.relative_to(REPO_ROOT)}")
    print("llm_api_calls=0")
    print("translation_performed=false")
    print("SOURCE_TEXT_INVENTORY_BUILD_PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
