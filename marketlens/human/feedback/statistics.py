"""Deterministic quantitative contract for MarketLens feedback."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping, Sequence


STATISTICS_VERSION = "marketlens-feedback-statistics-v1"

JUDGEMENT_ACTIONS = frozenset(
    {"BUY", "HOLD", "SELL"}
)

TRADE_ACTIONS = frozenset(
    {"BUY", "SELL"}
)


def _require_int(
    name: str,
    value: object,
    *,
    minimum: int | None = None,
) -> int:
    """Require a genuine integer without silent coercion."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"{name} must be an integer"
        )

    if minimum is not None and value < minimum:
        raise ValueError(
            f"{name} must be >= {minimum}"
        )

    return value


def _require_finite_number(
    name: str,
    value: object,
    *,
    minimum: float | None = None,
    strictly_positive: bool = False,
) -> float:
    """Require a finite Python numeric value without string/bool coercion."""

    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise ValueError(
            f"{name} must be a finite number"
        )

    number = float(value)

    if not math.isfinite(number):
        raise ValueError(
            f"{name} must be a finite number"
        )

    if strictly_positive and number <= 0:
        raise ValueError(
            f"{name} must be positive"
        )

    if minimum is not None and number < minimum:
        raise ValueError(
            f"{name} must be >= {minimum}"
        )

    return number


@dataclass(frozen=True, slots=True)
class JudgementObservation:
    period_number: int
    action: str
    confidence: float


@dataclass(frozen=True, slots=True)
class TradeObservation:
    period_number: int
    action: str


@dataclass(frozen=True, slots=True)
class AssessmentActionLink:
    """One assessment selected for comparison with period behaviour.

    Adapter policy will select the final formal judgement before the
    corresponding trading window:

        P1  -> J1
        P8  -> J3
        P15 -> J4

    The statistics layer does not inspect internal J labels itself.
    """

    period_number: int
    action: str


@dataclass(frozen=True, slots=True)
class FeedbackStatistics:
    statistics_version: str

    window: Mapping[str, int]

    market_metrics: Mapping[str, float]

    judgement_metrics: Mapping[str, object]
    confidence_metrics: Mapping[str, float]

    trading_metrics: Mapping[str, object]
    judgement_action_metrics: Mapping[str, int]

    portfolio_metrics: Mapping[str, float]

    information_metrics: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _check_period(
    period: int,
    start_period: int,
    end_period: int,
) -> None:

    if (
        period < start_period
        or period > end_period
    ):
        raise ValueError(
            f"period {period} is outside "
            f"feedback window "
            f"{start_period}..{end_period}"
        )


def _trade_directions_by_period(
    trades: Sequence[TradeObservation],
) -> dict[int, str]:
    """Return BUY, SELL or MIXED at period level.

    Multiple transactions are preserved as transactions elsewhere.
    This function only creates a neutral period-level description.

    No net-notional direction is invented.
    """

    grouped: dict[int, set[str]] = {}

    for trade in trades:

        action = trade.action.upper()

        if action not in TRADE_ACTIONS:
            raise ValueError(
                "unsupported settled "
                f"trade action: {trade.action!r}"
            )

        grouped.setdefault(
            trade.period_number,
            set(),
        ).add(action)

    result: dict[int, str] = {}

    for period, actions in grouped.items():

        if actions == {"BUY"}:
            result[period] = "BUY"

        elif actions == {"SELL"}:
            result[period] = "SELL"

        else:
            result[period] = "MIXED"

    return result


