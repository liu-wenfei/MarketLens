"""Authoritative deterministic source adapter for participant feedback statistics.

This layer reads only already-authoritative MarketLens participant state and
participant-safe canonical projections. It performs no LLM inference, does not
change experiment state, and does not interpret truth, treatment, or Agent
metadata.

Important semantics:

* round completion is evidence that the participant checkpoint behaviour has
  been locked, including a legitimate no-trade outcome;
* BACKGROUND_EXPOSED proves that the backend prepared and authorised the
  participant-visible background. It is not evidence that the participant
  read, used, believed, or attended to that information;
* historical participant portfolio values are reconstructed from authoritative
  cash/holding transaction continuity and then marked to the canonical
  market-state price for the requested checkpoint. Transaction-level
  portfolio_value_before/after fields are not used as cross-period valuations;
* Community counts use distinct participant-visible post identities. The
  cumulative forum projection is never naively summed across days.
"""

from __future__ import annotations
from marketlens.human.feedback.final_analytics import (
    FinalAnalyticsError,
    build_final_analytics,
)
from marketlens.human.feedback.journey_source import (
    JourneyAuthoritativeSourceAdapter,
    JourneySourceError,
)

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import json
import math
from typing import Any

from marketlens.human.schemas import ParticipantBackgroundRead
from marketlens.stimulus.manifest import sha256_json

from .statistics import (
    AssessmentActionLink,
    FeedbackStatistics,
    JudgementObservation,
    TradeObservation,
    build_feedback_statistics,
)


class FeedbackSourceError(ValueError):
    """Raised when authoritative feedback source data is incomplete or inconsistent."""


class FeedbackKind(StrEnum):
    F1 = "F1"
    F2 = "F2"
    FINAL = "FINAL"


@dataclass(frozen=True, slots=True)
class FeedbackWindow:
    start_period: int
    end_period: int
    lock_through_period: int
    required_judgements: tuple[str, ...]
    linked_judgements: tuple[str, ...]
    forum_baseline_period: int | None


_WINDOWS: Mapping[FeedbackKind, FeedbackWindow] = {
    FeedbackKind.F1: FeedbackWindow(
        start_period=1,
        end_period=4,
        lock_through_period=4,
        required_judgements=("J0", "J1"),
        linked_judgements=("J1",),
        forum_baseline_period=None,
    ),
    FeedbackKind.F2: FeedbackWindow(
        start_period=5,
        end_period=11,
        lock_through_period=11,
        required_judgements=("J2", "J3"),
        linked_judgements=("J3",),
        forum_baseline_period=4,
    ),
    FeedbackKind.FINAL: FeedbackWindow(
        start_period=1,
        end_period=15,
        lock_through_period=15,
        required_judgements=("J0", "J1", "J2", "J3", "J4"),
        linked_judgements=("J1", "J3", "J4"),
        forum_baseline_period=None,
    ),
}

