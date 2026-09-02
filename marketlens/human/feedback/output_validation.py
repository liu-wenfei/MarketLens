"""Validation for reflection-only MarketLens LLM output.

Deterministic feedback structure and metrics are backend-owned.
The model supplies only one qualitative reflection string.

No LLM or network call is made here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from .context import FeedbackContextPack


OUTPUT_CONTRACT_VERSION = (
    "marketlens-feedback-reflection-output-v2"
)


class FeedbackOutputValidationError(ValueError):
    pass


_WORD_RE = re.compile(
    r"[A-Za-z0-9]+"
    r"(?:['’\-][A-Za-z0-9]+)*"
)


_NUMERIC_LITERAL_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"[-+]?"
    r"(?:\d+(?:,\d{3})*)"
    r"(?:\.\d+)?"
    r"%?"
    r"(?![A-Za-z0-9_])"
)


_UNSUPPORTED_ATTRIBUTION_INFERENCE_RE = re.compile(
    r"\b(?:suggests?|suggesting|"
    r"indicates?|indicating|"
    r"implies?|implying|"
    r"reflects?|reflecting|"
    r"shows?|showing|"
    r"reveals?|revealing|"
    r"points?\s+to|"
    r"hints?\s+at|"
    r"appears?\s+to|"
    r"may\s+(?:reflect|indicate|suggest|imply))\b"
    r"[\s\S]{0,120}?"
    r"\b(?:preference|reliance|emphasis|"
    r"motivation|intent(?:ion)?|attention|"
    r"strategy|risk posture|risk containment|"
    r"monitoring process|methodical approach|"
    r"cautious stance|deliberate pacing|"
    r"validation of signals)\b",
    re.IGNORECASE,
)


_DIRECT_PARTICIPANT_STATE_RE = re.compile(
    r"\b(?:you|the participant)\s+(?:"
    r"prefer(?:red|s)?|"
    r"rely|relies|relied|relying|"
    r"intend(?:ed|s)?|"
    r"monitor(?:ed|s|ing)?|"
    r"believ(?:e|ed|es|ing)|"
    r"focus(?:ed|es|ing)?|"
    r"prioriti[sz](?:e|ed|es|ing)|"
    r"(?:were|was)\s+(?:cautious|methodical|deliberate)"
    r")\b",
    re.IGNORECASE,
)


_PARTICIPANT_REPORTING_CUE_RE = re.compile(
    r"\b(?:participant-reported|"
    r"participant reported|"
    r"reported|stated|"
    r"rationale\s+(?:reported|stated|described)|"
    r"evidence selection\s+(?:reported|stated|described))\b",
    re.IGNORECASE,
)


_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[.!?])\s+"
)


_FORBIDDEN_PATTERNS = (
    (
        "first-person participant impersonation",
        re.compile(
            r"\b(?:I|me|my|mine|myself)\b",
            re.IGNORECASE,
        ),
    ),
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
            r"stimulus|request|event|transaction)_id\b",
            re.IGNORECASE,
        ),
    ),
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
            r"\b(?:well done|good job|great job|"
            r"excellent job|great decision|"
            r"smart decision|excellent decision)\b",
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
        "prescriptive or optimisation language",
        re.compile(
            r"\b(?:moving forward|going forward|"
            r"aim to|aiming to|try to|trying to|"
            r"potential edge|risk management|"
            r"investment strategy|trading strategy|"
            r"disciplined|discipline)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "evaluative decision-quality language",
        re.compile(
            r"\b(?:better decision|worse decision|"
            r"good decision|poor decision|"
            r"effective decision|successful decision|"
            r"high-quality|low-quality)\b",
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
    (
        "Agent internal state",
        re.compile(
            r"\b(?:top[_ ]?user|prominence|"
            r"agent holdings|agent trades|"
            r"agent strategy|raw type)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "explicit causal claim",
        re.compile(
            r"\b(?:caused you to|caused your|"
            r"led you to)\b",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class ValidatedFeedbackOutput:
    output_contract_version: str
    feedback_kind: str
    payload: Mapping[str, object]
    word_count: int
    output_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "output_contract_version": (
                self.output_contract_version
            ),
            "feedback_kind": (
                self.feedback_kind
            ),
            "payload": dict(self.payload),
            "word_count": self.word_count,
            "output_sha256": self.output_sha256,
        }


def _reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
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
    raw: str | Mapping[str, object],
) -> dict[str, object]:
    if isinstance(raw, Mapping):
        return dict(raw)

    if not isinstance(raw, str):
        raise FeedbackOutputValidationError(
            "feedback output must be JSON text or a mapping"
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
            object_pairs_hook=_reject_duplicate_keys,
        )
    except FeedbackOutputValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise FeedbackOutputValidationError(
            "invalid feedback JSON"
        ) from exc

    if not isinstance(value, dict):
        raise FeedbackOutputValidationError(
            "feedback JSON root must be an object"
        )

    return value


def _reflection_text(
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise FeedbackOutputValidationError(
            "reflection must be non-empty text"
        )

    return value.strip()


def _word_count(
    text: str,
) -> int:
    return len(
        _WORD_RE.findall(text)
    )


def _validate_evidence_attribution(
    text: str,
) -> None:
    """Reject unsupported inference about unobserved participant states."""

    for sentence in _SENTENCE_SPLIT_RE.split(text):
        sentence = sentence.strip()

        if not sentence:
            continue

        if _UNSUPPORTED_ATTRIBUTION_INFERENCE_RE.search(
            sentence
        ):
            raise FeedbackOutputValidationError(
                "reflection contains unsupported psychological, "
                "attentional, intentional, or strategic attribution"
            )

        if (
            _DIRECT_PARTICIPANT_STATE_RE.search(sentence)
            and not _PARTICIPANT_REPORTING_CUE_RE.search(
                sentence
            )
        ):
            raise FeedbackOutputValidationError(
                "reflection contains unsupported psychological, "
                "attentional, intentional, or strategic attribution"
            )


def _validate_language(
    text: str,
) -> None:
    for label, pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(text):
            raise FeedbackOutputValidationError(
                "reflection contains forbidden "
                f"{label}"
            )

    _validate_evidence_attribution(
        text
    )

    if _NUMERIC_LITERAL_RE.search(text):
        raise FeedbackOutputValidationError(
            "reflection must not repeat or introduce "
            "numerical values; deterministic panels "
            "display them separately"
        )


def _canonical_sha256(
    payload: Mapping[str, object],
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
    raw: str | Mapping[str, object],
    *,
    context_pack: FeedbackContextPack,
) -> ValidatedFeedbackOutput:
    if not isinstance(
        context_pack,
        FeedbackContextPack,
    ):
        raise FeedbackOutputValidationError(
            "output validation requires a validated "
            "FeedbackContextPack"
        )

    payload = _parse_output(raw)

    if set(payload) != {
        "feedback_kind",
        "reflection",
    }:
        raise FeedbackOutputValidationError(
            "reflection output schema fields are invalid"
        )

    expected_kind = (
        context_pack.feedback_kind
    )

    if (
        payload["feedback_kind"]
        != expected_kind
    ):
        raise FeedbackOutputValidationError(
            "feedback_kind mismatch"
        )

    reflection = _reflection_text(
        payload["reflection"]
    )

    words = _word_count(
        reflection
    )

    if (
        expected_kind
        == "multi_period_decision_feedback"
    ):
        if not (
            110 <= words <= 170
        ):
            raise FeedbackOutputValidationError(
                "mid-session reflection must "
                "contain 110-170 English words"
            )

    elif (
        expected_kind
        == "final_session_summary"
    ):
        if not (
            250 <= words <= 350
        ):
            raise FeedbackOutputValidationError(
                "final reflection must "
                "contain 250-350 English words"
            )

    else:
        raise FeedbackOutputValidationError(
            "unsupported context feedback_kind"
        )

    _validate_language(
        reflection
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
        feedback_kind=expected_kind,
        payload=detached,
        word_count=words,
        output_sha256=(
            _canonical_sha256(detached)
        ),
    )
