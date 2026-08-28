from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from marketlens.human.feedback import (
    CONTEXT_PACK_VERSION,
    ContextLimits,
    FeedbackContextBuilder,
    FeedbackContextError,
    FeedbackKind,
)
from marketlens.human.schemas import (
    ParticipantBackgroundRead,
)
from marketlens.stimulus.manifest import (
    sha256_json,
)
from marketlens.stimulus.schema import (
    FormalUseStatus,
)


DATES = (
    "2023-06-19",
    "2023-06-20",
    "2023-06-21",
    "2023-06-26",
    "2023-06-27",
    "2023-06-28",
    "2023-06-29",
    "2023-06-30",
    "2023-07-03",
    "2023-07-04",
    "2023-07-05",
    "2023-07-06",
    "2023-07-07",
    "2023-07-10",
    "2023-07-11",
)


SPECS = {
    "J0": (0, DATES[0]),
    "J1": (0, DATES[0]),
    "J2": (7, DATES[7]),
    "J3": (7, DATES[7]),
    "J4": (14, DATES[14]),
}


class FakeStats:
    def __init__(self, payload):
        self.payload = payload

    def to_dict(self):
        return deepcopy(
            self.payload
        )


def _statistics_payload(
    start_period,
    end_period,
):
    return {
        "statistics_version": (
            "marketlens-feedback-statistics-v1"
        ),
        "window": {
            "start_period": (
                start_period
            ),
            "end_period": (
                end_period
            ),
            "periods_reviewed": (
                end_period
                - start_period
                + 1
            ),
        },
        "market_metrics": {
            "price_start": 10.0,
            "price_end": 12.0,
            "price_change_absolute": 2.0,
            "price_change_pct": 20.0,
        },
        "judgement_metrics": {
            "first_assessment": "HOLD",
            "latest_assessment": "SELL",
            "revision_count": 1,
        },
        "confidence_metrics": {
            "first": 70.0,
            "latest": 50.0,
            "change_points": -20.0,
        },
        "trading_metrics": {
            "eligible_periods": (
                end_period
                - start_period
                + 1
            ),
            "trade_periods": 1,
            "no_trade_periods": (
                end_period
                - start_period
            ),
            "buy_actions": 1,
            "sell_actions": 0,
            "transaction_count": 1,
            "trading_activity_pct": 25.0,
        },
        "judgement_action_metrics": {
            "linked_periods": 1,
            "same_direction_actions": 0,
            "opposite_direction_actions": 1,
            "no_trade": 0,
            "hold_with_trade": 0,
            "mixed_trading": 0,
        },
        "portfolio_metrics": {
            "starting_value": 1000.0,
            "ending_value": 1010.0,
            "change_absolute": 10.0,
            "change_pct": 1.0,
        },
        "information_metrics": {
            "news_items_available": (
                end_period
                - start_period
                + 1
            ),
            "community_posts_available": (
                end_period
                - start_period
                + 1
            ),
            "source_label_counts": {
                "Individual Investor": 1,
            },
        },
    }


class FakeStatisticsSource:
    def __init__(self):
        self.payloads = {
            FeedbackKind.F1: (
                _statistics_payload(
                    1,
                    4,
                )
            ),
            FeedbackKind.F2: (
                _statistics_payload(
                    5,
                    11,
                )
            ),
            FeedbackKind.FINAL: (
                _statistics_payload(
                    1,
                    15,
                )
            ),
        }

    def build(self, session_id, kind):
        return FakeStats(
            self.payloads[kind]
        )


class FakeListStore:
    def __init__(self, rows):
        self.rows = rows

    def list_for_session(
        self,
        session_id,
    ):
        return tuple(
            self.rows
        )


class FakeAssignmentStore:
    def get(self, session_id):
        return SimpleNamespace(
            episode_id="episode-test"
        )


class FakeContract:
    def checkpoint_date(
        self,
        step,
    ):
        return DATES[step]

    def judgement_spec(
        self,
        event,
    ):
        step, day = SPECS[event]

        return SimpleNamespace(
            judgement_event=event,
            experiment_step=step,
            agent_world_date=day,
        )