_KNOWN_JUDGEMENTS = frozenset(
    {"J0", "J1", "J2", "J3", "J4"}
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

_PROJECTION_KEYS = frozenset(
    {
        "current_date",
        "natural_news",
        "forum_posts",
    }
)


def _field(value: object, name: str) -> Any:
    if isinstance(value, Mapping):
        if name not in value:
            raise FeedbackSourceError(
                f"authoritative source missing field {name!r}"
            )
        return value[name]

    if not hasattr(value, name):
        raise FeedbackSourceError(
            f"authoritative source missing attribute {name!r}"
        )

    return getattr(value, name)


def _nonempty_string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FeedbackSourceError(
            f"{name} must be a non-empty string"
        )
    return value.strip()


def _strict_int(
    name: str,
    value: object,
    *,
    minimum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FeedbackSourceError(
            f"{name} must be an integer"
        )

    if minimum is not None and value < minimum:
        raise FeedbackSourceError(
            f"{name} must be >= {minimum}"
        )

    return value


def _finite_number(
    name: str,
    value: object,
    *,
    minimum: float | None = None,
) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise FeedbackSourceError(
            f"{name} must be a finite number"
        )

    result = float(value)

    if not math.isfinite(result):
        raise FeedbackSourceError(
            f"{name} must be finite"
        )

    if minimum is not None and result < minimum:
        raise FeedbackSourceError(
            f"{name} must be >= {minimum}"
        )

    return result


def _date_string(name: str, value: object) -> str:
    if type(value) is date:
        return value.isoformat()

    if not isinstance(value, str):
        raise FeedbackSourceError(
            f"{name} must be an ISO date"
        )

    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise FeedbackSourceError(
            f"{name} must be YYYY-MM-DD"
        ) from exc

    return parsed.isoformat()


def _event_type_name(value: object) -> str:
    raw = getattr(value, "value", value)
    return _nonempty_string(
        "participant event type",
        raw,
    )


def _feedback_window(
    kind: FeedbackKind | str,
) -> FeedbackWindow:
    try:
        resolved = (
            kind
            if isinstance(kind, FeedbackKind)
            else FeedbackKind(kind)
        )
    except ValueError as exc:
        raise FeedbackSourceError(
            f"unsupported feedback kind: {kind!r}"
        ) from exc

    return _WINDOWS[resolved]


class FeedbackStatisticsSourceAdapter:
    """Build FeedbackStatistics from authoritative participant-safe sources."""

    def __init__(
        self,
        *,
        assignments: object,
        projections: Mapping[str, object],
        judgements: object,
        portfolios: object,
        rounds: object,
        events: object,
        price_provider: object,
        calendar: object,
        contract: object,
        target_stock_id: str,
    ):
        self.assignments = assignments
        self.projections = dict(projections)
        self.judgements = judgements
        self.portfolios = portfolios
        self.rounds = rounds
        self.events = events
        self.price_provider = price_provider
        self.calendar = calendar
        self.contract = contract
        self.target_stock_id = _nonempty_string(
            "target_stock_id",
            target_stock_id,
        )

    def build(
        self,
        session_id: str,
        kind: FeedbackKind | str,
    ) -> FeedbackStatistics:
        session_id = _nonempty_string(
            "session_id",
            session_id,
        )
        window = _feedback_window(kind)

        episode_id, projection = (
            self._resolve_episode_projection(
                session_id
            )
        )

        self._require_round_lock(
            session_id,
            window,
        )

        self._require_background_exposures(
            session_id=session_id,
            episode_id=episode_id,
            projection=projection,
            window=window,
        )

        judgement_observations, links = (
            self._judgement_inputs(
                session_id=session_id,
                window=window,
            )
        )

        (
            portfolio_start,
            portfolio_end,
            trades,
        ) = self._portfolio_inputs(
            session_id=session_id,
            window=window,
        )

        eligible_periods = (
            self._eligible_trading_periods(
                window
            )
        )

        market_price_start = self._target_price(
            window.start_period
        )
        market_price_end = self._target_price(
            window.end_period
        )

        (
            news_items_available,
            community_posts_available,
            source_label_counts,
        ) = self._information_inputs(
            projection=projection,
            window=window,
        )

        final_only_metrics = None
        if (
            window.start_period == 1
            and window.end_period == 15
        ):
            final_only_metrics = (
                self._final_only_metrics(
                    session_id
                )
            )

        return build_feedback_statistics(
            start_period=window.start_period,
            end_period=window.end_period,
            market_price_start=market_price_start,
            market_price_end=market_price_end,
            judgements=judgement_observations,
            eligible_trading_periods=(
                eligible_periods
            ),
            trades=trades,
            behaviour_linked_assessments=links,
            portfolio_start_value=portfolio_start,
            portfolio_end_value=portfolio_end,
            news_items_available=(
                news_items_available
            ),
            community_posts_available=(
                community_posts_available
            ),
            source_label_counts=(
                source_label_counts
            ),
            final_only_metrics=final_only_metrics,
        )

    def _resolve_episode_projection(
        self,
        session_id: str,
    ) -> tuple[str, object]:
        try:
            assignment = self.assignments.get(
                session_id
            )
        except Exception as exc:
            raise FeedbackSourceError(
                "failed to read authoritative episode assignment"
            ) from exc

        if assignment is None:
            raise FeedbackSourceError(
                "session has no authoritative episode assignment"
            )

        episode_id = _nonempty_string(
            "episode_id",
            _field(assignment, "episode_id"),
        )

        try:
            projection = self.projections[
                episode_id
            ]
        except KeyError as exc:
            raise FeedbackSourceError(
                "assigned canonical episode has no "
                "participant-safe projection"
            ) from exc

        bound_episode = getattr(
            getattr(
                projection,
                "episode",
                None,
            ),
            "episode_id",
            None,
        )

        if bound_episode != episode_id:
            raise FeedbackSourceError(
                "participant projection episode binding "
                "disagrees with authoritative assignment"
            )

        return episode_id, projection

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
            raise FeedbackSourceError(
                f"cannot resolve checkpoint date for "
                f"period {period_number}"
            ) from exc

        return _date_string(
            "checkpoint date",
            raw,
        )

    def _require_round_lock(
        self,
        session_id: str,
        window: FeedbackWindow,
    ) -> None:
        try:
            rows = tuple(
                self.rounds.list_for_session(
                    session_id
                )
            )
        except Exception as exc:
            raise FeedbackSourceError(
                "failed to read authoritative round completions"
            ) from exc

        observed: dict[int, int] = {}

        for row in rows:
            row_session = _nonempty_string(
                "round session_id",
                _field(row, "session_id"),
            )

            if row_session != session_id:
                raise FeedbackSourceError(
                    "round reader returned another session"
                )

            step = _strict_int(
                "round step",
                _field(row, "step"),
                minimum=0,
            )
            observed[step] = (
                observed.get(step, 0) + 1
            )

        for step in range(
            window.lock_through_period
        ):
            count = observed.get(step, 0)

            if count != 1:
                raise FeedbackSourceError(
                    "feedback requires exactly one "
                    f"locked completion for period "
                    f"{step + 1}; observed {count}"
                )

    def _require_background_exposures(
        self,
        *,
        session_id: str,
        episode_id: str,
        projection: object,
        window: FeedbackWindow,
    ) -> None:
        try:
            rows = tuple(
                self.events.list_for_session(
                    session_id
                )
            )
        except Exception as exc:
            raise FeedbackSourceError(
                "failed to read participant exposure ledger"
            ) from exc

        background_by_step: dict[
            int,
            list[object],
        ] = {}

        for row in rows:
            if (
                _event_type_name(
                    _field(row, "event_type")
                )
                != "BACKGROUND_EXPOSED"
            ):
                continue

            step = _strict_int(
                "background exposure step",
                _field(
                    row,
                    "experiment_step",
                ),
                minimum=0,
            )

            background_by_step.setdefault(
                step,
                [],
            ).append(row)

        required_periods = set(
            range(
                window.start_period,
                window.end_period + 1,
            )
        )

        if (
            window.forum_baseline_period
            is not None
        ):
            required_periods.add(
                window.forum_baseline_period
            )

        for period in sorted(
            required_periods
        ):
            step = period - 1
            candidates = background_by_step.get(
                step,
                [],
            )

            if len(candidates) != 1:
                raise FeedbackSourceError(
                    "feedback requires exactly one "
                    "BACKGROUND_EXPOSED record for "
                    f"period {period}; observed "
                    f"{len(candidates)}"
                )

            row = candidates[0]

            if (
                _nonempty_string(
                    "exposure session_id",
                    _field(
                        row,
                        "session_id",
                    ),
                )
                != session_id
            ):
                raise FeedbackSourceError(
                    "background exposure session mismatch"
                )

            if (
                _nonempty_string(
                    "exposure episode_id",
                    _field(
                        row,
                        "episode_id",
                    ),
                )
                != episode_id
            ):
                raise FeedbackSourceError(
                    "background exposure episode mismatch"
                )

            expected_date = (
                self._checkpoint_date(period)
            )

            if (
                _date_string(
                    "background exposure date",
                    _field(
                        row,
                        "agent_world_date",
                    ),
                )
                != expected_date
            ):
                raise FeedbackSourceError(
                    "background exposure date "
                    "disagrees with frozen checkpoint"
                )


            # Reconstruct the exact participant-facing payload using the
            # participant-safe projection, then validate it against the
            # append-only exposure digest created at delivery time.
            payload = self._projection_payload(
                projection=projection,
                period_number=period,
            )

            background = ParticipantBackgroundRead(
                session_id=session_id,
                current_date=expected_date,
                natural_news=payload["natural_news"],
                forum_posts=payload["forum_posts"],
            )

            expected_digest = sha256_json(
                background.model_dump(mode="json")
            )

            stored_digest = _nonempty_string(
                "background exposure payload_digest",
                _field(
                    row,
                    "payload_digest",
                ),
            )

            if stored_digest != expected_digest:
                raise FeedbackSourceError(
                    "background exposure payload digest mismatch; "
                    "participant-safe reconstruction disagrees "
                    "with the append-only exposure record"
                )

    def _judgement_inputs(
        self,
        *,
        session_id: str,
        window: FeedbackWindow,
    ) -> tuple[
        tuple[JudgementObservation, ...],
        tuple[AssessmentActionLink, ...],
    ]:
        try:
            rows = tuple(
                self.judgements.list_for_session(
                    session_id
                )
            )
        except Exception as exc:
            raise FeedbackSourceError(
                "failed to read authoritative judgements"
            ) from exc

        event_rows: dict[
            str,
            object,
        ] = {}

        for row in rows:
            if (
                _nonempty_string(
                    "judgement session_id",
                    _field(row, "session_id"),
                )
                != session_id
            ):
                raise FeedbackSourceError(
                    "judgement reader returned another session"
                )

            event = _nonempty_string(
                "judgement_event",
                _field(
                    row,
                    "judgement_event",
                ),
            )

            if event not in _KNOWN_JUDGEMENTS:
                raise FeedbackSourceError(
                    f"unknown formal judgement event: "
                    f"{event!r}"
                )

            if event in event_rows:
                raise FeedbackSourceError(
                    f"duplicate formal judgement event: "
                    f"{event}"
                )

            event_rows[event] = row

        observations: list[
            JudgementObservation
        ] = []

        linked_by_event: dict[
            str,
            AssessmentActionLink,
        ] = {}

        for event in window.required_judgements:
            try:
                row = event_rows[event]
            except KeyError as exc:
                raise FeedbackSourceError(
                    f"required judgement {event} "
                    "is missing"
                ) from exc

            try:
                spec = (
                    self.contract.judgement_spec(
                        event
                    )
                )
            except Exception as exc:
                raise FeedbackSourceError(
                    f"cannot resolve frozen judgement "
                    f"spec for {event}"
                ) from exc

            expected_step = _strict_int(
                "judgement spec step",
                _field(
                    spec,
                    "experiment_step",
                ),
                minimum=0,
            )
            expected_date = _date_string(
                "judgement spec date",
                _field(
                    spec,
                    "agent_world_date",
                ),
            )

            persisted_step = _strict_int(
                "persisted judgement step",
                _field(
                    row,
                    "experiment_step",
                ),
                minimum=0,
            )
            persisted_date = _date_string(
                "persisted judgement date",
                _field(
                    row,
                    "agent_world_date",
                ),
            )

            if (
                persisted_step != expected_step
                or persisted_date != expected_date
            ):
                raise FeedbackSourceError(
                    f"persisted judgement {event} "
                    "disagrees with frozen protocol"
                )

            if (
                _nonempty_string(
                    "judgement stock_id",
                    _field(row, "stock_id"),
                )
                != self.target_stock_id
            ):
                raise FeedbackSourceError(
                    f"judgement {event} targets "
                    "the wrong stock"
                )

            period = persisted_step + 1

            if not (
                window.start_period
                <= period
                <= window.end_period
            ):
                raise FeedbackSourceError(
                    f"judgement {event} falls outside "
                    "the selected feedback window"
                )

            action = _nonempty_string(
                "judgement action",
                _field(row, "action"),
            ).upper()

            confidence = _finite_number(
                "judgement confidence",
                _field(
                    row,
                    "confidence",
                ),
                minimum=0.0,
            )

            raw_evidence = _field(
                row,
                "evidence_sources",
            )

            if not isinstance(raw_evidence, str):
                raise FeedbackSourceError(
                    "judgement evidence_sources must be persisted JSON text"
                )

            try:
                parsed_evidence = json.loads(raw_evidence)
            except json.JSONDecodeError as exc:
                raise FeedbackSourceError(
                    "judgement evidence_sources is invalid JSON"
                ) from exc

            if (
                not isinstance(parsed_evidence, list)
                or any(
                    not isinstance(item, str)
                    or not item.strip()
                    for item in parsed_evidence
                )
            ):
                raise FeedbackSourceError(
                    "judgement evidence_sources must be a JSON string list"
                )

            observations.append(
                JudgementObservation(
                    period_number=period,
                    action=action,
                    confidence=confidence,
                    evidence_sources=tuple(
                        item.strip()
                        for item in parsed_evidence
                    ),
                )
            )

            if event in window.linked_judgements:
                linked_by_event[event] = (
                    AssessmentActionLink(
                        period_number=period,
                        action=action,
                    )
                )

        links = tuple(
            linked_by_event[event]
            for event in window.linked_judgements
        )

        return tuple(observations), links

    def _transaction_rows(
        self,
        *,
        session_id: str,
        end_step: int,
    ) -> tuple[object, ...]:
        try:
            raw_rows = tuple(
                self.portfolios
                .list_transactions_for_session(
                    session_id
                )
            )
        except Exception as exc:
            raise FeedbackSourceError(
                "failed to read authoritative "
                "participant transactions"
            ) from exc

        selected: list[
            tuple[
                tuple[int, str, str],
                object,
            ]
        ] = []

        for row in raw_rows:
            if (
                _nonempty_string(
                    "transaction session_id",
                    _field(
                        row,
                        "session_id",
                    ),
                )
                != session_id
            ):
                raise FeedbackSourceError(
                    "transaction reader returned "
                    "another session"
                )

            step = _strict_int(
                "transaction step",
                _field(row, "step"),
                minimum=0,
            )

            # Do not allow later-session activity to
            # influence historical F1/F2 reconstruction.
            if step > end_step:
                continue

            submitted_at = _nonempty_string(
                "transaction submitted_at",
                _field(
                    row,
                    "submitted_at",
                ),
            )
            transaction_id = _nonempty_string(
                "transaction_id",
                _field(
                    row,
                    "transaction_id",
                ),
            )

            selected.append(
                (
                    (
                        step,
                        submitted_at,
                        transaction_id,
                    ),
                    row,
                )
            )

        selected.sort(
            key=lambda item: item[0]
        )

        return tuple(
            row
            for _, row in selected
        )

    def _portfolio_inputs(
        self,
        *,
        session_id: str,
        window: FeedbackWindow,
    ) -> tuple[
        float,
        float,
        tuple[TradeObservation, ...],
    ]:
        try:
            portfolio_row = (
                self.portfolios.get_portfolio(
                    session_id
                )
            )
        except Exception as exc:
            raise FeedbackSourceError(
                "failed to read authoritative "
                "participant portfolio"
            ) from exc

        if portfolio_row is None:
            raise FeedbackSourceError(
                "participant portfolio is missing"
            )

        initial_cash = _finite_number(
            "initial_cash",
            _field(
                portfolio_row,
                "initial_cash",
            ),
            minimum=0.0,
        )

        start_step = (
            window.start_period - 1
        )
        end_step = (
            window.end_period - 1
        )

        rows = self._transaction_rows(
            session_id=session_id,
            end_step=end_step,
        )

        by_step: dict[
            int,
            list[object],
        ] = {}

        for row in rows:
            step = _strict_int(
                "transaction step",
                _field(row, "step"),
                minimum=0,
            )
            by_step.setdefault(
                step,
                [],
            ).append(row)

        cash = initial_cash
        positions: dict[str, int] = {}

        start_value: float | None = None
        end_value: float | None = None

        trade_observations: list[
            TradeObservation
        ] = []

        for step in range(
            end_step + 1
        ):
            period = step + 1

            if step == start_step:
                start_value = (
                    self._account_value(
                        cash=cash,
                        positions=positions,
                        period_number=period,
                    )
                )

            for row in by_step.get(
                step,
                (),
            ):
                stock_id = _nonempty_string(
                    "transaction stock_id",
                    _field(
                        row,
                        "stock_id",
                    ),
                )
                action = _nonempty_string(
                    "transaction action",
                    _field(
                        row,
                        "action",
                    ),
                ).upper()

                if action not in {
                    "BUY",
                    "SELL",
                }:
                    raise FeedbackSourceError(
                        "authoritative transaction "
                        f"has unsupported action "
                        f"{action!r}"
                    )

                # A persisted transaction must agree with the frozen
                # checkpoint and the exact canonical settlement source.
                # This validates provenance only; cash/holding state remains
                # authoritative and is not recalculated from the price.
                market_status = self._market_status(
                    period
                )

                trading_enabled = _field(
                    market_status,
                    "participant_trading_enabled",
                )

                if not isinstance(
                    trading_enabled,
                    bool,
                ):
                    raise FeedbackSourceError(
                        "participant_trading_enabled "
                        "must be boolean for transaction provenance"
                    )

                if not trading_enabled:
                    raise FeedbackSourceError(
                        "authoritative transaction exists "
                        "for a non-trading-enabled participant period"
                    )

                expected_price_date = (
                    self._checkpoint_date(
                        period
                    )
                )

                persisted_price_date = _date_string(
                    "transaction price_date",
                    _field(
                        row,
                        "price_date",
                    ),
                )

                if (
                    persisted_price_date
                    != expected_price_date
                ):
                    raise FeedbackSourceError(
                        "transaction price_date disagrees "
                        "with the frozen checkpoint date"
                    )

                current_market_date = _date_string(
                    "transaction current_market_date",
                    _field(
                        market_status,
                        "current_market_date",
                    ),
                )

                if (
                    current_market_date
                    != expected_price_date
                ):
                    raise FeedbackSourceError(
                        "authorised current_market_date "
                        "disagrees with the transaction checkpoint"
                    )

                settlement_price = _finite_number(
                    "transaction settlement_price",
                    _field(
                        row,
                        "settlement_price",
                    ),
                    minimum=0.000000000001,
                )

                try:
                    canonical_record = (
                        self.price_provider.get_close(
                            stock_id,
                            persisted_price_date,
                        )
                    )
                except Exception as exc:
                    raise FeedbackSourceError(
                        "canonical settlement price "
                        "is unavailable for the "
                        "persisted transaction date"
                    ) from exc

                canonical_settlement_price = (
                    _finite_number(
                        "canonical settlement price",
                        _field(
                            canonical_record,
                            "close",
                        ),
                        minimum=0.000000000001,
                    )
                )

                if not math.isclose(
                    settlement_price,
                    canonical_settlement_price,
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                ):
                    raise FeedbackSourceError(
                        "transaction settlement price mismatch; "
                        "persisted settlement_price disagrees "
                        "with the canonical exact-date close"
                    )

                cash_before = _finite_number(
                    "transaction cash_before",
                    _field(
                        row,
                        "cash_before",
                    ),
                    minimum=0.0,
                )
                cash_after = _finite_number(
                    "transaction cash_after",
                    _field(
                        row,
                        "cash_after",
                    ),
                    minimum=0.0,
                )
                holding_before = _strict_int(
                    "transaction holding_before",
                    _field(
                        row,
                        "holding_before",
                    ),
                    minimum=0,
                )
                holding_after = _strict_int(
                    "transaction holding_after",
                    _field(
                        row,
                        "holding_after",
                    ),
                    minimum=0,
                )

                current_holding = (
                    positions.get(
                        stock_id,
                        0,
                    )
                )

                if not math.isclose(
                    cash,
                    cash_before,
                    rel_tol=1e-9,
                    abs_tol=1e-6,
                ):
                    raise FeedbackSourceError(
                        "transaction cash continuity "
                        "mismatch during historical replay"
                    )

                if (
                    current_holding
                    != holding_before
                ):
                    raise FeedbackSourceError(
                        "transaction holding continuity "
                        "mismatch during historical replay"
                    )

                if (
                    action == "BUY"
                    and holding_after
                    <= holding_before
                ):
                    raise FeedbackSourceError(
                        "BUY transaction does not "
                        "increase authoritative holding"
                    )

                if (
                    action == "SELL"
                    and holding_after
                    >= holding_before
                ):
                    raise FeedbackSourceError(
                        "SELL transaction does not "
                        "decrease authoritative holding"
                    )

                cash = cash_after

                if holding_after == 0:
                    positions.pop(
                        stock_id,
                        None,
                    )
                else:
                    positions[
                        stock_id
                    ] = holding_after

                if (
                    window.start_period
                    <= period
                    <= window.end_period
                ):
                    executed_notional = _finite_number(
                        "transaction executed_notional",
                        _field(
                            row,
                            "executed_notional",
                        ),
                        minimum=0.0,
                    )

                    trade_observations.append(
                        TradeObservation(
                            period_number=period,
                            action=action,
                            executed_notional=(
                                executed_notional
                            ),
                        )
                    )

            if step == end_step:
                end_value = (
                    self._account_value(
                        cash=cash,
                        positions=positions,
                        period_number=period,
                    )
                )

        if (
            start_value is None
            or end_value is None
        ):
            raise FeedbackSourceError(
                "failed to reconstruct feedback "
                "portfolio boundary values"
            )

        return (
            start_value,
            end_value,
            tuple(trade_observations),
        )

    def _market_status(
        self,
        period_number: int,
    ) -> object:
        checkpoint_date = (
            self._checkpoint_date(
                period_number
            )
        )

        try:
            return self.calendar.status(
                checkpoint_date
            )
        except Exception as exc:
            raise FeedbackSourceError(
                "cannot resolve authoritative "
                f"market status for period "
                f"{period_number}"
            ) from exc

    def _market_state_date(
        self,
        period_number: int,
    ) -> str:
        status = self._market_status(
            period_number
        )

        return _date_string(
            "market_state_date",
            _field(
                status,
                "market_state_date",
            ),
        )

    def _price(
        self,
        *,
        stock_id: str,
        period_number: int,
    ) -> float:
        market_date = (
            self._market_state_date(
                period_number
            )
        )

        try:
            record = (
                self.price_provider.get_close(
                    stock_id,
                    market_date,
                )
            )
        except Exception as exc:
            raise FeedbackSourceError(
                "canonical close price unavailable "
                f"for {stock_id!r} on "
                f"{market_date}"
            ) from exc

        return _finite_number(
            "canonical close price",
            _field(
                record,
                "close",
            ),
            minimum=0.000000000001,
        )

    def _target_price(
        self,
        period_number: int,
    ) -> float:
        return self._price(
            stock_id=self.target_stock_id,
            period_number=period_number,
        )

    def _account_value(
        self,
        *,
        cash: float,
        positions: Mapping[str, int],
        period_number: int,
    ) -> float:
        total = _finite_number(
            "portfolio cash",
            cash,
            minimum=0.0,
        )

        for stock_id, quantity in sorted(
            positions.items()
        ):
            quantity = _strict_int(
                "portfolio holding quantity",
                quantity,
                minimum=0,
            )

            price = self._price(
                stock_id=stock_id,
                period_number=period_number,
            )
            total += quantity * price

        if not math.isfinite(total):
            raise FeedbackSourceError(
                "historical portfolio valuation "
                "is not finite"
            )

        return total

    def _eligible_trading_periods(
        self,
        window: FeedbackWindow,
    ) -> tuple[int, ...]:
        eligible: list[int] = []

        for period in range(
            window.start_period,
            window.end_period + 1,
        ):
            status = self._market_status(
                period
            )
            raw = _field(
                status,
                "participant_trading_enabled",
            )

            if not isinstance(raw, bool):
                raise FeedbackSourceError(
                    "participant_trading_enabled "
                    "must be boolean"
                )

            if raw:
                eligible.append(period)

        return tuple(eligible)

    def _projection_payload(
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
            raise FeedbackSourceError(
                "participant-safe background "
                f"projection failed for period "
                f"{period_number}"
            ) from exc

        if not isinstance(payload, Mapping):
            raise FeedbackSourceError(
                "participant-safe projection "
                "must return a mapping"
            )

        if set(payload) != _PROJECTION_KEYS:
            raise FeedbackSourceError(
                "participant-safe projection "
                "field allow-list changed"
            )

        projected_date = _date_string(
            "projected current_date",
            payload["current_date"],
        )

        if projected_date != expected_date:
            raise FeedbackSourceError(
                "participant-safe projection "
                "returned the wrong date"
            )

        news = payload["natural_news"]

        if not isinstance(news, list):
            raise FeedbackSourceError(
                "natural_news must be a list"
            )

        for item in news:
            _nonempty_string(
                "participant-visible natural news",
                item,
            )

        forum = payload["forum_posts"]

        if not isinstance(forum, list):
            raise FeedbackSourceError(
                "forum_posts must be a list"
            )

        self._forum_map(forum)

        return payload

    @staticmethod
    def _forum_map(
        posts: list[object],
    ) -> dict[int, str]:
        result: dict[int, str] = {}

        for raw_post in posts:
            if not isinstance(
                raw_post,
                Mapping,
            ):
                raise FeedbackSourceError(
                    "participant forum post "
                    "must be a mapping"
                )

            if set(raw_post) != _FORUM_KEYS:
                raise FeedbackSourceError(
                    "participant forum allow-list "
                    "fields changed"
                )

            post_id = _strict_int(
                "forum post_id",
                raw_post["post_id"],
                minimum=0,
            )
            source_label = _nonempty_string(
                "forum source_label",
                raw_post["source_label"],
            )

            _nonempty_string(
                "forum author_id",
                raw_post["author_id"],
            )
            _nonempty_string(
                "forum display_text",
                raw_post["display_text"],
            )
            _nonempty_string(
                "forum created_at",
                raw_post["created_at"],
            )

            if post_id in result:
                raise FeedbackSourceError(
                    "participant-safe projection "
                    f"contains duplicate post_id "
                    f"{post_id}"
                )

            result[post_id] = (
                source_label
            )

        return result

    def _information_inputs(
        self,
        *,
        projection: object,
        window: FeedbackWindow,
    ) -> tuple[
        int,
        int,
        Mapping[str, int],
    ]:
        seen_labels: dict[
            int,
            str,
        ] = {}

        if (
            window.forum_baseline_period
            is not None
        ):
            baseline = (
                self._projection_payload(
                    projection=projection,
                    period_number=(
                        window
                        .forum_baseline_period
                    ),
                )
            )

            seen_labels.update(
                self._forum_map(
                    baseline["forum_posts"]  # type: ignore[arg-type]
                )
            )

        news_count = 0
        new_post_count = 0
        source_counts: Counter[str] = (
            Counter()
        )

        for period in range(
            window.start_period,
            window.end_period + 1,
        ):
            payload = (
                self._projection_payload(
                    projection=projection,
                    period_number=period,
                )
            )

            news = payload["natural_news"]
            assert isinstance(news, list)
            news_count += len(news)

            current_posts = self._forum_map(
                payload["forum_posts"]  # type: ignore[arg-type]
            )

            for post_id, label in (
                current_posts.items()
            ):
                if post_id in seen_labels:
                    if (
                        seen_labels[post_id]
                        != label
                    ):
                        raise FeedbackSourceError(
                            "participant-visible "
                            "source label changed "
                            f"for post_id {post_id}"
                        )
                    continue

                seen_labels[post_id] = label
                source_counts[label] += 1
                new_post_count += 1

        return (
            news_count,
            new_post_count,
            dict(
                sorted(
                    source_counts.items()
                )
            ),
        )
    def _final_only_metrics(
        self,
        session_id: str,
    ) -> dict[str, object]:
        """Build FINAL-only analytics from authoritative Journey state.

        The Journey remains the source of cross-period portfolio continuity.
        Exact-date canonical prices are reused only to value the prior account
        at each eligible settlement date and the final risky-asset sleeve.
        """

        try:
            journey = JourneyAuthoritativeSourceAdapter(
                judgements=self.judgements,
                portfolios=self.portfolios,
                rounds=self.rounds,
                price_provider=self.price_provider,
                calendar=self.calendar,
                contract=self.contract,
                target_stock_id=self.target_stock_id,
            ).build(session_id)
        except JourneySourceError as exc:
            raise FeedbackSourceError(
                "failed to build authoritative FINAL participant Journey"
            ) from exc

        if tuple(
            period.period_number
            for period in journey.periods
        ) != tuple(range(1, 16)):
            raise FeedbackSourceError(
                "FINAL feedback requires the complete authoritative P1-P15 Journey"
            )

        trades_by_day: dict[str, tuple[float, ...]] = {}
        previous_portfolio_values: dict[str, float] = {}

        previous_cash = journey.initial_cash
        previous_positions = dict(
            journey.initial_holdings
        )

        for period in journey.periods:
            if period.participant_trading_enabled:
                previous_portfolio_values[
                    period.agent_world_date
                ] = self._account_value(
                    cash=previous_cash,
                    positions=previous_positions,
                    period_number=period.period_number,
                )

                trades_by_day[
                    period.agent_world_date
                ] = tuple(
                    transaction.executed_notional
                    for transaction in period.transactions
                )

            previous_cash = period.portfolio_end.cash
            previous_positions = dict(
                period.portfolio_end.holdings
            )

        final_period = journey.periods[-1]
        final_risky_asset_values: dict[str, float] = {}

        for stock_id, quantity in sorted(
            final_period.portfolio_end.holdings.items()
        ):
            quantity = _strict_int(
                "FINAL portfolio holding quantity",
                quantity,
                minimum=0,
            )

            if quantity == 0:
                continue

            final_risky_asset_values[stock_id] = (
                quantity
                * self._price(
                    stock_id=stock_id,
                    period_number=(
                        final_period.period_number
                    ),
                )
            )

        try:
            return build_final_analytics(
                journey=journey,
                trades_by_day=trades_by_day,
                previous_portfolio_values=(
                    previous_portfolio_values
                ),
                final_risky_asset_values=(
                    final_risky_asset_values
                ),
            )
        except FinalAnalyticsError as exc:
            raise FeedbackSourceError(
                "authoritative FINAL analytics are incomplete or inconsistent"
            ) from exc
