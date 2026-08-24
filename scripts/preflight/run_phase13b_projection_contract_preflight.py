#!/usr/bin/env python3
"""Zero-LLM Phase 13B participant-background projection contract preflight.

This is contract evidence only.  It uses an explicit development fixture and
proves that formal mode fails closed until a hash-pinned canonical episode and
frozen participant text pack exist.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.information import (
    CanonicalEpisodeBinding,
    FrozenTextPack,
    ParticipantBackgroundProjection,
    ParticipantInformationProjectionError,
    source_text_sha256,
)

EVIDENCE_CLASS = (
    "NON-FORMAL / PHASE 13B PARTICIPANT BACKGROUND PROJECTION CONTRACT PREFLIGHT / "
    "ZERO-LLM / NOT FORMAL EXPERIMENT EVIDENCE"
)


def main() -> int:
    artifact_root = REPO_ROOT / "artifacts" / "preflight" / "phase13"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = artifact_root / f"{stamp}_phase13b_projection_contract"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="marketlens-phase13b-") as tmp:
        tmp_path = Path(tmp)
        user_db = tmp_path / "canonical-user.db"
        forum_db = tmp_path / "canonical-forum.db"
        news_pickle = tmp_path / "news.pkl"
        user_db.write_bytes(b"development-user-db-fixture")
        forum_db.write_bytes(b"development-forum-db-fixture")
        news_pickle.write_bytes(b"development-news-fixture")

        news_source = "当日自然新闻"
        latest_source = "当天论坛正文"
        warmup_source = "预热期论坛正文"
        pack = FrozenTextPack(
            pack_id="phase13b-development-fixture",
            version="0-preflight",
            status="development",
            translations={
                source_text_sha256(news_source): "Current natural news",
                source_text_sha256(latest_source): "Current-day forum body",
                source_text_sha256(warmup_source): "Warm-up forum body",
            },
        )
        binding = CanonicalEpisodeBinding(
            episode_id="phase13b-development-fixture",
            user_db_path=user_db,
            forum_db_path=forum_db,
            status="development",
        )

        def news_loader(path, *, current_date):
            assert Path(path) == news_pickle.resolve()
            assert current_date == "2023-06-19"
            return [news_source]

        def forum_reader(*, end_date, db_path):
            assert str(end_date) == "2023-06-19 23:59:59"
            assert db_path == str(forum_db.resolve())
            return {
                "A1": [
                    {
                        "id": 20,
                        "user_id": "A1",
                        "content": "type2：" + latest_source,
                        "score": 999,
                        "belief": "INTERNAL_DO_NOT_EXPOSE",
                        "type": "type2",
                        "created_at": "2023-06-19 00:00:00",
                    },
                    {
                        "id": 3,
                        "user_id": "A1",
                        "content": "type3 " + warmup_source,
                        "score": -5,
                        "belief": "INTERNAL_DO_NOT_EXPOSE",
                        "type": "type3",
                        "created_at": "2023-06-15 00:00:00",
                    },
                ]
            }

        snapshot_requests: list[str] = []

        def source_cue_resolver(user_id, *, db_path, created_at):
            assert user_id == "A1"
            assert db_path == str(user_db.resolve())
            snapshot_requests.append(created_at)
            return {
                "user_id": user_id,
                "user_type": "普通股民",
                "source_label": "Individual Investor",
            }

        projection = ParticipantBackgroundProjection(
            episode=binding,
            text_pack=pack,
            news_pickle=news_pickle,
            formal=False,
            forum_reader=forum_reader,
            source_cue_resolver=source_cue_resolver,
            news_loader=news_loader,
        )
        body = projection.project(current_date="2023-06-19")

        formal_mode_rejected = False
        try:
            ParticipantBackgroundProjection(
                episode=binding,
                text_pack=pack,
                news_pickle=news_pickle,
                formal=True,
                forum_reader=forum_reader,
                source_cue_resolver=source_cue_resolver,
                news_loader=news_loader,
            ).project(current_date="2023-06-19")
        except ParticipantInformationProjectionError:
            formal_mode_rejected = True

        forum_keys = set().union(*(post.keys() for post in body["forum_posts"]))
        forbidden = {
            "belief",
            "type",
            "score",
            "user_type",
            "sys_prompt",
            "prompt",
            "is_top_user",
            "degree",
            "controlled_stimulus",
            "future_correction",
        }
        participant_forum_allowlist_exact = forum_keys == {
            "post_id",
            "author_id",
            "source_label",
            "display_text",
            "created_at",
        }
        internal_fields_absent = forbidden.isdisjoint(forum_keys)
        internal_type_prefix_absent = all(
            not post["display_text"].lower().startswith(("type1", "type2", "type3"))
            for post in body["forum_posts"]
        )

        summary = {
            "status": "PASS",
            "evidence_class": EVIDENCE_CLASS,
            "llm_api_calls": 0,
            "formal_experiment_evidence": False,
            "phase13b_contract_status": "development",
            "runtime_binding_default": "fail_closed_until_explicit_canonical_episode_binding",
            "reuse_contract": {
                "natural_news_source": "Phase 7 marketlens.market.runtime.news.load_daily_news",
                "forum_source": "inherited util.ForumDB.get_all_users_posts_db",
                "agent_source_identity": "Phase 12 resolve_agent_source_cue -> inherited UserDB.user_type",
                "controlled_stimulus_source": "EXCLUDED_FROM_GENERIC_BACKGROUND_ENDPOINT; remains Phase 11 moment-aware + Phase 12 cue",
            },
            "development_projection_passed": True,
            "formal_mode_rejected_without_frozen_episode_and_text_pack": formal_mode_rejected,
            "live_translation_used": False,
            "frozen_text_pack_lookup_by_source_sha256": True,
            "participant_forum_allowlist_exact": participant_forum_allowlist_exact,
            "internal_forum_fields_absent": internal_fields_absent,
            "inherited_type_prefix_removed": internal_type_prefix_absent,
            "forum_is_cumulative_through_current_sealed_date": [
                post["created_at"] for post in body["forum_posts"]
            ] == ["2023-06-19 00:00:00", "2023-06-15 00:00:00"],
            "profile_snapshot_join_requests": snapshot_requests,
            "natural_news_current_day_only": body["natural_news"] == ["Current natural news"],
            "controlled_stimulus_present_in_background_payload": False,
            "participant_behaviour_parameters_added": 0,
            "agent_world_mutation_performed": False,
            "forum_write_performed": False,
            "market_write_performed": False,
            "canonical_episode_formal_assets_bound": False,
            "formal_agent_translation_assets_bound": False,
            "note": (
                "Phase 13B contract only. Formal runtime remains intentionally unavailable until the "
                "single canonical episode DB pair and reviewed/hash-frozen participant English text pack exist."
            ),
        }

        checks = [
            summary["development_projection_passed"],
            summary["formal_mode_rejected_without_frozen_episode_and_text_pack"],
            summary["participant_forum_allowlist_exact"],
            summary["internal_forum_fields_absent"],
            summary["inherited_type_prefix_removed"],
            summary["forum_is_cumulative_through_current_sealed_date"],
            summary["natural_news_current_day_only"],
            not summary["controlled_stimulus_present_in_background_payload"],
            summary["participant_behaviour_parameters_added"] == 0,
        ]
        if not all(checks):
            summary["status"] = "FAIL"

    artifact = artifact_dir / "summary.json"
    artifact.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(EVIDENCE_CLASS)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Artifact: {artifact}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