class FakeProjection:
    def __init__(
        self,
        payloads,
    ):
        self.episode = SimpleNamespace(
            episode_id="episode-test"
        )
        self.payloads = payloads

    def project(
        self,
        *,
        current_date,
    ):
        return deepcopy(
            self.payloads[
                current_date
            ]
        )


def _background_payloads():
    payloads = {}

    for index, day in enumerate(
        DATES,
        start=1,
    ):
        posts = []

        for post_id in range(
            index,
            0,
            -1,
        ):
            posts.append(
                {
                    "post_id": post_id,
                    "author_id": (
                        f"user-{post_id}"
                    ),
                    "source_label": (
                        "Individual Investor"
                        if post_id % 2
                        else "Market Blogger"
                    ),
                    "display_text": (
                        f"community-{post_id}"
                    ),
                    "created_at": (
                        f"{DATES[post_id - 1]} "
                        "12:00:00"
                    ),
                }
            )

        payloads[day] = {
            "current_date": day,
            "natural_news": [
                f"news-{index}"
            ],
            "forum_posts": posts,
        }

    return payloads


def _judgements():
    return [
        {
            "session_id": "session-test",
            "judgement_event": "J0",
            "experiment_step": 0,
            "agent_world_date": DATES[0],
            "stock_id": "TLEI",
            "action": "HOLD",
            "confidence": 70.0,
            "evidence_sources": json.dumps(
                [
                    "Market information",
                    "Community discussion",
                ]
            ),
            "rationale": (
                "I was uncertain about "
                "the available information."
            ),
            "submitted_at": (
                "2023-06-19T10:00:00+00:00"
            ),
        },
        {
            "session_id": "session-test",
            "judgement_event": "J1",
            "experiment_step": 0,
            "agent_world_date": DATES[0],
            "stock_id": "TLEI",
            "action": "SELL",
            "confidence": 60.0,
            "evidence_sources": json.dumps(
                ["New market information"]
            ),
            "rationale": (
                "I changed my judgement "
                "after reviewing the new information."
            ),
            "submitted_at": (
                "2023-06-19T10:05:00+00:00"
            ),
        },
        {
            "session_id": "session-test",
            "judgement_event": "J2",
            "experiment_step": 7,
            "agent_world_date": DATES[7],
            "stock_id": "TLEI",
            "action": "BUY",
            "confidence": 55.0,
            "evidence_sources": json.dumps(
                ["Community discussion"]
            ),
            "rationale": (
                "I was still uncertain."
            ),
            "submitted_at": (
                "2023-06-30T10:00:00+00:00"
            ),
        },
        {
            "session_id": "session-test",
            "judgement_event": "J3",
            "experiment_step": 7,
            "agent_world_date": DATES[7],
            "stock_id": "TLEI",
            "action": "HOLD",
            "confidence": 50.0,
            "evidence_sources": json.dumps(
                ["Company information"]
            ),
            "rationale": (
                "The later information "
                "increased my uncertainty."
            ),
            "submitted_at": (
                "2023-06-30T10:05:00+00:00"
            ),
        },
        {
            "session_id": "session-test",
            "judgement_event": "J4",
            "experiment_step": 14,
            "agent_world_date": DATES[14],
            "stock_id": "TLEI",
            "action": "SELL",
            "confidence": 45.0,
            "evidence_sources": json.dumps(
                ["Market information"]
            ),
            "rationale": (
                "My later judgement "
                "remained cautious."
            ),
            "submitted_at": (
                "2023-07-11T10:00:00+00:00"
            ),
        },
    ]


def _decorate(raw):
    item = dict(raw)

    if item["stimulus_id"] == "stim-a":
        label = "Market Source"
        descriptor = (
            "Participant-visible market source"
        )
    else:
        label = "Company Source"
        descriptor = (
            "Participant-visible company source"
        )

    return {
        **item,
        "source_label": label,
        "source_descriptor": (
            descriptor
        ),
    }


