"""Deterministic MarketLens v2 forum-language validation.

This module performs zero-LLM format validation only. It does not translate,
rewrite, score sentiment, or judge the substantive quality of an Agent post.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

_CJK_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"
)
_LATIN_RE = re.compile(r"[A-Za-z]")
_TYPE_PREFIX_RE = re.compile(r"^\s*type[123]\s*:\s*", re.IGNORECASE)


def english_forum_post_violations(text: str) -> tuple[str, ...]:
    """Return deterministic language-format violations for one post."""
    value = str(text or "")
    violations: list[str] = []
    if not value.strip():
        violations.append("empty_post")
    if _CJK_RE.search(value):
        violations.append("contains_cjk_character")
    if not _LATIN_RE.search(value):
        violations.append("missing_latin_letter")
    if _TYPE_PREFIX_RE.search(value):
        violations.append("type_prefix_in_post")
    return tuple(violations)


def validate_english_forum_post(text: str) -> dict[str, Any]:
    violations = english_forum_post_violations(text)
    return {
        "complete": not violations,
        "violations": list(violations),
        "contains_cjk": "contains_cjk_character" in violations,
        "contains_latin_letter": "missing_latin_letter" not in violations,
        "type_prefix_in_post": "type_prefix_in_post" in violations,
    }


def validate_forum_db_english_posts(forum_db: str | Path) -> dict[str, Any]:
    """Validate every stored forum post without altering the database."""
    db = Path(forum_db).resolve()
    checked = 0
    invalid: list[dict[str, Any]] = []
    with sqlite3.connect(str(db)) as conn:
        rows = conn.execute(
            "SELECT id, user_id, content, created_at FROM posts ORDER BY id"
        ).fetchall()
    for post_id, user_id, content, created_at in rows:
        checked += 1
        violations = english_forum_post_violations(str(content or ""))
        if violations:
            invalid.append(
                {
                    "post_id": str(post_id),
                    "user_id": str(user_id),
                    "created_at": str(created_at),
                    "violations": list(violations),
                }
            )
    return {
        "complete": not invalid,
        "posts_checked": checked,
        "invalid_post_count": len(invalid),
        "invalid_posts": invalid,
        "validation_mode": "deterministic_zero_llm_no_translation",
    }
