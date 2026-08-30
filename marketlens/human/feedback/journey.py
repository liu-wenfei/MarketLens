"""Deterministic participant decision + portfolio journey projection.

This module creates no new source of truth.

It receives already-authoritative participant judgement, transaction,
round-lock and canonical close-price inputs and reconstructs a bounded
period-by-period descriptive journey.

Important semantics:

* one MarketLens participant Period is not called a calendar "day";
* absence of transactions is NO_TRADE only after the period is locked;
* multiple transactions in one period are preserved;
* portfolio value is multi-asset mark-to-market;
* transaction-level portfolio_value_before/after is never used for
  cross-period valuation;
* transaction fees must already be reflected in authoritative cash_after
  and are never subtracted a second time;
* profit/loss is descriptive only and never a correctness judgement.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass

from dataclasses import asdict, dataclass
from datetime import datetime
import math
from types import MappingProxyType
from typing import Mapping, Sequence


JOURNEY_VERSION = "marketlens-participant-decision-journey-v1"

BEHAVIOUR_NO_TRADE = "NO_TRADE"
BEHAVIOUR_BUY_ONLY = "BUY_ONLY"
BEHAVIOUR_SELL_ONLY = "SELL_ONLY"
BEHAVIOUR_MIXED = "MIXED_TRADING"

PNL_GAIN = "GAIN"
PNL_LOSS = "LOSS"
PNL_FLAT = "FLAT"

FEEDBACK_NONE = "NONE"
FEEDBACK_DECISION = "DECISION_FEEDBACK_AFTER_PERIOD"
FEEDBACK_FINAL = "FINAL_SUMMARY_AFTER_PERIOD"

_FEEDBACK_BOUNDARIES = MappingProxyType(
    {
        4: FEEDBACK_DECISION,
        11: FEEDBACK_DECISION,
        15: FEEDBACK_FINAL,
    }
)

_EXPECTED_JUDGEMENT_COUNTS = MappingProxyType(
    {
        1: 2,
        8: 2,
        15: 1,
    }
)

_ALLOWED_JUDGEMENT_ACTIONS = frozenset(
    {"BUY", "HOLD", "SELL"}
)

_ALLOWED_TRADE_ACTIONS = frozenset(
    {"BUY", "SELL"}
)

_EPSILON = 1e-9


class ParticipantDecisionJourneyError(ValueError):
    """Authoritative journey inputs are incomplete or inconsistent."""


def _finite_number(
    name: str,
    value: object,
    *,
    minimum: float | None = None,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise ParticipantDecisionJourneyError(
            f"{name} must be a finite number"
        )

    number = float(value)

    if not math.isfinite(number):
        raise ParticipantDecisionJourneyError(
            f"{name} must be finite"
        )

    if minimum is not None and number < minimum:
        raise ParticipantDecisionJourneyError(
            f"{name} must be >= {minimum}"
        )

    return number


def _strict_int(
    name: str,
    value: object,
    *,
    minimum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParticipantDecisionJourneyError(
            f"{name} must be an integer"
        )

    if minimum is not None and value < minimum:
        raise ParticipantDecisionJourneyError(
            f"{name} must be >= {minimum}"
        )

    return value


def _nonempty(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ParticipantDecisionJourneyError(
            f"{name} must be a non-empty string"
        )

    return value.strip()


def _iso_timestamp(name: str, value: object) -> str:
    raw = _nonempty(name, value)

    try:
        parsed = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ParticipantDecisionJourneyError(
            f"{name} must be an ISO timestamp"
        ) from exc

    if parsed.tzinfo is None:
        raise ParticipantDecisionJourneyError(
            f"{name} must be timezone-aware"
        )

    return raw


def _same_money(left: float, right: float) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=0.0,
        abs_tol=_EPSILON,
    )


@dataclass(frozen=True, slots=True)
class JourneyJudgementInput:
    period_number: int
    stock_id: str
    action: str
    confidence: float
    evidence_sources: tuple[str, ...]
    rationale: str | None
    submitted_at: str


@dataclass(frozen=True, slots=True)
class JourneyTransactionInput:
    transaction_id: str
    period_number: int
    stock_id: str
    action: str

    requested_amount: float | None
    requested_units: float | None

    executed_units: int
    executed_notional: float
    settlement_price: float
    fee: float

    cash_before: float
    cash_after: float

    holding_before: int
    holding_after: int

    submitted_at: str


@dataclass(frozen=True, slots=True)
class JourneyPeriodInput:
    period_number: int
    agent_world_date: str

    market_open: bool
    participant_trading_enabled: bool
    round_locked: bool

    judgements: tuple[JourneyJudgementInput, ...]
    transactions: tuple[JourneyTransactionInput, ...]

    canonical_close_prices: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class JourneyJudgement:
    sequence_within_period: int
    stock_id: str
    action: str
    confidence: float
    evidence_sources: tuple[str, ...]
    rationale: str | None
    submitted_at: str


@dataclass(frozen=True, slots=True)
class JourneyTransaction:
    sequence_within_period: int
    transaction_id: str
    stock_id: str
    action: str

    requested_amount: float | None
    requested_units: float | None

    executed_units: int
    executed_notional: float
    settlement_price: float
    fee: float

    cash_before: float
    cash_after: float

    holding_before: int
    holding_after: int

    submitted_at: str


@dataclass(frozen=True, slots=True)
class JourneyPortfolioSnapshot:
    cash: float
    holdings: Mapping[str, int]
    portfolio_value: float


@dataclass(frozen=True, slots=True)
class JourneyPeriod:
    period_number: int
    agent_world_date: str

    market_open: bool
    participant_trading_enabled: bool

    judgements: tuple[JourneyJudgement, ...]
    transactions: tuple[JourneyTransaction, ...]

    behaviour_summary: str
    holding_changes: Mapping[str, int]

    portfolio_end: JourneyPortfolioSnapshot

    period_pnl: float
    cumulative_pnl: float
    pnl_direction: str

    feedback_boundary: str


@dataclass(frozen=True, slots=True)
class ParticipantDecisionJourney:
    journey_version: str
    target_stock_id: str

    initial_cash: float
    initial_holdings: Mapping[str, int]
    initial_portfolio_value: float

    periods: tuple[JourneyPeriod, ...]

    def to_dict(self) -> dict[str, object]:
        def _plain(value):
            if is_dataclass(value) and not isinstance(value, type):
                return {
                    field.name: _plain(getattr(value, field.name))
                    for field in fields(value)
                }
            if isinstance(value, MappingProxyType):
                return {
                    key: _plain(item)
                    for key, item in value.items()
                }
            if isinstance(value, dict):
                return {
                    key: _plain(item)
                    for key, item in value.items()
                }
            if isinstance(value, tuple):
                return tuple(_plain(item) for item in value)
            if isinstance(value, list):
                return [_plain(item) for item in value]
            return value

        return _plain(self)


def _normalise_judgements(
    *,
    period_number: int,
    target_stock_id: str,
    rows: Sequence[JourneyJudgementInput],
) -> tuple[JourneyJudgement, ...]:
    expected_count = _EXPECTED_JUDGEMENT_COUNTS.get(
        period_number,
        0,
    )

    if len(rows) != expected_count:
        raise ParticipantDecisionJourneyError(
            f"period {period_number} requires "
            f"{expected_count} formal judgement(s), "
            f"got {len(rows)}"
        )

    ordered = sorted(
        rows,
        key=lambda row: (
            _iso_timestamp(
                "judgement submitted_at",
                row.submitted_at,
            ),
            row.action,
        ),
    )

    result: list[JourneyJudgement] = []

    for sequence, row in enumerate(ordered, start=1):
        if row.period_number != period_number:
            raise ParticipantDecisionJourneyError(
                "judgement period_number disagrees with "
                "containing period"
            )

        stock_id = _nonempty(
            "judgement stock_id",
            row.stock_id,
        )

        if stock_id != target_stock_id:
            raise ParticipantDecisionJourneyError(
                "formal judgement target disagrees with "
                "server-owned target stock"
            )

        action = _nonempty(
            "judgement action",
            row.action,
        ).upper()

        if action not in _ALLOWED_JUDGEMENT_ACTIONS:
            raise ParticipantDecisionJourneyError(
                f"unsupported judgement action: {action}"
            )

        confidence = _finite_number(
            "judgement confidence",
            row.confidence,
            minimum=0.0,
        )

        if confidence > 100.0:
            raise ParticipantDecisionJourneyError(
                "judgement confidence must be <= 100"
            )

        evidence: list[str] = []

        for item in row.evidence_sources:
            evidence.append(
                _nonempty(
                    "evidence source",
                    item,
                )
            )

        rationale = row.rationale

        if rationale is not None:
            if not isinstance(rationale, str):
                raise ParticipantDecisionJourneyError(
                    "judgement rationale must be a string or None"
                )
            rationale = rationale.strip() or None

        result.append(
            JourneyJudgement(
                sequence_within_period=sequence,
                stock_id=stock_id,
                action=action,
                confidence=confidence,
                evidence_sources=tuple(evidence),
                rationale=rationale,
                submitted_at=_iso_timestamp(
                    "judgement submitted_at",
                    row.submitted_at,
                ),
            )
        )

    return tuple(result)


def _normalise_transactions(
    *,
    period_number: int,
    rows: Sequence[JourneyTransactionInput],
) -> tuple[JourneyTransactionInput, ...]:
    identities: set[str] = set()

    ordered = sorted(
        rows,
        key=lambda row: (
            _iso_timestamp(
                "transaction submitted_at",
                row.submitted_at,
            ),
            _nonempty(
                "transaction_id",
                row.transaction_id,
            ),
        ),
    )

    for row in ordered:
        if row.period_number != period_number:
            raise ParticipantDecisionJourneyError(
                "transaction period_number disagrees with "
                "containing period"
            )

        transaction_id = _nonempty(
            "transaction_id",
            row.transaction_id,
        )

        if transaction_id in identities:
            raise ParticipantDecisionJourneyError(
                f"duplicate transaction_id: {transaction_id}"
            )

        identities.add(transaction_id)

    return tuple(ordered)


def _behaviour_summary(
    transactions: Sequence[JourneyTransaction],
) -> str:
    actions = {
        transaction.action
        for transaction in transactions
    }

    if not actions:
        return BEHAVIOUR_NO_TRADE

    if actions == {"BUY"}:
        return BEHAVIOUR_BUY_ONLY

    if actions == {"SELL"}:
        return BEHAVIOUR_SELL_ONLY

    return BEHAVIOUR_MIXED


def _pnl_direction(value: float) -> str:
    if value > _EPSILON:
        return PNL_GAIN

    if value < -_EPSILON:
        return PNL_LOSS

    return PNL_FLAT


def build_participant_decision_journey(
    *,
    target_stock_id: str,
    initial_cash: float,
    initial_holdings: Mapping[str, int],
    initial_portfolio_value: float,
    periods: Sequence[JourneyPeriodInput],
) -> ParticipantDecisionJourney:
    """Reconstruct a contiguous participant Period journey.

    Input periods must begin at P1 and be contiguous. This deliberately
    supports early bounded histories such as P1-P4 or P1-P11, preventing
    the caller from constructing an F1/F2 projection from future periods.
    """

    target_stock_id = _nonempty(
        "target_stock_id",
        target_stock_id,
    )

    cash = _finite_number(
        "initial_cash",
        initial_cash,
        minimum=0.0,
    )

    initial_value = _finite_number(
        "initial_portfolio_value",
        initial_portfolio_value,
        minimum=0.0,
    )

    holdings: dict[str, int] = {}

    for stock_id, raw_quantity in initial_holdings.items():
        stock = _nonempty(
            "initial holding stock_id",
            stock_id,
        )
        quantity = _strict_int(
            "initial holding quantity",
            raw_quantity,
            minimum=0,
        )

        if quantity:
            holdings[stock] = quantity

    ordered_periods = tuple(
        sorted(
            periods,
            key=lambda item: item.period_number,
        )
    )

    if not ordered_periods:
        raise ParticipantDecisionJourneyError(
            "journey requires at least one participant period"
        )

    expected_numbers = tuple(
        range(
            1,
            len(ordered_periods) + 1,
        )
    )
    actual_numbers = tuple(
        item.period_number
        for item in ordered_periods
    )

    if actual_numbers != expected_numbers:
        raise ParticipantDecisionJourneyError(
            "journey periods must begin at P1 and be contiguous"
        )

    if len(ordered_periods) > 15:
        raise ParticipantDecisionJourneyError(
            "journey cannot extend beyond P15"
        )

    previous_value = initial_value
    result_periods: list[JourneyPeriod] = []

    for period in ordered_periods:
        period_number = _strict_int(
            "period_number",
            period.period_number,
            minimum=1,
        )

        if period_number > 15:
            raise ParticipantDecisionJourneyError(
                "period_number cannot exceed P15"
            )

        date_value = _nonempty(
            "agent_world_date",
            period.agent_world_date,
        )

        if not isinstance(period.market_open, bool):
            raise ParticipantDecisionJourneyError(
                "market_open must be boolean"
            )

        if not isinstance(
            period.participant_trading_enabled,
            bool,
        ):
            raise ParticipantDecisionJourneyError(
                "participant_trading_enabled must be boolean"
            )

        if not isinstance(period.round_locked, bool):
            raise ParticipantDecisionJourneyError(
                "round_locked must be boolean"
            )

        if not period.round_locked:
            raise ParticipantDecisionJourneyError(
                f"P{period_number} is not behaviour-locked"
            )

        judgements = _normalise_judgements(
            period_number=period_number,
            target_stock_id=target_stock_id,
            rows=period.judgements,
        )

        raw_transactions = _normalise_transactions(
            period_number=period_number,
            rows=period.transactions,
        )

        if (
            raw_transactions
            and not period.participant_trading_enabled
        ):
            raise ParticipantDecisionJourneyError(
                "authoritative transaction exists while participant "
                "trading was disabled"
            )

        transaction_results: list[JourneyTransaction] = []
        holding_changes: dict[str, int] = {}

        for sequence, row in enumerate(
            raw_transactions,
            start=1,
        ):
            stock_id = _nonempty(
                "transaction stock_id",
                row.stock_id,
            )

            action = _nonempty(
                "transaction action",
                row.action,
            ).upper()

            if action not in _ALLOWED_TRADE_ACTIONS:
                raise ParticipantDecisionJourneyError(
                    f"unsupported transaction action: {action}"
                )

            executed_units = _strict_int(
                "executed_units",
                row.executed_units,
                minimum=0,
            )

            executed_notional = _finite_number(
                "executed_notional",
                row.executed_notional,
                minimum=0.0,
            )

            settlement_price = _finite_number(
                "settlement_price",
                row.settlement_price,
                minimum=0.0,
            )

            if settlement_price <= 0.0:
                raise ParticipantDecisionJourneyError(
                    "settlement_price must be positive"
                )

            fee = _finite_number(
                "fee",
                row.fee,
                minimum=0.0,
            )

            cash_before = _finite_number(
                "cash_before",
                row.cash_before,
                minimum=0.0,
            )
            cash_after = _finite_number(
                "cash_after",
                row.cash_after,
                minimum=0.0,
            )

            holding_before = _strict_int(
                "holding_before",
                row.holding_before,
                minimum=0,
            )
            holding_after = _strict_int(
                "holding_after",
                row.holding_after,
                minimum=0,
            )

            current_holding = holdings.get(
                stock_id,
                0,
            )

            if not _same_money(
                cash_before,
                cash,
            ):
                raise ParticipantDecisionJourneyError(
                    "transaction cash continuity mismatch"
                )

            if holding_before != current_holding:
                raise ParticipantDecisionJourneyError(
                    "transaction holding continuity mismatch"
                )

            if (
                action == "BUY"
                and holding_after < holding_before
            ):
                raise ParticipantDecisionJourneyError(
                    "BUY transaction reduced the holding"
                )

            if (
                action == "SELL"
                and holding_after > holding_before
            ):
                raise ParticipantDecisionJourneyError(
                    "SELL transaction increased the holding"
                )

            # Authoritative cash_after already incorporates notional and
            # transaction fee. Do not recalculate or subtract fee again.
            cash = cash_after

            if holding_after:
                holdings[stock_id] = holding_after
            else:
                holdings.pop(
                    stock_id,
                    None,
                )

            holding_changes[stock_id] = (
                holding_changes.get(stock_id, 0)
                + holding_after
                - holding_before
            )

            requested_amount = (
                None
                if row.requested_amount is None
                else _finite_number(
                    "requested_amount",
                    row.requested_amount,
                    minimum=0.0,
                )
            )

            requested_units = (
                None
                if row.requested_units is None
                else _finite_number(
                    "requested_units",
                    row.requested_units,
                    minimum=0.0,
                )
            )

            transaction_results.append(
                JourneyTransaction(
                    sequence_within_period=sequence,
                    transaction_id=_nonempty(
                        "transaction_id",
                        row.transaction_id,
                    ),
                    stock_id=stock_id,
                    action=action,
                    requested_amount=requested_amount,
                    requested_units=requested_units,
                    executed_units=executed_units,
                    executed_notional=executed_notional,
                    settlement_price=settlement_price,
                    fee=fee,
                    cash_before=cash_before,
                    cash_after=cash_after,
                    holding_before=holding_before,
                    holding_after=holding_after,
                    submitted_at=_iso_timestamp(
                        "transaction submitted_at",
                        row.submitted_at,
                    ),
                )
            )

        prices: dict[str, float] = {}

        for stock_id, raw_price in (
            period.canonical_close_prices.items()
        ):
            prices[
                _nonempty(
                    "canonical price stock_id",
                    stock_id,
                )
            ] = _finite_number(
                "canonical close price",
                raw_price,
                minimum=0.0,
            )

            if prices[stock_id] <= 0.0:
                raise ParticipantDecisionJourneyError(
                    "canonical close price must be positive"
                )

        portfolio_value = cash

        for stock_id, quantity in sorted(
            holdings.items()
        ):
            if stock_id not in prices:
                raise ParticipantDecisionJourneyError(
                    "canonical close price missing for held asset "
                    f"{stock_id}"
                )

            portfolio_value += (
                quantity * prices[stock_id]
            )

        period_pnl = (
            portfolio_value
            - previous_value
        )
        cumulative_pnl = (
            portfolio_value
            - initial_value
        )

        snapshot = JourneyPortfolioSnapshot(
            cash=cash,
            holdings=MappingProxyType(
                dict(
                    sorted(
                        holdings.items()
                    )
                )
            ),
            portfolio_value=portfolio_value,
        )

        result_periods.append(
            JourneyPeriod(
                period_number=period_number,
                agent_world_date=date_value,
                market_open=period.market_open,
                participant_trading_enabled=(
                    period.participant_trading_enabled
                ),
                judgements=judgements,
                transactions=tuple(
                    transaction_results
                ),
                behaviour_summary=_behaviour_summary(
                    transaction_results
                ),
                holding_changes=MappingProxyType(
                    dict(
                        sorted(
                            (
                                stock_id,
                                delta,
                            )
                            for stock_id, delta
                            in holding_changes.items()
                            if delta != 0
                        )
                    )
                ),
                portfolio_end=snapshot,
                period_pnl=period_pnl,
                cumulative_pnl=cumulative_pnl,
                pnl_direction=_pnl_direction(
                    period_pnl
                ),
                feedback_boundary=(
                    _FEEDBACK_BOUNDARIES.get(
                        period_number,
                        FEEDBACK_NONE,
                    )
                ),
            )
        )

        previous_value = portfolio_value

    return ParticipantDecisionJourney(
        journey_version=JOURNEY_VERSION,
        target_stock_id=target_stock_id,
        initial_cash=cash
        if not result_periods
        else _finite_number(
            "initial_cash",
            initial_cash,
            minimum=0.0,
        ),
        initial_holdings=MappingProxyType(
            dict(
                sorted(
                    (
                        stock_id,
                        quantity,
                    )
                    for stock_id, quantity
                    in initial_holdings.items()
                    if quantity != 0
                )
            )
        ),
        initial_portfolio_value=initial_value,
        periods=tuple(result_periods),
    )