class FakeStimulusEngine:
    def __init__(self):
        self.misinformation_step = 0
        self.correction_step = 7

        self.material = (
            SimpleNamespace(
                formal_use_status=(
                    FormalUseStatus
                    .FORMAL_FROZEN
                ),
                material_version=(
                    "stimulus-v1"
                ),
                misinformation=(
                    SimpleNamespace(
                        stimulus_id="stim-a",
                        content_sha256=(
                            "a" * 64
                        ),
                    )
                ),
                correction=(
                    SimpleNamespace(
                        stimulus_id="stim-b",
                        content_sha256=(
                            "b" * 64
                        ),
                    )
                ),
            )
        )

        self._mis = {
            "stimulus_id": "stim-a",
            "kind": "rumour",
            "headline": (
                "Market update"
            ),
            "body": (
                "Participant-visible "
                "controlled information A."
            ),
            "corrects_stimulus_id": None,
        }

        self._corr = {
            "stimulus_id": "stim-b",
            "kind": (
                "authoritative_correction"
            ),
            "headline": (
                "Company update"
            ),
            "body": (
                "Participant-visible "
                "controlled information B."
            ),
            "corrects_stimulus_id": (
                "stim-a"
            ),
        }

    def participant_payload(
        self,
        step,
        *,
        moment,
    ):
        if step == 0:
            return (
                deepcopy(
                    self._mis
                ),
            )

        if step == 7:
            return (
                deepcopy(
                    self._mis
                ),
                deepcopy(
                    self._corr
                ),
            )

        raise ValueError(
            "unexpected release step"
        )


def _controlled_delivery(
    *,
    session_id,
    current_date,
    raw,
):
    decorated = _decorate(raw)

    return {
        "session_id": session_id,
        "current_date": current_date,
        "stimulus_id": (
            decorated[
                "stimulus_id"
            ]
        ),
        "kind": decorated["kind"],
        "headline": (
            decorated["headline"]
        ),
        "body": decorated["body"],
        "corrects_stimulus_id": (
            decorated[
                "corrects_stimulus_id"
            ]
        ),
        "source_label": (
            decorated[
                "source_label"
            ]
        ),
        "source_descriptor": (
            decorated[
                "source_descriptor"
            ]
        ),
    }


def _events(
    engine,
):
    payloads = (
        _background_payloads()
    )

    rows = []

    for step, day in enumerate(
        DATES
    ):
        background = (
            ParticipantBackgroundRead(
                session_id="session-test",
                current_date=day,
                natural_news=(
                    payloads[
                        day
                    ]["natural_news"]
                ),
                forum_posts=(
                    payloads[
                        day
                    ]["forum_posts"]
                ),
            )
        )

        rows.append(
            {
                "event_id": (
                    f"background-{step}"
                ),
                "session_id": (
                    "session-test"
                ),
                "episode_id": (
                    "episode-test"
                ),
                "experiment_step": (
                    step
                ),
                "agent_world_date": (
                    day
                ),
                "event_type": (
                    "BACKGROUND_EXPOSED"
                ),
                "payload_digest": (
                    sha256_json(
                        background
                        .model_dump(
                            mode="json"
                        )
                    )
                ),
            }
        )

    mis_delivery = (
        _controlled_delivery(
            session_id="session-test",
            current_date=DATES[0],
            raw=engine._mis,
        )
    )

    corr_delivery = (
        _controlled_delivery(
            session_id="session-test",
            current_date=DATES[7],
            raw=engine._corr,
        )
    )

    rows.extend(
        [
            {
                "event_id": (
                    "controlled-a"
                ),
                "session_id": (
                    "session-test"
                ),
                "episode_id": (
                    "episode-test"
                ),
                "experiment_step": 0,
                "agent_world_date": (
                    DATES[0]
                ),
                "event_type": (
                    "CONTROLLED_STIMULUS_EXPOSED"
                ),
                "stimulus_id": (
                    "stim-a"
                ),
                "stimulus_version": (
                    "stimulus-v1"
                ),
                "stimulus_sha256": (
                    "a" * 64
                ),
                "source_cue": (
                    "Market Source"
                ),
                "payload_digest": (
                    sha256_json(
                        mis_delivery
                    )
                ),
            },
            {
                "event_id": (
                    "controlled-b"
                ),
                "session_id": (
                    "session-test"
                ),
                "episode_id": (
                    "episode-test"
                ),
                "experiment_step": 7,
                "agent_world_date": (
                    DATES[7]
                ),
                "event_type": (
                    "CONTROLLED_STIMULUS_EXPOSED"
                ),
                "stimulus_id": (
                    "stim-b"
                ),
                "stimulus_version": (
                    "stimulus-v1"
                ),
                "stimulus_sha256": (
                    "b" * 64
                ),
                "source_cue": (
                    "Company Source"
                ),
                "payload_digest": (
                    sha256_json(
                        corr_delivery
                    )
                ),
            },
        ]
    )

    return rows


