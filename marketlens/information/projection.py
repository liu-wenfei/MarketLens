"""Participant-safe projection of canonical TwinMarket background information.

This module is intentionally read-only.  It reuses:
- Phase 7 ``load_daily_news`` for current-day inherited natural news;
- inherited ``util.ForumDB.get_all_users_posts_db`` for cumulative forum history;
- Phase 12 ``resolve_agent_source_cue`` for stable author source status.

Controlled misinformation/correction is *not* projected here because its same-day
visibility is moment-aware and remains owned by Phase 11 + Phase 12.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable, Mapping, Any

import pandas as pd

from marketlens.information.binding import CanonicalEpisodeBinding
from marketlens.information.text_pack import FrozenTextPack
from marketlens.source_cues.adapter import resolve_agent_source_cue


class ParticipantInformationProjectionError(ValueError):
    """Raised when participant-safe background information cannot be proven safe."""


_INTERNAL_POST_PREFIX = re.compile(r"^\s*type[123](?:\s*[:：|｜,，]\s*|\s+)", re.IGNORECASE)
_FORUM_PARTICIPANT_KEYS = frozenset(
    {"post_id", "author_id", "source_label", "display_text", "created_at"}
)


def strip_inherited_post_type_prefix(content: str) -> str:
    """Remove only the inherited leading type1/type2/type3 marker.

    The remainder is not summarised, translated, sentiment-edited, or otherwise
    rewritten here.  Translation is supplied only through ``FrozenTextPack``.
    """
    if not isinstance(content, str) or not content.strip():
        raise ParticipantInformationProjectionError("forum post content must be non-empty text")
    cleaned = _INTERNAL_POST_PREFIX.sub("", content, count=1)
    if not cleaned.strip():
        raise ParticipantInformationProjectionError(
            "forum post became empty after removing inherited internal type marker"
        )
    return cleaned


def _default_news_loader(news_pickle: str | Path, *, current_date: str) -> list[Any]:
    # Lazy import preserves direct Phase 7 reuse without importing unrelated
    # Agent/matching runtime dependencies when a projection fixture is injected.
    from marketlens.market.runtime.news import load_daily_news

    return load_daily_news(news_pickle, current_date=current_date)


def _default_forum_reader(*, end_date: pd.Timestamp, db_path: str) -> Mapping[str, list[dict]]:
    from util.ForumDB import get_all_users_posts_db

    return get_all_users_posts_db(end_date=end_date, db_path=db_path)


def _default_source_cue_resolver(user_id: str, *, db_path: str, created_at: str) -> dict[str, str]:
    return resolve_agent_source_cue(user_id, db_path=db_path, created_at=created_at)


def _parse_post_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ParticipantInformationProjectionError("forum post created_at must be a string timestamp")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ParticipantInformationProjectionError(
            f"invalid inherited forum post created_at: {value!r}"
        ) from exc


def _profile_snapshot_timestamp(post_timestamp: datetime) -> str:
    # TwinMarket Profiles are daily snapshots at simulated-day midnight.
    return f"{post_timestamp.date().isoformat()} 00:00:00"


class ParticipantBackgroundProjection:
    def __init__(
        self,
        *,
        episode: CanonicalEpisodeBinding,
        text_pack: FrozenTextPack,
        news_pickle: str | Path = "data/sorted_impact_news.pkl",
        formal: bool = False,
        forum_reader: Callable[..., Mapping[str, list[dict]]] | None = None,
        source_cue_resolver: Callable[..., dict[str, str]] | None = None,
        news_loader: Callable[..., list[Any]] | None = None,
    ):
        self.episode = episode
        self.text_pack = text_pack
        self.news_pickle = Path(news_pickle).expanduser().resolve()
        self.formal = bool(formal)
        self.forum_reader = forum_reader or _default_forum_reader
        self.source_cue_resolver = source_cue_resolver or _default_source_cue_resolver
        self.news_loader = news_loader or _default_news_loader

    def validate_binding(self) -> None:
        try:
            self.episode.validate(formal=self.formal)
            self.text_pack.validate(formal=self.formal)
        except ValueError as exc:
            raise ParticipantInformationProjectionError(str(exc)) from exc
        if not self.news_pickle.is_file():
            raise ParticipantInformationProjectionError(
                f"protected TwinMarket natural-news source not found: {self.news_pickle}"
            )

    def project(self, *, current_date: str) -> dict[str, object]:
        try:
            return self._project(current_date=current_date)
        except ParticipantInformationProjectionError:
            raise
        except (ValueError, FileNotFoundError) as exc:
            raise ParticipantInformationProjectionError(str(exc)) from exc

    def _project(self, *, current_date: str) -> dict[str, object]:
        self.validate_binding()
        try:
            current = date.fromisoformat(current_date)
        except (TypeError, ValueError) as exc:
            raise ParticipantInformationProjectionError(
                f"current_date must be YYYY-MM-DD: {current_date!r}"
            ) from exc

        natural_news_source = self.news_loader(self.news_pickle, current_date=current.isoformat())
        natural_news: list[str] = []
        for item in natural_news_source:
            if not isinstance(item, str) or not item.strip():
                raise ParticipantInformationProjectionError(
                    "participant natural-news projection only accepts non-empty inherited text items"
                )
            natural_news.append(self.text_pack.display_text(item, formal=self.formal))

        cutoff = pd.Timestamp(f"{current.isoformat()} 23:59:59")
        grouped = self.forum_reader(
            end_date=cutoff,
            db_path=str(self.episode.resolved_forum_db_path),
        )
        if not isinstance(grouped, Mapping):
            raise ParticipantInformationProjectionError(
                "inherited forum reader must return the TwinMarket user->posts mapping"
            )
        flat_posts: list[dict] = []
        for posts in grouped.values():
            flat_posts.extend(posts)

        # Inherited reader groups by user. Re-sort into one participant feed without
        # changing content and keep the most recent canonical posts first.
        def sort_key(post: Mapping[str, Any]) -> tuple[datetime, int]:
            ts = _parse_post_timestamp(post.get("created_at"))
            try:
                post_id = int(post.get("id"))
            except (TypeError, ValueError) as exc:
                raise ParticipantInformationProjectionError("forum post id must be an integer") from exc
            return ts, post_id

        flat_posts.sort(key=sort_key, reverse=True)
        forum_posts: list[dict[str, object]] = []
        for post in flat_posts:
            ts = _parse_post_timestamp(post.get("created_at"))
            if ts.date() > current:
                raise ParticipantInformationProjectionError(
                    "inherited forum reader returned a future post beyond the sealed participant date"
                )
            if post.get("type") == "repost":
                raise ParticipantInformationProjectionError(
                    "inherited forum reader unexpectedly exposed a repost in participant projection"
                )

            try:
                post_id = int(post["id"])
                user_id = str(post["user_id"])
                raw_content = post["content"]
            except KeyError as exc:
                raise ParticipantInformationProjectionError(
                    f"inherited forum post missing required field {exc.args[0]!r}"
                ) from exc

            source_text = strip_inherited_post_type_prefix(raw_content)
            cue = self.source_cue_resolver(
                user_id,
                db_path=str(self.episode.resolved_user_db_path),
                created_at=_profile_snapshot_timestamp(ts),
            )
            source_label = cue.get("source_label")
            if not isinstance(source_label, str) or not source_label:
                raise ParticipantInformationProjectionError("Phase 12 source cue has no usable source_label")

            projected = {
                "post_id": post_id,
                "author_id": user_id,
                "source_label": source_label,
                "display_text": self.text_pack.display_text(source_text, formal=self.formal),
                "created_at": ts.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if set(projected) != _FORUM_PARTICIPANT_KEYS:
                raise ParticipantInformationProjectionError(
                    "participant forum allow-list projection invariant failed"
                )
            forum_posts.append(projected)

        return {
            "current_date": current.isoformat(),
            "natural_news": natural_news,
            "forum_posts": forum_posts,
        }
