"""Deterministic participant-safe context packs for MarketLens feedback.

This module prepares the only qualitative/quantitative context that a later
feedback LLM may receive.

It deliberately does NOT:
- call an LLM;
- query raw Agent belief/type/prominence/trading state;
- expose experimental truth labels or condition metadata;
- expose internal judgement/stimulus identifiers;
- read prior LLM feedback text.

Participant-authored and participant-visible text remains untrusted DATA.
Prompt-level instruction handling belongs to the later frozen prompt contract.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import date
import json
import math
from typing import Any

from marketlens.human.measurement.models import (
    ParticipantEventType,
)
from marketlens.human.schemas import (
    ParticipantBackgroundRead,
)
from marketlens.source_cues.adapter import (
    assert_formal_source_cue_freeze,
    decorate_controlled_stimulus_payload,
)
from marketlens.stimulus.engine import (
    VisibilityMoment,
)
from marketlens.stimulus.manifest import (
    sha256_json,
    verify_hashes,
)
from marketlens.stimulus.schema import (
    FormalUseStatus,
)

from .source import FeedbackKind


CONTEXT_PACK_VERSION = (
    "marketlens-feedback-context-v1"
)


class FeedbackContextError(ValueError):
    """Participant feedback context cannot be proven safe/complete."""


@dataclass(frozen=True, slots=True)
class ContextLimits:
    """Explicit deterministic context bounds.

    No defaults are provided deliberately. Formal runtime wiring must supply
    an explicitly versioned limits policy rather than silently inheriting a
    development choice.
    """

    policy_version: str

    max_news_items: int
    max_community_posts: int

    max_news_chars: int
    max_community_chars: int

    max_rationale_chars: int

    max_evidence_sources: int
    max_evidence_source_chars: int

    max_controlled_headline_chars: int
    max_controlled_body_chars: int

    max_source_label_chars: int
    max_source_descriptor_chars: int

    def __post_init__(self) -> None:
        if (
            not isinstance(
                self.policy_version,
                str,
            )
            or not self.policy_version.strip()
        ):
            raise FeedbackContextError(
                "context policy_version must be non-empty"
            )

        for field_name in (
            "max_news_items",
            "max_community_posts",
            "max_news_chars",
            "max_community_chars",
            "max_rationale_chars",
            "max_evidence_sources",
            "max_evidence_source_chars",
            "max_controlled_headline_chars",
            "max_controlled_body_chars",
            "max_source_label_chars",
            "max_source_descriptor_chars",
        ):
            value = getattr(
                self,
                field_name,
            )

            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
            ):
                raise FeedbackContextError(
                    f"{field_name} must be "
                    "a positive integer"
                )


@dataclass(frozen=True, slots=True)
class FeedbackContextPack:
    context_pack_version: str
    context_policy_version: str

    feedback_kind: str

    window: Mapping[str, int]
    statistics: Mapping[str, object]

    information_environment: Mapping[
        str,
        object,
    ]

    participant_reflections: tuple[
        Mapping[str, object],
        ...,
    ]

    prior_context: Mapping[
        str,
        object,
    ] | None

    context_coverage: Mapping[
        str,
        object,
    ]

    def to_dict(self) -> dict[str, object]:
        # JSON round-trip creates a detached, JSON-safe representation and
        # normalises tuples to arrays before hashing/prompt serialization.
        return json.loads(
            json.dumps(
                asdict(self),
                ensure_ascii=False,
            )
        )

    def sha256(self) -> str:
        return sha256_json(
            self.to_dict()
        )


_EXPECTED_WINDOWS: Mapping[
    FeedbackKind,
    tuple[int, int],
] = {
    FeedbackKind.F1: (1, 4),
    FeedbackKind.F2: (5, 11),
    FeedbackKind.FINAL: (1, 15),
}


_EXPECTED_JUDGEMENTS: Mapping[
    FeedbackKind,
    frozenset[str],
] = {
    FeedbackKind.F1: frozenset(
        {"J0", "J1"}
    ),
    FeedbackKind.F2: frozenset(
        {"J2", "J3"}
    ),
    FeedbackKind.FINAL: frozenset(
        {
            "J0",
            "J1",
            "J2",
            "J3",
            "J4",
        }
    ),
}


_PROMPT_FEEDBACK_KIND: Mapping[
    FeedbackKind,
    str,
] = {
    FeedbackKind.F1: (
        "multi_period_decision_feedback"
    ),
    FeedbackKind.F2: (
        "multi_period_decision_feedback"
    ),
    FeedbackKind.FINAL: (
        "final_session_summary"
    ),
}


# Neutral participant-experienced chronology for same-period
# assessment -> controlled information -> assessment sequences.
#
# J labels remain backend-only and are never emitted into the pack.
_ASSESSMENT_WITHIN_PERIOD_SEQUENCE = {
    "J0": 1,
    "J1": 3,
    "J2": 1,
    "J3": 3,
    "J4": 1,
}

_CONTROLLED_WITHIN_PERIOD_SEQUENCE = 2


_BACKGROUND_KEYS = frozenset(
    {
        "current_date",
        "natural_news",
        "forum_posts",
    }
)


_FORUM_KEYS = frozenset(
    {
        "post_id",
        "author_id",
        "source_label",
        "display_text",
        "created_at",
    }
)


_DECORATED_STIMULUS_KEYS = frozenset(
    {
        "stimulus_id",
        "kind",
        "headline",
        "body",
        "corrects_stimulus_id",
        "source_label",
        "source_descriptor",
    }
)


# Structural keys forbidden from reaching the LLM-facing context pack.
# Values are intentionally not scanned: participant-visible text may itself
# contain words such as "score", "belief", or "correction".
_FORBIDDEN_KEYS = frozenset(
    {
        "truth_label",
        "misinformation_truth",
        "correct_answer",
        "expected_action",
        "future_price",
        "future_prices",
        "future_news",
        "future_stimulus",
        "future_correction",
        "condition",
        "condition_assignment",
        "episode_id",
        "experiment_step",
        "judgement_event",
        "stimulus_id",
        "stimulus_version",
        "stimulus_sha256",
        "corrects_stimulus_id",
        "participant_id",
        "session_id",
        "request_id",
        "event_id",
        "domain_record_id",
        "judgement_id",
        "assessment_id",
        "completion_id",
        "transaction_id",
        "payload_digest",
        "source_cue",
        "content_sha256",
        "manifest_sha256",
        "protocol_version",
        "material_version",
        "market_open",
        "participant_trading_enabled",
        "occurred_at_utc",
        "submitted_at",
        "current_stage",
        "next_stage",
        "kind",
        "belief",
        "agent_belief",
        "raw_type",
        "type",
        "top_user",
        "prominence",
        "strategy",
        "agent_holdings",
        "agent_trades",
        "other_participant",
        "population_percentile",
        "percentile",
        "rank",
        "score",
        "bias_resistance",
        "scenario_score",
    }
)


def _field(
    value: object,
    name: str,
) -> Any:
    if isinstance(value, Mapping):
        if name not in value:
            raise FeedbackContextError(
                f"source missing field "
                f"{name!r}"
            )
        return value[name]

    if not hasattr(value, name):
        raise FeedbackContextError(
            f"source missing attribute "
            f"{name!r}"
        )

    return getattr(
        value,
        name,
    )


def _nonempty(
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise FeedbackContextError(
            f"{name} must be "
            "a non-empty string"
        )

    return value.strip()


def _strict_int(
    name: str,
    value: object,
    *,
    minimum: int | None = None,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise FeedbackContextError(
            f"{name} must be an integer"
        )

    if (
        minimum is not None
        and value < minimum
    ):
        raise FeedbackContextError(
            f"{name} must be >= {minimum}"
        )

    return value


def _finite(
    name: str,
    value: object,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (int, float),
        )
    ):
        raise FeedbackContextError(
            f"{name} must be numeric"
        )

    result = float(value)

    if not math.isfinite(result):
        raise FeedbackContextError(
            f"{name} must be finite"
        )

    if (
        minimum is not None
        and result < minimum
    ):
        raise FeedbackContextError(
            f"{name} must be >= {minimum}"
        )

    if (
        maximum is not None
        and result > maximum
    ):
        raise FeedbackContextError(
            f"{name} must be <= {maximum}"
        )

    return result


def _iso_date(
    name: str,
    value: object,
) -> str:
    if type(value) is date:
        return value.isoformat()

    if not isinstance(value, str):
        raise FeedbackContextError(
            f"{name} must be YYYY-MM-DD"
        )

    try:
        parsed = date.fromisoformat(
            value
        )
    except ValueError as exc:
        raise FeedbackContextError(
            f"{name} must be YYYY-MM-DD"
        ) from exc

    return parsed.isoformat()


def _event_type_name(
    value: object,
) -> str:
    raw = getattr(
        value,
        "value",
        value,
    )
    return _nonempty(
        "event_type",
        raw,
    )


def _bounded_text(
    value: object,
    *,
    name: str,
    max_chars: int,
    allow_empty: bool = False,
) -> tuple[str, bool]:
    if not isinstance(
        value,
        str,
    ):
        raise FeedbackContextError(
            f"{name} must be text"
        )

    if (
        not allow_empty
        and not value.strip()
    ):
        raise FeedbackContextError(
            f"{name} must be non-empty"
        )

    if len(value) <= max_chars:
        return value, False

    return (
        value[:max_chars],
        True,
    )


def _validate_no_forbidden_keys(
    value: object,
    *,
    path: str = "$",
) -> None:
    if isinstance(
        value,
        Mapping,
    ):
        for key, child in value.items():
            if not isinstance(
                key,
                str,
            ):
                raise FeedbackContextError(
                    "context mappings must use "
                    "string keys"
                )

            if key in _FORBIDDEN_KEYS:
                raise FeedbackContextError(
                    "forbidden feedback context "
                    f"field at {path}.{key}"
                )

            _validate_no_forbidden_keys(
                child,
                path=f"{path}.{key}",
            )

    elif isinstance(
        value,
        (list, tuple),
    ):
        for index, child in enumerate(
            value
        ):
            _validate_no_forbidden_keys(
                child,
                path=f"{path}[{index}]",
            )


def _json_evidence(
    value: object,
) -> list[str]:
    if isinstance(
        value,
        str,
    ):
        try:
            decoded = json.loads(
                value
            )
        except json.JSONDecodeError as exc:
            raise FeedbackContextError(
                "evidence_sources is not "
                "valid JSON"
            ) from exc
    else:
        decoded = value

    if not isinstance(
        decoded,
        list,
    ):
        raise FeedbackContextError(
            "evidence_sources must "
            "decode to a list"
        )

    result: list[str] = []

    for item in decoded:
        if not isinstance(
            item,
            str,
        ):
            raise FeedbackContextError(
                "evidence_sources values "
                "must be strings"
            )
        result.append(item)

    return result


class FeedbackContextBuilder:
    """Build one deterministic participant-safe feedback context pack."""

    def __init__(
        self,
        *,
        statistics_source: object,
        judgements: object,
        events: object,
        assignments: object,
        projections: Mapping[
            str,
            object,
        ],
        contract: object,
        stimulus_engine: object,
        target_stock_id: str,
        limits: ContextLimits,
        controlled_payload_decorator: Callable[
            [Mapping[str, object]],
            Mapping[str, object],
        ] = decorate_controlled_stimulus_payload,
        source_cue_freeze_checker: Callable[
            [],
            object,
        ] = assert_formal_source_cue_freeze,
        stimulus_material_validator: Callable[
            [object],
            object,
        ] = verify_hashes,
    ):
        self.statistics_source = (
            statistics_source
        )
        self.judgements = judgements
        self.events = events
        self.assignments = assignments
        self.projections = dict(
            projections
        )
        self.contract = contract
        self.stimulus_engine = (
            stimulus_engine
        )
        self.target_stock_id = (
            _nonempty(
                "target_stock_id",
                target_stock_id,
            )
        )
        self.limits = limits

        self.controlled_payload_decorator = (
            controlled_payload_decorator
        )
        self.source_cue_freeze_checker = (
            source_cue_freeze_checker
        )
        self.stimulus_material_validator = (
            stimulus_material_validator
        )

    def build(
        self,
        session_id: str,
        kind: FeedbackKind | str,
    ) -> FeedbackContextPack:
        session_id = _nonempty(
            "session_id",
            session_id,
        )

        try:
            resolved_kind = (
                kind
                if isinstance(
                    kind,
                    FeedbackKind,
                )
                else FeedbackKind(kind)
            )
        except ValueError as exc:
            raise FeedbackContextError(
                f"unsupported feedback kind: "
                f"{kind!r}"
            ) from exc

        statistics = (
            self._statistics(
                session_id,
                resolved_kind,
            )
        )

        start_period, end_period = (
            self._validated_window(
                statistics,
                resolved_kind,
            )
        )

        episode_id, projection = (
            self._projection_for_session(
                session_id
            )
        )

        events = (
            self._events_for_session(
                session_id
            )
        )

        background_payloads = (
            self._background_payloads(
                session_id=session_id,
                episode_id=episode_id,
                projection=projection,
                events=events,
                kind=resolved_kind,
                start_period=start_period,
                end_period=end_period,
            )
        )

        (
            information,
            information_coverage,
        ) = self._information_environment(
            kind=resolved_kind,
            background_payloads=(
                background_payloads
            ),
            start_period=start_period,
            end_period=end_period,
        )

        controlled = (
            self._controlled_information(
                session_id=session_id,
                episode_id=episode_id,
                events=events,
                start_period=start_period,
                end_period=end_period,
            )
        )

        information[
            "released_controlled_information"
        ] = controlled

        (
            reflections,
            reflection_coverage,
        ) = self._participant_reflections(
            session_id=session_id,
            kind=resolved_kind,
            start_period=start_period,
            end_period=end_period,
        )

        prior_context = (
            self._prior_context(
                session_id=session_id,
                kind=resolved_kind,
            )
        )

        coverage = {
            **information_coverage,
            **reflection_coverage,
            "controlled_items_included": (
                len(controlled)
            ),
            "content_is_deterministically_bounded": (
                True
            ),
        }

        pack = FeedbackContextPack(
            context_pack_version=(
                CONTEXT_PACK_VERSION
            ),
            context_policy_version=(
                self.limits.policy_version
            ),
            feedback_kind=(
                _PROMPT_FEEDBACK_KIND[
                    resolved_kind
                ]
            ),
            window=dict(
                statistics["window"]
            ),
            statistics=statistics,
            information_environment=(
                information
            ),
            participant_reflections=(
                tuple(reflections)
            ),
            prior_context=prior_context,
            context_coverage=coverage,
        )

        payload = pack.to_dict()

        _validate_no_forbidden_keys(
            payload
        )

        return pack

    def _statistics(
        self,
        session_id: str,
        kind: FeedbackKind,
    ) -> dict[str, object]:
        try:
            result = (
                self.statistics_source.build(
                    session_id,
                    kind,
                )
            )
        except Exception as exc:
            raise FeedbackContextError(
                "authoritative feedback "
                "statistics build failed"
            ) from exc

        try:
            payload = result.to_dict()
        except Exception as exc:
            raise FeedbackContextError(
                "statistics object cannot "
                "be serialized"
            ) from exc

        if not isinstance(
            payload,
            Mapping,
        ):
            raise FeedbackContextError(
                "statistics payload must "
                "be a mapping"
            )

        detached = json.loads(
            json.dumps(
                payload,
                ensure_ascii=False,
            )
        )

        _validate_no_forbidden_keys(
            detached,
            path="$.statistics",
        )

        return detached

    @staticmethod
    def _validated_window(
        statistics: Mapping[
            str,
            object,
        ],
        kind: FeedbackKind,
    ) -> tuple[int, int]:
        raw_window = statistics.get(
            "window"
        )

        if not isinstance(
            raw_window,
            Mapping,
        ):
            raise FeedbackContextError(
                "statistics window "
                "is missing"
            )

        start = _strict_int(
            "window.start_period",
            raw_window.get(
                "start_period"
            ),
            minimum=1,
        )
        end = _strict_int(
            "window.end_period",
            raw_window.get(
                "end_period"
            ),
            minimum=1,
        )
        reviewed = _strict_int(
            "window.periods_reviewed",
            raw_window.get(
                "periods_reviewed"
            ),
            minimum=1,
        )

        expected = (
            _EXPECTED_WINDOWS[kind]
        )

        if (
            (start, end)
            != expected
        ):
            raise FeedbackContextError(
                "statistics window "
                "disagrees with frozen "
                "feedback context contract"
            )

        if (
            reviewed
            != end - start + 1
        ):
            raise FeedbackContextError(
                "statistics periods_reviewed "
                "is inconsistent"
            )

        return start, end

    def _projection_for_session(
        self,
        session_id: str,
    ) -> tuple[str, object]:
        try:
            assignment = (
                self.assignments.get(
                    session_id
                )
            )
        except Exception as exc:
            raise FeedbackContextError(
                "episode assignment read failed"
            ) from exc

        if assignment is None:
            raise FeedbackContextError(
                "session has no episode assignment"
            )

        episode_id = _nonempty(
            "episode_id",
            _field(
                assignment,
                "episode_id",
            ),
        )

        try:
            projection = (
                self.projections[
                    episode_id
                ]
            )
        except KeyError as exc:
            raise FeedbackContextError(
                "assigned participant-safe "
                "projection is unavailable"
            ) from exc

        bound_id = getattr(
            getattr(
                projection,
                "episode",
                None,
            ),
            "episode_id",
            None,
        )

        if bound_id != episode_id:
            raise FeedbackContextError(
                "projection episode binding "
                "mismatch"
            )

        return (
            episode_id,
            projection,
        )

    def _events_for_session(
        self,
        session_id: str,
    ) -> tuple[object, ...]:
        try:
            rows = tuple(
                self.events.list_for_session(
                    session_id
                )
            )
        except Exception as exc:
            raise FeedbackContextError(
                "participant event ledger "
                "read failed"
            ) from exc

        for row in rows:
            if (
                _nonempty(
                    "event session_id",
                    _field(
                        row,
                        "session_id",
                    ),
                )
                != session_id
            ):
                raise FeedbackContextError(
                    "event reader returned "
                    "another session"
                )

        return rows

    def _checkpoint_date(
        self,
        period_number: int,
    ) -> str:
        step = period_number - 1

        try:
            raw = self.contract.checkpoint_date(
                step
            )
        except Exception as exc:
            raise FeedbackContextError(
                "checkpoint date "
                f"unavailable for period "
                f"{period_number}"
            ) from exc

        return _iso_date(
            "checkpoint date",
            raw,
        )

    def _safe_background_payload(
        self,
        *,
        projection: object,
        period_number: int,
    ) -> Mapping[str, object]:
        expected_date = (
            self._checkpoint_date(
                period_number
            )
        )

        try:
            payload = projection.project(
                current_date=expected_date
            )
        except Exception as exc:
            raise FeedbackContextError(
                "participant-safe background "
                "projection failed"
            ) from exc

        if not isinstance(
            payload,
            Mapping,
        ):
            raise FeedbackContextError(
                "background projection "
                "must be a mapping"
            )

        if set(payload) != _BACKGROUND_KEYS:
            raise FeedbackContextError(
                "background participant-safe "
                "allow-list changed"
            )

        if (
            _iso_date(
                "background current_date",
                payload["current_date"],
            )
            != expected_date
        ):
            raise FeedbackContextError(
                "background projection date "
                "mismatch"
            )

        news = payload[
            "natural_news"
        ]

        if not isinstance(
            news,
            list,
        ):
            raise FeedbackContextError(
                "natural_news must be a list"
            )

        for item in news:
            _nonempty(
                "natural news item",
                item,
            )

        forum = payload[
            "forum_posts"
        ]

        if not isinstance(
            forum,
            list,
        ):
            raise FeedbackContextError(
                "forum_posts must be a list"
            )

        seen: set[int] = set()

        for raw_post in forum:
            if not isinstance(
                raw_post,
                Mapping,
            ):
                raise FeedbackContextError(
                    "forum post must "
                    "be a mapping"
                )

            if set(
                raw_post
            ) != _FORUM_KEYS:
                raise FeedbackContextError(
                    "forum participant-safe "
                    "allow-list changed"
                )

            post_id = _strict_int(
                "forum post_id",
                raw_post["post_id"],
                minimum=0,
            )

            if post_id in seen:
                raise FeedbackContextError(
                    "duplicate forum post_id "
                    "inside projection"
                )

            seen.add(post_id)

            _nonempty(
                "forum author_id",
                raw_post[
                    "author_id"
                ],
            )
            _nonempty(
                "forum source_label",
                raw_post[
                    "source_label"
                ],
            )
            _nonempty(
                "forum display_text",
                raw_post[
                    "display_text"
                ],
            )
            _nonempty(
                "forum created_at",
                raw_post[
                    "created_at"
                ],
            )

        return payload

    def _background_payloads(
        self,
        *,
        session_id: str,
        episode_id: str,
        projection: object,
        events: tuple[
            object,
            ...,
        ],
        kind: FeedbackKind,
        start_period: int,
        end_period: int,
    ) -> dict[
        int,
        Mapping[str, object],
    ]:
        background_events: dict[
            int,
            list[object],
        ] = {}

        for row in events:
            if (
                _event_type_name(
                    _field(
                        row,
                        "event_type",
                    )
                )
                != ParticipantEventType
                .BACKGROUND_EXPOSED
                .value
            ):
                continue

            step = _strict_int(
                "background experiment_step",
                _field(
                    row,
                    "experiment_step",
                ),
                minimum=0,
            )

            background_events.setdefault(
                step,
                [],
            ).append(row)

        required_periods = set(
            range(
                start_period,
                end_period + 1,
            )
        )

        # F2 needs the prior exposed P4 cumulative forum projection only as
        # a deterministic identity baseline. No P1-P4 raw text is re-sent.
        if kind is FeedbackKind.F2:
            required_periods.add(4)

        result: dict[
            int,
            Mapping[str, object],
        ] = {}

        for period in sorted(
            required_periods
        ):
            step = period - 1

            candidates = (
                background_events.get(
                    step,
                    [],
                )
            )

            if len(candidates) != 1:
                raise FeedbackContextError(
                    "context requires exactly "
                    "one BACKGROUND_EXPOSED "
                    f"event for period "
                    f"{period}"
                )

            event = candidates[0]

            if (
                _nonempty(
                    "background episode_id",
                    _field(
                        event,
                        "episode_id",
                    ),
                )
                != episode_id
            ):
                raise FeedbackContextError(
                    "background exposure "
                    "episode mismatch"
                )

            expected_date = (
                self._checkpoint_date(
                    period
                )
            )

            if (
                _iso_date(
                    "background exposure date",
                    _field(
                        event,
                        "agent_world_date",
                    ),
                )
                != expected_date
            ):
                raise FeedbackContextError(
                    "background exposure "
                    "date mismatch"
                )

            payload = (
                self._safe_background_payload(
                    projection=projection,
                    period_number=period,
                )
            )

            exact_background = (
                ParticipantBackgroundRead(
                    session_id=session_id,
                    current_date=(
                        expected_date
                    ),
                    natural_news=(
                        payload[
                            "natural_news"
                        ]
                    ),
                    forum_posts=(
                        payload[
                            "forum_posts"
                        ]
                    ),
                )
            )

            expected_digest = (
                sha256_json(
                    exact_background.model_dump(
                        mode="json"
                    )
                )
            )

            stored_digest = (
                _nonempty(
                    "background payload_digest",
                    _field(
                        event,
                        "payload_digest",
                    ),
                )
            )

            if (
                stored_digest
                != expected_digest
            ):
                raise FeedbackContextError(
                    "background payload digest "
                    "mismatch"
                )

            result[
                period
            ] = payload

        return result

    def _information_environment(
        self,
        *,
        kind: FeedbackKind,
        background_payloads: Mapping[
            int,
            Mapping[str, object],
        ],
        start_period: int,
        end_period: int,
    ) -> tuple[
        dict[str, object],
        dict[str, object],
    ]:
        news_raw: list[
            dict[str, object]
        ] = []

        community_raw: list[
            dict[str, object]
        ] = []

        seen_labels: dict[
            int,
            str,
        ] = {}

        if kind is FeedbackKind.F2:
            baseline = (
                background_payloads[4]
            )

            for post in baseline[
                "forum_posts"
            ]:
                assert isinstance(
                    post,
                    Mapping,
                )

                post_id = int(
                    post["post_id"]
                )
                source_label = str(
                    post["source_label"]
                )

                seen_labels[
                    post_id
                ] = source_label

        for period in range(
            start_period,
            end_period + 1,
        ):
            payload = (
                background_payloads[
                    period
                ]
            )

            day = self._checkpoint_date(
                period
            )

            for text in payload[
                "natural_news"
            ]:
                news_raw.append(
                    {
                        "period_number": (
                            period
                        ),
                        "date": day,
                        "text": text,
                    }
                )

            for post in payload[
                "forum_posts"
            ]:
                assert isinstance(
                    post,
                    Mapping,
                )

                post_id = int(
                    post["post_id"]
                )
                source_label = str(
                    post["source_label"]
                )

                if post_id in seen_labels:
                    if (
                        seen_labels[
                            post_id
                        ]
                        != source_label
                    ):
                        raise FeedbackContextError(
                            "participant-visible "
                            "source label drifted "
                            f"for post {post_id}"
                        )

                    continue

                seen_labels[
                    post_id
                ] = source_label

                community_raw.append(
                    {
                        "period_first_available": (
                            period
                        ),
                        "date_first_available": (
                            day
                        ),
                        "source_label": (
                            source_label
                        ),
                        "created_at": (
                            str(
                                post[
                                    "created_at"
                                ]
                            )
                        ),
                        "text": (
                            str(
                                post[
                                    "display_text"
                                ]
                            )
                        ),
                    }
                )

        included_news_raw = (
            news_raw[
                : self.limits
                .max_news_items
            ]
        )

        included_community_raw = (
            community_raw[
                : self.limits
                .max_community_posts
            ]
        )

        news_output: list[
            dict[str, object]
        ] = []

        community_output: list[
            dict[str, object]
        ] = []

        truncated_text_fields = 0

        for item in included_news_raw:
            bounded, truncated = (
                _bounded_text(
                    item["text"],
                    name="natural news",
                    max_chars=(
                        self.limits
                        .max_news_chars
                    ),
                )
            )

            if truncated:
                truncated_text_fields += 1

            news_output.append(
                {
                    "period_number": (
                        item[
                            "period_number"
                        ]
                    ),
                    "date": item[
                        "date"
                    ],
                    "text": bounded,
                    "text_truncated": (
                        truncated
                    ),
                }
            )

        for item in included_community_raw:
            source_label = (
                _nonempty(
                    "community source_label",
                    item[
                        "source_label"
                    ],
                )
            )

            if (
                len(source_label)
                > self.limits
                .max_source_label_chars
            ):
                raise FeedbackContextError(
                    "participant-visible "
                    "community source label "
                    "exceeds frozen context bound"
                )

            bounded, truncated = (
                _bounded_text(
                    item["text"],
                    name="community text",
                    max_chars=(
                        self.limits
                        .max_community_chars
                    ),
                )
            )

            if truncated:
                truncated_text_fields += 1

            community_output.append(
                {
                    "period_first_available": (
                        item[
                            "period_first_available"
                        ]
                    ),
                    "date_first_available": (
                        item[
                            "date_first_available"
                        ]
                    ),
                    "source_label": (
                        source_label
                    ),
                    "created_at": (
                        item[
                            "created_at"
                        ]
                    ),
                    "text": bounded,
                    "text_truncated": (
                        truncated
                    ),
                }
            )

        coverage = {
            "news_items_total": (
                len(news_raw)
            ),
            "news_items_included": (
                len(news_output)
            ),
            "news_items_omitted": (
                len(news_raw)
                - len(news_output)
            ),
            "community_posts_total": (
                len(community_raw)
            ),
            "community_posts_included": (
                len(
                    community_output
                )
            ),
            "community_posts_omitted": (
                len(community_raw)
                - len(
                    community_output
                )
            ),
            "information_text_fields_truncated": (
                truncated_text_fields
            ),
        }

        return (
            {
                "available_news": (
                    news_output
                ),
                "available_community_content": (
                    community_output
                ),
            },
            coverage,
        )

    def _controlled_information(
        self,
        *,
        session_id: str,
        episode_id: str,
        events: tuple[
            object,
            ...,
        ],
        start_period: int,
        end_period: int,
    ) -> list[
        dict[str, object]
    ]:
        engine = self.stimulus_engine
        material = getattr(
            engine,
            "material",
            None,
        )

        if material is None:
            raise FeedbackContextError(
                "controlled stimulus "
                "engine is unbound"
            )

        if (
            getattr(
                material,
                "formal_use_status",
                None,
            )
            is not FormalUseStatus
            .FORMAL_FROZEN
        ):
            raise FeedbackContextError(
                "feedback context requires "
                "formal_frozen stimulus material"
            )

        try:
            self.stimulus_material_validator(
                material
            )
            self.source_cue_freeze_checker()
        except Exception as exc:
            raise FeedbackContextError(
                "controlled stimulus "
                "freeze validation failed"
            ) from exc

        releases = (
            (
                material.misinformation,
                int(
                    engine
                    .misinformation_step
                ),
                VisibilityMoment
                .POST_MISINFORMATION_RELEASE,
            ),
            (
                material.correction,
                int(
                    engine
                    .correction_step
                ),
                VisibilityMoment
                .POST_CORRECTION_RELEASE,
            ),
        )

        controlled_events: list[
            object
        ] = []

        for row in events:
            if (
                _event_type_name(
                    _field(
                        row,
                        "event_type",
                    )
                )
                == ParticipantEventType
                .CONTROLLED_STIMULUS_EXPOSED
                .value
            ):
                controlled_events.append(
                    row
                )

        output: list[
            dict[str, object]
        ] = []

        expected_event_ids: set[
            str
        ] = set()

        for (
            item,
            step,
            moment,
        ) in releases:
            period = step + 1

            if not (
                start_period
                <= period
                <= end_period
            ):
                continue

            item_id = _nonempty(
                "stimulus_id",
                getattr(
                    item,
                    "stimulus_id",
                    None,
                ),
            )

            candidates = [
                row
                for row
                in controlled_events
                if (
                    _field(
                        row,
                        "stimulus_id",
                    )
                    == item_id
                    and _strict_int(
                        "controlled step",
                        _field(
                            row,
                            "experiment_step",
                        ),
                        minimum=0,
                    )
                    == step
                )
            ]

            if len(candidates) != 1:
                raise FeedbackContextError(
                    "context requires exactly "
                    "one controlled-stimulus "
                    "exposure for each released "
                    "item in the feedback window"
                )

            event = candidates[0]

            expected_event_ids.add(
                _nonempty(
                    "controlled event_id",
                    _field(
                        event,
                        "event_id",
                    ),
                )
            )

            if (
                _nonempty(
                    "controlled episode_id",
                    _field(
                        event,
                        "episode_id",
                    ),
                )
                != episode_id
            ):
                raise FeedbackContextError(
                    "controlled exposure "
                    "episode mismatch"
                )

            release_date = (
                self._checkpoint_date(
                    period
                )
            )

            if (
                _iso_date(
                    "controlled exposure date",
                    _field(
                        event,
                        "agent_world_date",
                    ),
                )
                != release_date
            ):
                raise FeedbackContextError(
                    "controlled exposure "
                    "date mismatch"
                )

            try:
                visible = (
                    engine.participant_payload(
                        step,
                        moment=moment,
                    )
                )
            except Exception as exc:
                raise FeedbackContextError(
                    "controlled participant "
                    "payload reconstruction failed"
                ) from exc

            try:
                raw = next(
                    payload
                    for payload in visible
                    if (
                        payload.get(
                            "stimulus_id"
                        )
                        == item_id
                    )
                )
            except StopIteration as exc:
                raise FeedbackContextError(
                    "released controlled item "
                    "missing from participant payload"
                ) from exc

            try:
                decorated = dict(
                    self
                    .controlled_payload_decorator(
                        raw
                    )
                )
            except Exception as exc:
                raise FeedbackContextError(
                    "controlled source-cue "
                    "projection failed"
                ) from exc

            if (
                set(decorated)
                != _DECORATED_STIMULUS_KEYS
            ):
                raise FeedbackContextError(
                    "controlled participant-safe "
                    "projection fields changed"
                )

            headline = _nonempty(
                "controlled headline",
                decorated[
                    "headline"
                ],
            )
            body = _nonempty(
                "controlled body",
                decorated[
                    "body"
                ],
            )
            source_label = _nonempty(
                "controlled source_label",
                decorated[
                    "source_label"
                ],
            )
            source_descriptor = (
                _nonempty(
                    "controlled source_descriptor",
                    decorated[
                        "source_descriptor"
                    ],
                )
            )

            # Controlled experimental information is never silently truncated.
            # If the frozen content exceeds the explicit policy, fail closed.
            if (
                len(headline)
                > self.limits
                .max_controlled_headline_chars
            ):
                raise FeedbackContextError(
                    "controlled headline "
                    "exceeds context bound"
                )

            if (
                len(body)
                > self.limits
                .max_controlled_body_chars
            ):
                raise FeedbackContextError(
                    "controlled body "
                    "exceeds context bound"
                )

            if (
                len(source_label)
                > self.limits
                .max_source_label_chars
            ):
                raise FeedbackContextError(
                    "controlled source label "
                    "exceeds context bound"
                )

            if (
                len(source_descriptor)
                > self.limits
                .max_source_descriptor_chars
            ):
                raise FeedbackContextError(
                    "controlled source descriptor "
                    "exceeds context bound"
                )

            corrects = decorated[
                "corrects_stimulus_id"
            ]

            delivery_payload = {
                "session_id": (
                    session_id
                ),
                "current_date": (
                    release_date
                ),
                "stimulus_id": (
                    str(
                        decorated[
                            "stimulus_id"
                        ]
                    )
                ),
                "kind": (
                    str(
                        decorated[
                            "kind"
                        ]
                    )
                ),
                "headline": headline,
                "body": body,
                "corrects_stimulus_id": (
                    None
                    if corrects is None
                    else str(corrects)
                ),
                "source_label": (
                    source_label
                ),
                "source_descriptor": (
                    source_descriptor
                ),
            }

            if (
                _nonempty(
                    "event stimulus_version",
                    _field(
                        event,
                        "stimulus_version",
                    ),
                )
                != _nonempty(
                    "material_version",
                    getattr(
                        material,
                        "material_version",
                        None,
                    ),
                )
            ):
                raise FeedbackContextError(
                    "controlled stimulus "
                    "version provenance mismatch"
                )

            if (
                _nonempty(
                    "event stimulus_sha256",
                    _field(
                        event,
                        "stimulus_sha256",
                    ),
                )
                != _nonempty(
                    "item content_sha256",
                    getattr(
                        item,
                        "content_sha256",
                        None,
                    ),
                )
            ):
                raise FeedbackContextError(
                    "controlled stimulus "
                    "content hash provenance mismatch"
                )

            if (
                _nonempty(
                    "event source_cue",
                    _field(
                        event,
                        "source_cue",
                    ),
                )
                != source_label
            ):
                raise FeedbackContextError(
                    "controlled stimulus "
                    "source cue provenance mismatch"
                )

            if (
                _nonempty(
                    "controlled payload_digest",
                    _field(
                        event,
                        "payload_digest",
                    ),
                )
                != sha256_json(
                    delivery_payload
                )
            ):
                raise FeedbackContextError(
                    "controlled stimulus "
                    "payload digest mismatch"
                )

            # Only participant-safe qualitative fields survive.
            # Internal kind/ids/correction links are deliberately stripped.
            output.append(
                {
                    "release_period": (
                        period
                    ),
                    "release_date": (
                        release_date
                    ),
                    "within_period_sequence": (
                        _CONTROLLED_WITHIN_PERIOD_SEQUENCE
                    ),
                    "headline": (
                        headline
                    ),
                    "body": body,
                    "source_label": (
                        source_label
                    ),
                    "source_descriptor": (
                        source_descriptor
                    ),
                }
            )

        # Reject any unexpected controlled exposure falling inside this window.
        for event in controlled_events:
            step = _strict_int(
                "controlled event step",
                _field(
                    event,
                    "experiment_step",
                ),
                minimum=0,
            )
            period = step + 1

            if (
                start_period
                <= period
                <= end_period
            ):
                event_id = _nonempty(
                    "controlled event_id",
                    _field(
                        event,
                        "event_id",
                    ),
                )

                if (
                    event_id
                    not in expected_event_ids
                ):
                    raise FeedbackContextError(
                        "unexpected controlled "
                        "stimulus exposure exists "
                        "inside feedback window"
                    )

        return output

    def _participant_reflections(
        self,
        *,
        session_id: str,
        kind: FeedbackKind,
        start_period: int,
        end_period: int,
    ) -> tuple[
        list[dict[str, object]],
        dict[str, object],
    ]:
        try:
            rows = tuple(
                self.judgements.list_for_session(
                    session_id
                )
            )
        except Exception as exc:
            raise FeedbackContextError(
                "judgement history read failed"
            ) from exc

        expected_events = (
            _EXPECTED_JUDGEMENTS[
                kind
            ]
        )

        selected: list[
            tuple[
                tuple[int, str, str],
                dict[str, object],
                str,
            ]
        ] = []

        observed: set[str] = set()

        total_evidence_omitted = 0
        truncated_rationales = 0
        truncated_evidence_values = 0

        for row in rows:
            if (
                _nonempty(
                    "judgement session_id",
                    _field(
                        row,
                        "session_id",
                    ),
                )
                != session_id
            ):
                raise FeedbackContextError(
                    "judgement reader returned "
                    "another session"
                )

            persisted_step = (
                _strict_int(
                    "judgement step",
                    _field(
                        row,
                        "experiment_step",
                    ),
                    minimum=0,
                )
            )

            period = (
                persisted_step + 1
            )

            # Do not inspect future qualitative participant content.
            if period > end_period:
                continue

            event_name = _nonempty(
                "judgement_event",
                _field(
                    row,
                    "judgement_event",
                ),
            )

            try:
                spec = (
                    self.contract
                    .judgement_spec(
                        event_name
                    )
                )
            except Exception as exc:
                raise FeedbackContextError(
                    "unknown formal "
                    "judgement event"
                ) from exc

            expected_step = (
                _strict_int(
                    "judgement spec step",
                    _field(
                        spec,
                        "experiment_step",
                    ),
                    minimum=0,
                )
            )

            expected_date = (
                _iso_date(
                    "judgement spec date",
                    _field(
                        spec,
                        "agent_world_date",
                    ),
                )
            )

            if (
                expected_step
                != persisted_step
                or _iso_date(
                    "judgement date",
                    _field(
                        row,
                        "agent_world_date",
                    ),
                )
                != expected_date
            ):
                raise FeedbackContextError(
                    "persisted judgement "
                    "disagrees with frozen protocol"
                )

            if event_name not in (
                expected_events
            ):
                continue

            if not (
                start_period
                <= period
                <= end_period
            ):
                raise FeedbackContextError(
                    "required judgement "
                    "falls outside context window"
                )

            if event_name in observed:
                raise FeedbackContextError(
                    "duplicate formal "
                    "judgement event"
                )

            observed.add(
                event_name
            )

            if (
                _nonempty(
                    "judgement stock_id",
                    _field(
                        row,
                        "stock_id",
                    ),
                )
                != self.target_stock_id
            ):
                raise FeedbackContextError(
                    "judgement target "
                    "stock mismatch"
                )

            action = _nonempty(
                "judgement action",
                _field(
                    row,
                    "action",
                ),
            ).upper()

            if action not in {
                "BUY",
                "HOLD",
                "SELL",
            }:
                raise FeedbackContextError(
                    "unsupported judgement action"
                )

            confidence = _finite(
                "judgement confidence",
                _field(
                    row,
                    "confidence",
                ),
                minimum=0.0,
                maximum=100.0,
            )

            evidence = _json_evidence(
                _field(
                    row,
                    "evidence_sources",
                )
            )

            included_evidence = (
                evidence[
                    : self.limits
                    .max_evidence_sources
                ]
            )

            total_evidence_omitted += (
                len(evidence)
                - len(
                    included_evidence
                )
            )

            bounded_evidence: list[
                str
            ] = []

            for value in (
                included_evidence
            ):
                bounded, truncated = (
                    _bounded_text(
                        value,
                        name=(
                            "evidence source"
                        ),
                        max_chars=(
                            self.limits
                            .max_evidence_source_chars
                        ),
                        allow_empty=True,
                    )
                )

                if truncated:
                    truncated_evidence_values += 1

                bounded_evidence.append(
                    bounded
                )

            rationale_raw = _field(
                row,
                "rationale",
            )

            rationale: str | None
            rationale_truncated = False

            if rationale_raw is None:
                rationale = None
            else:
                (
                    rationale,
                    rationale_truncated,
                ) = _bounded_text(
                    rationale_raw,
                    name="participant rationale",
                    max_chars=(
                        self.limits
                        .max_rationale_chars
                    ),
                    allow_empty=True,
                )

            if rationale_truncated:
                truncated_rationales += 1

            submitted_at = str(
                _field(
                    row,
                    "submitted_at",
                )
            )

            participant_safe = {
                "period_number": (
                    period
                ),
                "date": expected_date,
                "within_period_sequence": (
                    _ASSESSMENT_WITHIN_PERIOD_SEQUENCE[
                        event_name
                    ]
                ),
                "action": action,
                "confidence": (
                    confidence
                ),
                "evidence_sources_selected": (
                    bounded_evidence
                ),
                "evidence_sources_omitted": (
                    len(evidence)
                    - len(
                        included_evidence
                    )
                ),
                "rationale": rationale,
                "rationale_truncated": (
                    rationale_truncated
                ),
            }

            selected.append(
                (
                    (
                        period,
                        submitted_at,
                        event_name,
                    ),
                    participant_safe,
                    event_name,
                )
            )

        if (
            observed
            != set(
                expected_events
            )
        ):
            raise FeedbackContextError(
                "required formal judgement "
                "history is incomplete"
            )

        selected.sort(
            key=lambda item: item[0]
        )

        return (
            [
                item[1]
                for item in selected
            ],
            {
                "participant_reflections_included": (
                    len(selected)
                ),
                "rationales_truncated": (
                    truncated_rationales
                ),
                "evidence_values_truncated": (
                    truncated_evidence_values
                ),
                "evidence_values_omitted": (
                    total_evidence_omitted
                ),
            },
        )

    def _prior_context(
        self,
        *,
        session_id: str,
        kind: FeedbackKind,
    ) -> Mapping[
        str,
        object,
    ] | None:
        if kind is not FeedbackKind.F2:
            return None

        prior = self._statistics(
            session_id,
            FeedbackKind.F1,
        )

        start, end = (
            self._validated_window(
                prior,
                FeedbackKind.F1,
            )
        )

        required_sections = (
            "judgement_metrics",
            "confidence_metrics",
            "trading_metrics",
            "judgement_action_metrics",
            "portfolio_metrics",
        )

        compact: dict[
            str,
            object,
        ] = {
            "earlier_window": {
                "start_period": start,
                "end_period": end,
            }
        }

        for section in required_sections:
            value = prior.get(
                section
            )

            if not isinstance(
                value,
                Mapping,
            ):
                raise FeedbackContextError(
                    "prior deterministic "
                    f"statistics missing "
                    f"{section}"
                )

            compact[
                section
            ] = dict(value)

        _validate_no_forbidden_keys(
            compact,
            path="$.prior_context",
        )

        return compact