def _limits(
    **changes,
):
    values = {
        "policy_version": (
            "context-policy-test-v1"
        ),
        "max_news_items": 50,
        "max_community_posts": 50,
        "max_news_chars": 1000,
        "max_community_chars": 1000,
        "max_rationale_chars": 2000,
        "max_evidence_sources": 12,
        "max_evidence_source_chars": 300,
        "max_controlled_headline_chars": 500,
        "max_controlled_body_chars": 5000,
        "max_source_label_chars": 200,
        "max_source_descriptor_chars": 500,
    }

    values.update(
        changes
    )

    return ContextLimits(
        **values
    )


def _parts(
    *,
    limits=None,
):
    engine = FakeStimulusEngine()
    backgrounds = (
        _background_payloads()
    )

    return {
        "statistics_source": (
            FakeStatisticsSource()
        ),
        "judgements": FakeListStore(
            _judgements()
        ),
        "events": FakeListStore(
            _events(engine)
        ),
        "assignments": (
            FakeAssignmentStore()
        ),
        "projections": {
            "episode-test": (
                FakeProjection(
                    backgrounds
                )
            )
        },
        "contract": FakeContract(),
        "stimulus_engine": (
            engine
        ),
        "target_stock_id": "TLEI",
        "limits": (
            limits
            or _limits()
        ),
        "controlled_payload_decorator": (
            _decorate
        ),
        "source_cue_freeze_checker": (
            lambda: "ok"
        ),
        "stimulus_material_validator": (
            lambda material: None
        ),
    }


def _builder(
    *,
    limits=None,
):
    return FeedbackContextBuilder(
        **_parts(
            limits=limits
        )
    )


def _all_keys(value):
    keys = set()

    if isinstance(
        value,
        dict,
    ):
        for key, child in value.items():
            keys.add(key)
            keys.update(
                _all_keys(child)
            )

    elif isinstance(
        value,
        list,
    ):
        for child in value:
            keys.update(
                _all_keys(child)
            )

    return keys


def test_f1_builds_participant_safe_recent_context():
    pack = _builder().build(
        "session-test",
        FeedbackKind.F1,
    )

    payload = pack.to_dict()

    assert (
        payload[
            "context_pack_version"
        ]
        == CONTEXT_PACK_VERSION
    )

    assert (
        payload["feedback_kind"]
        == "multi_period_decision_feedback"
    )

    assert payload["window"][
        "start_period"
    ] == 1
    assert payload["window"][
        "end_period"
    ] == 4

    assert len(
        payload[
            "participant_reflections"
        ]
    ) == 2

    controlled = (
        payload[
            "information_environment"
        ][
            "released_controlled_information"
        ]
    )

    assert len(controlled) == 1

    assert set(
        controlled[0]
    ) == {
        "release_period",
        "release_date",
        "within_period_sequence",
        "headline",
        "body",
        "source_label",
        "source_descriptor",
    }

    assert (
        controlled[0][
            "headline"
        ]
        == "Market update"
    )

    forbidden = {
        "stimulus_id",
        "kind",
        "corrects_stimulus_id",
        "judgement_event",
        "experiment_step",
        "episode_id",
        "session_id",
    }

    assert not (
        _all_keys(payload)
        & forbidden
    )

    assert pack.sha256() == (
        pack.sha256()
    )


def test_f1_contains_no_future_period_text():
    payload = (
        _builder()
        .build(
            "session-test",
            FeedbackKind.F1,
        )
        .to_dict()
    )

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
    )

    assert "news-4" in encoded
    assert "news-5" not in encoded
    assert "community-4" in encoded
    assert "community-5" not in encoded