def _build_judgement_action_metrics(
    *,
    links: Sequence[AssessmentActionLink],
    trade_directions: Mapping[int, str],
    start_period: int,
    end_period: int,
) -> dict[str, int]:
    """Describe, but never score, judgement/action relationships."""

    same_direction = 0
    opposite_direction = 0
    no_trade = 0
    hold_with_trade = 0
    mixed_trading = 0

    seen_periods: set[int] = set()

    for link in links:

        link_period = _require_int(
            "assessment-action period_number",
            link.period_number,
            minimum=1,
        )

        _check_period(
            link_period,
            start_period,
            end_period,
        )

        if link_period in seen_periods:
            raise ValueError(
                "only one behaviour-linked "
                "assessment is allowed per period"
            )

        seen_periods.add(
            link_period
        )

        judgement = link.action.upper()

        if judgement not in JUDGEMENT_ACTIONS:
            raise ValueError(
                "unsupported judgement "
                f"action: {link.action!r}"
            )

        trading = trade_directions.get(
            link_period
        )

        if trading is None:
            no_trade += 1
            continue

        if trading == "MIXED":
            mixed_trading += 1
            continue

        if judgement == "HOLD":
            hold_with_trade += 1
            continue

        if judgement == trading:
            same_direction += 1
        else:
            opposite_direction += 1

    return {
        "linked_periods": len(links),
        "same_direction_actions": (
            same_direction
        ),
        "opposite_direction_actions": (
            opposite_direction
        ),
        "no_trade": no_trade,
        "hold_with_trade": hold_with_trade,
        "mixed_trading": mixed_trading,
    }


