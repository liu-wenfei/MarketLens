from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from marketlens.human.services.background_service import ParticipantBackgroundUnavailableError
from marketlens.information import (
    CanonicalEpisodeBinding,
    CanonicalEpisodeBindingError,
    FrozenTextPack,
    FrozenTextPackError,
    ParticipantBackgroundProjection,
    ParticipantInformationProjectionError,
    source_text_sha256,
    strip_inherited_post_type_prefix,
)
from marketlens.main import create_app
from marketlens.persistence.schema import sessions


def _touch_sources(tmp_path: Path) -> tuple[Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    user_db = tmp_path / "canonical-user.db"
    forum_db = tmp_path / "canonical-forum.db"
    news = tmp_path / "news.pkl"
    user_db.write_bytes(b"user-db-fixture")
    forum_db.write_bytes(b"forum-db-fixture")
    news.write_bytes(b"news-fixture")
    return user_db, forum_db, news


def _pack(*source_to_display: tuple[str, str], status: str = "development") -> FrozenTextPack:
    translations = {source_text_sha256(source): display for source, display in source_to_display}
    base = FrozenTextPack(
        pack_id="phase13b-test-pack",
        version="0-test",
        status=status,
        translations=translations,
    )
    if status == "formal_frozen":
        return FrozenTextPack(
            pack_id=base.pack_id,
            version=base.version,
            status=base.status,
            translations=translations,
            expected_manifest_sha256=base.manifest_sha256(),
        )
    return base


def _projection(tmp_path: Path, *, current_posts=None, formal: bool = False, pack=None):
    user_db, forum_db, news = _touch_sources(tmp_path)
    binding = CanonicalEpisodeBinding(
        episode_id="dev-episode",
        user_db_path=user_db,
        forum_db_path=forum_db,
        status="development",
    )
    posts = current_posts or {
        "A1": [
            {
                "id": 11,
                "user_id": "A1",
                "content": "type2：原始论坛正文",
                "score": 99,
                "belief": "internal-belief",
                "type": "type2",
                "created_at": "2023-06-19 00:00:00",
            },
            {
                "id": 7,
                "user_id": "A1",
                "content": "type3 旧论坛正文",
                "score": -2,
                "belief": "internal-belief-2",
                "type": "type3",
                "created_at": "2023-06-15 00:00:00",
            },
        ]
    }
    text_pack = pack or _pack(
        ("当日自然新闻", "Current natural news"),
        ("原始论坛正文", "Original forum body"),
        ("旧论坛正文", "Earlier forum body"),
    )

    def forum_reader(*, end_date, db_path):
        assert str(end_date) == "2023-06-19 23:59:59"
        assert db_path == str(forum_db.resolve())
        return posts

    def source_cue_resolver(user_id, *, db_path, created_at):
        assert db_path == str(user_db.resolve())
        assert created_at in {"2023-06-15 00:00:00", "2023-06-19 00:00:00"}
        return {"user_id": user_id, "user_type": "普通股民", "source_label": "Individual Investor"}

    def news_loader(path, *, current_date):
        assert Path(path) == news.resolve()
        assert current_date == "2023-06-19"
        return ["当日自然新闻"]

    return ParticipantBackgroundProjection(
        episode=binding,
        text_pack=text_pack,
        news_pickle=news,
        formal=formal,
        forum_reader=forum_reader,
        source_cue_resolver=source_cue_resolver,
        news_loader=news_loader,
    )


def test_internal_type_marker_is_removed_without_rewriting_body():
    assert strip_inherited_post_type_prefix("type2：正文") == "正文"
    assert strip_inherited_post_type_prefix(" type3: body") == "body"
    assert strip_inherited_post_type_prefix("type1 body") == "body"
    assert strip_inherited_post_type_prefix("type2｜正文") == "正文"
    assert strip_inherited_post_type_prefix("type3，正文") == "正文"
    assert strip_inherited_post_type_prefix("ordinary body") == "ordinary body"
    assert strip_inherited_post_type_prefix("正文中提到type2但不是前缀") == "正文中提到type2但不是前缀"


def test_projection_exposes_allowlisted_background_only(tmp_path):
    projected = _projection(tmp_path).project(current_date="2023-06-19")
    assert projected["current_date"] == "2023-06-19"
    assert projected["natural_news"] == ["Current natural news"]
    assert projected["forum_posts"] == [
        {
            "post_id": 11,
            "author_id": "A1",
            "source_label": "Individual Investor",
            "display_text": "Original forum body",
            "created_at": "2023-06-19 00:00:00",
        },
        {
            "post_id": 7,
            "author_id": "A1",
            "source_label": "Individual Investor",
            "display_text": "Earlier forum body",
            "created_at": "2023-06-15 00:00:00",
        },
    ]
    forbidden = {
        "belief", "type", "score", "user_type", "sys_prompt", "prompt",
        "is_top_user", "degree", "future_correction", "controlled_stimulus",
    }
    for post in projected["forum_posts"]:
        assert forbidden.isdisjoint(post)


def test_forum_feed_is_cumulative_and_globally_recent_first(tmp_path):
    projected = _projection(tmp_path).project(current_date="2023-06-19")
    assert [post["post_id"] for post in projected["forum_posts"]] == [11, 7]


def test_future_forum_post_fails_closed_even_if_reader_misbehaves(tmp_path):
    future_posts = {
        "A1": [{
            "id": 12,
            "user_id": "A1",
            "content": "type2：未来正文",
            "score": 0,
            "belief": "x",
            "type": "type2",
            "created_at": "2023-06-20 00:00:00",
        }]
    }
    projection = _projection(
        tmp_path,
        current_posts=future_posts,
        pack=_pack(("当日自然新闻", "Current natural news"), ("未来正文", "Future body")),
    )
    with pytest.raises(ParticipantInformationProjectionError, match="future post"):
        projection.project(current_date="2023-06-19")


def test_missing_frozen_translation_fails_closed_instead_of_live_translation(tmp_path):
    projection = _projection(
        tmp_path,
        pack=_pack(("当日自然新闻", "Current natural news")),
    )
    with pytest.raises(ParticipantInformationProjectionError, match="live translation is forbidden"):
        projection.project(current_date="2023-06-19")


def test_formal_episode_binding_requires_hash_pinned_formal_assets(tmp_path):
    user_db, forum_db, _ = _touch_sources(tmp_path)
    binding = CanonicalEpisodeBinding(
        episode_id="not-formal",
        user_db_path=user_db,
        forum_db_path=forum_db,
    )
    with pytest.raises(CanonicalEpisodeBindingError, match="status"):
        binding.validate(formal=True)

    formal = CanonicalEpisodeBinding(
        episode_id="formal-episode",
        user_db_path=user_db,
        forum_db_path=forum_db,
        status="formal_frozen",
        user_db_sha256=sha256(user_db.read_bytes()).hexdigest(),
        forum_db_sha256=sha256(forum_db.read_bytes()).hexdigest(),
    )
    formal.validate(formal=True)


def test_formal_text_pack_requires_exact_manifest_hash():
    dev = _pack(("源文本", "Frozen English"))
    with pytest.raises(FrozenTextPackError, match="status"):
        dev.validate(formal=True)

    formal = _pack(("源文本", "Frozen English"), status="formal_frozen")
    formal.validate(formal=True)
    tampered = FrozenTextPack(
        pack_id=formal.pack_id,
        version=formal.version,
        status=formal.status,
        translations={source_text_sha256("源文本"): "Changed English"},
        expected_manifest_sha256=formal.expected_manifest_sha256,
    )
    with pytest.raises(FrozenTextPackError, match="hash mismatch"):
        tampered.validate(formal=True)


def test_default_human_api_does_not_bind_legacy_or_sample_forum(tmp_path):
    with TestClient(create_app(tmp_path / "human.db")) as client:
        session = client.post(
            "/session", json={"participant_id": "P13B", "request_id": "s-1"}
        ).json()
        with client.app.state.db.connect() as connection:
            connection.execute(
                update(sessions)
                .where(sessions.c.session_id == session["session_id"])
                .values(current_date="2023-06-19")
            )
        response = client.get(f"/session/{session['session_id']}/background")
        assert response.status_code == 409
        assert "not bound" in response.json()["detail"]


def test_background_endpoint_uses_session_authorised_date_and_safe_projection(tmp_path):
    projection = _projection(tmp_path / "projection")
    with TestClient(
        create_app(tmp_path / "human.db", background_projection=projection)
    ) as client:
        session = client.post(
            "/session", json={"participant_id": "P13B", "request_id": "s-2"}
        ).json()
        with client.app.state.db.connect() as connection:
            connection.execute(
                update(sessions)
                .where(sessions.c.session_id == session["session_id"])
                .values(current_date="2023-06-19")
            )
        response = client.get(f"/session/{session['session_id']}/background")
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"session_id", "current_date", "natural_news", "forum_posts"}
        assert body["current_date"] == "2023-06-19"
        assert "controlled_stimuli" not in body
        assert "source_descriptor" not in body


def test_projection_source_declares_frozen_reuse_and_excludes_legacy_rumor_logic():
    source = Path("marketlens/information/projection.py").read_text(encoding="utf-8")
    assert "load_daily_news" in source
    assert "util.ForumDB" in source
    assert "get_all_users_posts_db" in source
    assert "resolve_agent_source_cue" in source
    assert "RumorInjector" not in source
    assert "translate_texts" not in source
    assert "get_reposts_for_posts_db" not in source