def test_f2_uses_new_window_plus_deterministic_prior_context():
    payload = (
        _builder()
        .build(
            "session-test",
            FeedbackKind.F2,
        )
        .to_dict()
    )

    news = payload[
        "information_environment"
    ]["available_news"]

    assert [
        item["period_number"]
        for item in news
    ] == list(
        range(
            5,
            12,
        )
    )

    community = payload[
        "information_environment"
    ][
        "available_community_content"
    ]

    assert [
        item[
            "period_first_available"
        ]
        for item in community
    ] == list(
        range(
            5,
            12,
        )
    )

    controlled = payload[
        "information_environment"
    ][
        "released_controlled_information"
    ]

    assert len(controlled) == 1
    assert (
        controlled[0][
            "headline"
        ]
        == "Company update"
    )

    prior = payload[
        "prior_context"
    ]

    assert prior is not None
    assert prior[
        "earlier_window"
    ] == {
        "start_period": 1,
        "end_period": 4,
    }

    prior_encoded = json.dumps(
        prior,
        ensure_ascii=False,
    )

    assert "news-1" not in prior_encoded
    assert "community-1" not in prior_encoded
    assert "Market update" not in prior_encoded


def test_final_uses_whole_session_without_prior_llm_text():
    payload = (
        _builder()
        .build(
            "session-test",
            FeedbackKind.FINAL,
        )
        .to_dict()
    )

    assert (
        payload["feedback_kind"]
        == "final_session_summary"
    )

    assert len(
        payload[
            "information_environment"
        ]["available_news"]
    ) == 15

    assert len(
        payload[
            "information_environment"
        ][
            "available_community_content"
        ]
    ) == 15

    assert len(
        payload[
            "information_environment"
        ][
            "released_controlled_information"
        ]
    ) == 2

    assert len(
        payload[
            "participant_reflections"
        ]
    ) == 5

    assert payload[
        "prior_context"
    ] is None


def test_background_digest_mismatch_fails_closed():
    parts = _parts()

    for row in (
        parts["events"].rows
    ):
        if (
            row["event_id"]
            == "background-2"
        ):
            row[
                "payload_digest"
            ] = "0" * 64

    builder = (
        FeedbackContextBuilder(
            **parts
        )
    )

    with pytest.raises(
        FeedbackContextError,
        match="background payload digest",
    ):
        builder.build(
            "session-test",
            FeedbackKind.F1,
        )


def test_controlled_digest_mismatch_fails_closed():
    parts = _parts()

    for row in (
        parts["events"].rows
    ):
        if (
            row["event_id"]
            == "controlled-a"
        ):
            row[
                "payload_digest"
            ] = "0" * 64

    builder = (
        FeedbackContextBuilder(
            **parts
        )
    )

    with pytest.raises(
        FeedbackContextError,
        match="controlled stimulus payload digest",
    ):
        builder.build(
            "session-test",
            FeedbackKind.F1,
        )


def test_missing_controlled_exposure_fails_closed():
    parts = _parts()

    parts["events"].rows = [
        row
        for row in parts[
            "events"
        ].rows
        if (
            row["event_id"]
            != "controlled-b"
        )
    ]

    builder = (
        FeedbackContextBuilder(
            **parts
        )
    )

    with pytest.raises(
        FeedbackContextError,
        match="one controlled-stimulus exposure",
    ):
        builder.build(
            "session-test",
            FeedbackKind.F2,
        )


def test_deterministic_bounds_preserve_order_and_report_coverage():
    limits = _limits(
        max_news_items=2,
        max_community_posts=2,
        max_news_chars=4,
        max_community_chars=5,
        max_rationale_chars=6,
        max_evidence_sources=1,
        max_evidence_source_chars=5,
    )

    payload = (
        _builder(
            limits=limits
        )
        .build(
            "session-test",
            FeedbackKind.F1,
        )
        .to_dict()
    )

    news = payload[
        "information_environment"
    ]["available_news"]

    assert len(news) == 2
    assert news[0][
        "period_number"
    ] == 1
    assert news[1][
        "period_number"
    ] == 2
    assert news[0][
        "text"
    ] == "news"
    assert news[0][
        "text_truncated"
    ] is True

    community = payload[
        "information_environment"
    ][
        "available_community_content"
    ]

    assert len(community) == 2
    assert community[0][
        "period_first_available"
    ] == 1
    assert community[1][
        "period_first_available"
    ] == 2

    coverage = payload[
        "context_coverage"
    ]

    assert coverage[
        "news_items_total"
    ] == 4
    assert coverage[
        "news_items_included"
    ] == 2
    assert coverage[
        "news_items_omitted"
    ] == 2

    assert coverage[
        "community_posts_total"
    ] == 4
    assert coverage[
        "community_posts_included"
    ] == 2
    assert coverage[
        "community_posts_omitted"
    ] == 2

    reflection = payload[
        "participant_reflections"
    ][0]

    assert len(
        reflection[
            "evidence_sources_selected"
        ]
    ) == 1

    assert reflection[
        "evidence_sources_omitted"
    ] == 1

    assert reflection[
        "rationale_truncated"
    ] is True