def build_feedback_statistics(
    *,
    start_period: int,
    end_period: int,

    market_price_start: float,
    market_price_end: float,

    judgements: Sequence[
        JudgementObservation
    ],

    eligible_trading_periods: Sequence[int],

    trades: Sequence[
        TradeObservation
    ],

    behaviour_linked_assessments: Sequence[
        AssessmentActionLink
    ],

    portfolio_start_value: float,
    portfolio_end_value: float,

    news_items_available: int,
    community_posts_available: int,

    source_label_counts: (
        Mapping[str, int] | None
    ) = None,
) -> FeedbackStatistics:

    start_period = _require_int(
        "start_period",
        start_period,
        minimum=1,
    )

    end_period = _require_int(
        "end_period",
        end_period,
        minimum=1,
    )

    if end_period < start_period:
        raise ValueError(
            "feedback window must use "
            "ascending positive period numbers"
        )

    market_price_start = _require_finite_number(
        "market_price_start",
        market_price_start,
        strictly_positive=True,
    )

    market_price_end = _require_finite_number(
        "market_price_end",
        market_price_end,
        strictly_positive=True,
    )

    portfolio_start_value = _require_finite_number(
        "portfolio_start_value",
        portfolio_start_value,
        minimum=0.0,
    )

    portfolio_end_value = _require_finite_number(
        "portfolio_end_value",
        portfolio_end_value,
        minimum=0.0,
    )

    news_items_available = _require_int(
        "news_items_available",
        news_items_available,
        minimum=0,
    )

    community_posts_available = _require_int(
        "community_posts_available",
        community_posts_available,
        minimum=0,
    )

    if not judgements:
        raise ValueError(
            "at least one formal judgement "
            "is required"
        )

    normalized_judgements: list[
        JudgementObservation
    ] = []

    previous_period: int | None = None

    for judgement in judgements:

        judgement_period = _require_int(
            "judgement period_number",
            judgement.period_number,
            minimum=1,
        )

        _check_period(
            judgement_period,
            start_period,
            end_period,
        )

        if (
            previous_period is not None
            and judgement_period
            < previous_period
        ):
            raise ValueError(
                "judgements must be supplied "
                "in chronological order"
            )

        previous_period = judgement_period

        action = judgement.action.upper()

        if action not in JUDGEMENT_ACTIONS:
            raise ValueError(
                "unsupported judgement "
                f"action: {judgement.action!r}"
            )

        confidence = _require_finite_number(
            "confidence",
            judgement.confidence,
            minimum=0.0,
        )

        if confidence > 100:
            raise ValueError(
                "confidence must be "
                "between 0 and 100"
            )

        normalized_judgements.append(
            JudgementObservation(
                period_number=judgement_period,
                action=action,
                confidence=confidence,
            )
        )

    eligible = tuple(
        _require_int(
            "eligible trading period",
            period,
            minimum=1,
        )
        for period
        in eligible_trading_periods
    )

    if len(set(eligible)) != len(eligible):
        raise ValueError(
            "eligible trading periods "
            "must be unique"
        )

    for period in eligible:
        _check_period(
            period,
            start_period,
            end_period,
        )

    eligible_set = set(eligible)

    normalized_trades: list[
        TradeObservation
    ] = []

    for trade in trades:

        trade_period = _require_int(
            "trade period_number",
            trade.period_number,
            minimum=1,
        )

        _check_period(
            trade_period,
            start_period,
            end_period,
        )

        if trade_period not in eligible_set:
            raise ValueError(
                "settled trade period must "
                "be trading-eligible"
            )

        action = trade.action.upper()

        if action not in TRADE_ACTIONS:
            raise ValueError(
                "unsupported settled "
                f"trade action: {trade.action!r}"
            )

        normalized_trades.append(
            TradeObservation(
                period_number=trade_period,
                action=action,
            )
        )

    trade_directions = (
        _trade_directions_by_period(
            normalized_trades
        )
    )

    eligible_count = len(eligible)

    trade_period_count = len(
        trade_directions
    )

    no_trade_period_count = (
        eligible_count
        - trade_period_count
    )

    if no_trade_period_count < 0:
        raise ValueError(
            "trade-period count exceeds "
            "eligible periods"
        )

    buy_count = sum(
        1
        for trade in normalized_trades
        if trade.action == "BUY"
    )

    sell_count = sum(
        1
        for trade in normalized_trades
        if trade.action == "SELL"
    )

    revision_count = sum(
        1
        for previous, current
        in zip(
            normalized_judgements,
            normalized_judgements[1:],
        )
        if previous.action
        != current.action
    )

    first = normalized_judgements[0]
    latest = normalized_judgements[-1]

    price_change_absolute = (
        float(market_price_end)
        - float(market_price_start)
    )

    price_change_pct = (
        price_change_absolute
        / float(market_price_start)
        * 100.0
    )

    labels = dict(
        source_label_counts or {}
    )

    for label, count in labels.items():

        if (
            not isinstance(label, str)
            or not label.strip()
        ):
            raise ValueError(
                "source labels must be "
                "non-empty strings"
            )

        _require_int(
            "source-label count",
            count,
            minimum=0,
        )

    return FeedbackStatistics(

        statistics_version=(
            STATISTICS_VERSION
        ),

        window={
            "start_period": start_period,
            "end_period": end_period,
            "periods_reviewed": (
                end_period
                - start_period
                + 1
            ),
        },

        market_metrics={
            "price_start": float(
                market_price_start
            ),
            "price_end": float(
                market_price_end
            ),
            "price_change_absolute": (
                price_change_absolute
            ),
            "price_change_pct": (
                price_change_pct
            ),
        },

        judgement_metrics={
            "first_assessment": (
                first.action
            ),
            "latest_assessment": (
                latest.action
            ),
            "revision_count": (
                revision_count
            ),
        },

        confidence_metrics={
            "first": first.confidence,
            "latest": latest.confidence,
            "change_points": (
                latest.confidence
                - first.confidence
            ),
        },

        trading_metrics={
            "eligible_periods": (
                eligible_count
            ),
            "trade_periods": (
                trade_period_count
            ),
            "no_trade_periods": (
                no_trade_period_count
            ),
            "transaction_count": len(
                normalized_trades
            ),
            "buy_actions": buy_count,
            "sell_actions": sell_count,
            "trading_activity_pct": (
                None
                if eligible_count == 0
                else (
                    trade_period_count
                    / eligible_count
                    * 100.0
                )
            ),
        },

        judgement_action_metrics=(
            _build_judgement_action_metrics(
                links=(
                    behaviour_linked_assessments
                ),
                trade_directions=(
                    trade_directions
                ),
                start_period=start_period,
                end_period=end_period,
            )
        ),

        portfolio_metrics={
            "starting_value": float(
                portfolio_start_value
            ),
            "ending_value": float(
                portfolio_end_value
            ),
        },

        information_metrics={
            "news_items_available": int(
                news_items_available
            ),
            "community_posts_available": int(
                community_posts_available
            ),
            "source_label_counts": labels,
        },
    )
