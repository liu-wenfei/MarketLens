"""Deterministic schema/content validation for MarketLens feedback output.

This validator runs after a future LLM response and before persistence or
participant display. It makes no LLM/API calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from .context import FeedbackContextPack
from .prompt import ALLOWED_FEEDBACK_FOCUS


OUTPUT_CONTRACT_VERSION = (
    "marketlens-feedback-output-v1"
)


class FeedbackOutputValidationError(
    ValueError
):
    pass


_WORD_RE = re.compile(
    r"[A-Za-z0-9]+"
    r"(?:['’\-][A-Za-z0-9]+)*"
)


_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"[-+]?"
    r"(?:\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.\d+)?"
    r"(?![A-Za-z0-9_])"
)


_INTERNAL_TOKEN_PATTERNS = (
    (
        "internal judgement label",
        re.compile(
            r"\bJ[0-4]\b",
            re.IGNORECASE,
        ),
    ),
    (
        "internal identifier",
        re.compile(
            r"\b(?:episode|session|participant|"
            r"stimulus|request|event|transaction)"
            r"_id\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Agent internal state",
        re.compile(
            r"\b(?:top[_ ]?user|prominence|"
            r"agent holdings|agent trades|"
            r"agent strategy|raw type)\b",
            re.IGNORECASE,
        ),
    ),
)


_FORBIDDEN_CONTENT_PATTERNS = (
    (
        "truth/correctness language",
        re.compile(
            r"\b(?:correct|incorrect|right answer|"
            r"wrong answer|misinformation|"
            r"false information|fake information|"
            r"truth label)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "score/rank language",
        re.compile(
            r"\b(?:score|scored|grade|graded|"
            r"percentile|ranked?|ranking|"
            r"outperformed|underperformed)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "praise language",
        re.compile(
            r"\b(?:well done|good job|excellent job|"
            r"great decision|smart decision|"
            r"excellent decision)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "financial advice language",
        re.compile(
            r"\b(?:you should|you ought to|"
            r"you need to|I recommend|"
            r"we recommend|financial advice|"
            r"consider buying|consider selling|"
            r"consider holding)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "other-participant comparison",
        re.compile(
            r"\b(?:other participants?|"
            r"average participant|"
            r"compared with participants?|"
            r"compared to participants?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "future prediction",
        re.compile(
            r"\b(?:will rise|will fall|"
            r"will increase|will decrease|"
            r"future price|next period's price|"
            r"next period price)\b",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(
    frozen=True,
    slots=True,
)
class ValidatedFeedbackOutput:
    output_contract_version: str
    feedback_kind: str
    payload: Mapping[str, object]
    word_count: int
    output_sha256: str

    def to_dict(
        self,
    ) -> dict[str, object]:
        return {
            "output_contract_version": (
                self.output_contract_version
            ),
            "feedback_kind": (
                self.feedback_kind
            ),
            "payload": dict(
                self.payload
            ),
            "word_count": (
                self.word_count
            ),
            "output_sha256": (
                self.output_sha256
            ),
        }


def _reject_duplicate_keys(
    pairs: list[
        tuple[str, Any]
    ],
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for key, value in pairs:
        if key in result:
            raise FeedbackOutputValidationError(
                "duplicate JSON object key: "
                f"{key!r}"
            )

        result[key] = value

    return result


def _parse_output(
    raw: str | Mapping[
        str,
        object,
    ],
) -> dict[str, object]:
    if isinstance(
        raw,
        Mapping,
    ):
        return dict(raw)

    if not isinstance(
        raw,
        str,
    ):
        raise FeedbackOutputValidationError(
            "feedback output must be "
            "JSON text or a mapping"
        )

    stripped = raw.strip()

    if (
        stripped.startswith("```")
        or stripped.endswith("```")
    ):
        raise FeedbackOutputValidationError(
            "Markdown/code fences are forbidden"
        )

    try:
        value = json.loads(
            stripped,
            object_pairs_hook=(
                _reject_duplicate_keys
            ),
        )
    except (
        json.JSONDecodeError,
        FeedbackOutputValidationError,
    ):
        raise
    except Exception as exc:
        raise FeedbackOutputValidationError(
            "invalid feedback JSON"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise FeedbackOutputValidationError(
            "feedback JSON root must "
            "be an object"
        )

    return value


def _word_count(
    text: str,
) -> int:
    return len(
        _WORD_RE.findall(
            text
        )
    )


def _require_text(
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise FeedbackOutputValidationError(
            f"{name} must be "
            "non-empty text"
        )

    return value.strip()


def _all_output_text(
    payload: Mapping[
        str,
        object,
    ],
) -> str:
    chunks: list[str] = []

    def visit(
        value: object,
    ) -> None:
        if isinstance(
            value,
            str,
        ):
            chunks.append(
                value
            )
        elif isinstance(
            value,
            Mapping,
        ):
            for child in (
                value.values()
            ):
                visit(child)
        elif isinstance(
            value,
            (list, tuple),
        ):
            for child in value:
                visit(child)

    visit(payload)

    return "\n".join(
        chunks
    )


def _validate_content_language(
    text: str,
) -> None:
    for (
        label,
        pattern,
    ) in (
        *_INTERNAL_TOKEN_PATTERNS,
        *_FORBIDDEN_CONTENT_PATTERNS,
    ):
        if pattern.search(text):
            raise FeedbackOutputValidationError(
                f"feedback contains forbidden "
                f"{label}"
            )


def _context_numbers(
    pack: FeedbackContextPack,
) -> set[Decimal]:
    values: set[Decimal] = set()

    def visit(
        value: object,
    ) -> None:
        if isinstance(
            value,
            bool,
        ):
            return

        if isinstance(
            value,
            (int, float),
        ):
            try:
                values.add(
                    Decimal(
                        str(value)
                    ).normalize()
                )
            except InvalidOperation as exc:
                raise FeedbackOutputValidationError(
                    "context contains invalid "
                    "numeric value"
                ) from exc
            return

        if isinstance(
            value,
            Mapping,
        ):
            for child in (
                value.values()
            ):
                visit(child)
            return

        if isinstance(
            value,
            (list, tuple),
        ):
            for child in value:
                visit(child)

    visit(
        pack.to_dict()
    )

    return values


def _output_numbers(
    text: str,
) -> set[Decimal]:
    result: set[Decimal] = set()

    for raw in _NUMBER_RE.findall(
        text
    ):
        normalized = raw.replace(
            ",",
            "",
        )

        try:
            number = Decimal(
                normalized
            ).normalize()
        except InvalidOperation as exc:
            raise FeedbackOutputValidationError(
                "feedback contains invalid "
                "numeric literal"
            ) from exc

        result.add(
            number
        )

    return result


def _validate_quantitative_literals(
    *,
    text: str,
    pack: FeedbackContextPack,
) -> None:
    available = (
        _context_numbers(
            pack
        )
    )

    used = _output_numbers(
        text
    )

    invented = (
        used - available
    )

    if invented:
        raise FeedbackOutputValidationError(
            "feedback contains quantitative "
            "literal(s) not supplied by the "
            "validated context: "
            + ", ".join(
                sorted(
                    str(value)
                    for value
                    in invented
                )
            )
        )


def _canonical_sha256(
    payload: Mapping[
        str,
        object,
    ],
) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()


def validate_feedback_output(
    raw: str | Mapping[
        str,
        object,
    ],
    *,
    context_pack: FeedbackContextPack,
) -> ValidatedFeedbackOutput:
    if not isinstance(
        context_pack,
        FeedbackContextPack,
    ):
        raise FeedbackOutputValidationError(
            "output validation requires "
            "a validated FeedbackContextPack"
        )

    payload = _parse_output(
        raw
    )

    expected_kind = (
        context_pack.feedback_kind
    )

    if (
        expected_kind
        == "multi_period_decision_feedback"
    ):
        if set(payload) != {
            "feedback_kind",
            "focus",
            "message",
        }:
            raise FeedbackOutputValidationError(
                "mid-session feedback "
                "schema fields are invalid"
            )

        if (
            payload[
                "feedback_kind"
            ]
            != expected_kind
        ):
            raise FeedbackOutputValidationError(
                "feedback_kind mismatch"
            )

        focus = payload[
            "focus"
        ]

        if (
            not isinstance(
                focus,
                list,
            )
            or not focus
        ):
            raise FeedbackOutputValidationError(
                "focus must be a "
                "non-empty list"
            )

        if len(focus) != len(
            set(focus)
        ):
            raise FeedbackOutputValidationError(
                "focus values must be unique"
            )

        for item in focus:
            if (
                not isinstance(
                    item,
                    str,
                )
                or item
                not in ALLOWED_FEEDBACK_FOCUS
            ):
                raise FeedbackOutputValidationError(
                    "unsupported feedback focus"
                )

        message = _require_text(
            "message",
            payload["message"],
        )

        words = _word_count(
            message
        )

        if not (
            110 <= words <= 170
        ):
            raise FeedbackOutputValidationError(
                "mid-session feedback must "
                "contain 110-170 English words"
            )

        prose = message

    elif (
        expected_kind
        == "final_session_summary"
    ):
        if set(payload) != {
            "feedback_kind",
            "sections",
        }:
            raise FeedbackOutputValidationError(
                "final feedback schema "
                "fields are invalid"
            )

        if (
            payload[
                "feedback_kind"
            ]
            != expected_kind
        ):
            raise FeedbackOutputValidationError(
                "feedback_kind mismatch"
            )

        sections = payload[
            "sections"
        ]

        if not isinstance(
            sections,
            Mapping,
        ):
            raise FeedbackOutputValidationError(
                "final sections must "
                "be an object"
            )

        expected_sections = {
            "decision_journey",
            "confidence_and_action",
            "overall_reflection",
        }

        if (
            set(sections)
            != expected_sections
        ):
            raise FeedbackOutputValidationError(
                "final feedback sections "
                "are invalid"
            )

        section_texts = [
            _require_text(
                name,
                sections[name],
            )
            for name in (
                "decision_journey",
                "confidence_and_action",
                "overall_reflection",
            )
        ]

        prose = "\n".join(
            section_texts
        )

        words = _word_count(
            prose
        )

        if not (
            250 <= words <= 350
        ):
            raise FeedbackOutputValidationError(
                "final feedback must contain "
                "250-350 English words total"
            )

    else:
        raise FeedbackOutputValidationError(
            "unsupported context feedback_kind"
        )

    _validate_content_language(
        prose
    )

    _validate_quantitative_literals(
        text=prose,
        pack=context_pack,
    )

    detached = json.loads(
        json.dumps(
            payload,
            ensure_ascii=False,
        )
    )

    return ValidatedFeedbackOutput(
        output_contract_version=(
            OUTPUT_CONTRACT_VERSION
        ),
        feedback_kind=(
            expected_kind
        ),
        payload=detached,
        word_count=words,
        output_sha256=(
            _canonical_sha256(
                detached
            )
        ),
    )