def test_forbidden_statistics_field_is_rejected():
    parts = _parts()

    parts[
        "statistics_source"
    ].payloads[
        FeedbackKind.F1
    ][
        "truth_label"
    ] = "hidden"

    builder = (
        FeedbackContextBuilder(
            **parts
        )
    )

    with pytest.raises(
        FeedbackContextError,
        match="forbidden feedback context field",
    ):
        builder.build(
            "session-test",
            FeedbackKind.F1,
        )


def test_evidence_and_rationale_are_data_not_internal_labels():
    payload = (
        _builder()
        .build(
            "session-test",
            FeedbackKind.F1,
        )
        .to_dict()
    )

    first = payload[
        "participant_reflections"
    ][0]

    assert first[
        "evidence_sources_selected"
    ] == [
        "Market information",
        "Community discussion",
    ]

    assert (
        first["rationale"]
        == "I was uncertain about "
        "the available information."
    )

    keys = _all_keys(
        first
    )

    assert (
        "judgement_event"
        not in keys
    )
    assert (
        "participant_id"
        not in keys
    )


def test_same_period_temporal_sequence_is_explicit():
    f1 = (
        _builder()
        .build(
            "session-test",
            FeedbackKind.F1,
        )
        .to_dict()
    )

    f1_reflections = f1[
        "participant_reflections"
    ]

    assert [
        item["within_period_sequence"]
        for item in f1_reflections
        if item["period_number"] == 1
    ] == [1, 3]

    f1_controlled = f1[
        "information_environment"
    ][
        "released_controlled_information"
    ]

    assert len(f1_controlled) == 1
    assert (
        f1_controlled[0][
            "within_period_sequence"
        ]
        == 2
    )

    f2 = (
        _builder()
        .build(
            "session-test",
            FeedbackKind.F2,
        )
        .to_dict()
    )

    f2_reflections = f2[
        "participant_reflections"
    ]

    assert [
        item["within_period_sequence"]
        for item in f2_reflections
        if item["period_number"] == 8
    ] == [1, 3]

    f2_controlled = f2[
        "information_environment"
    ][
        "released_controlled_information"
    ]

    assert len(f2_controlled) == 1
    assert (
        f2_controlled[0][
            "within_period_sequence"
        ]
        == 2
    )

    final_payload = (
        _builder()
        .build(
            "session-test",
            FeedbackKind.FINAL,
        )
        .to_dict()
    )

    p15 = [
        item
        for item in final_payload[
            "participant_reflections"
        ]
        if item["period_number"] == 15
    ]

    assert len(p15) == 1
    assert (
        p15[0][
            "within_period_sequence"
        ]
        == 1
    )

    # The ordering is exposed without leaking internal J labels.
    encoded = json.dumps(
        f1,
        ensure_ascii=False,
    )

    assert '"J0"' not in encoded
    assert '"J1"' not in encoded
    assert "judgement_event" not in encoded


def test_internal_provenance_field_is_rejected():
    parts = _parts()

    parts[
        "statistics_source"
    ].payloads[
        FeedbackKind.F1
    ][
        "payload_digest"
    ] = "0" * 64

    builder = FeedbackContextBuilder(
        **parts
    )

    with pytest.raises(
        FeedbackContextError,
        match="forbidden feedback context field",
    ):
        builder.build(
            "session-test",
            FeedbackKind.F1,
        )
