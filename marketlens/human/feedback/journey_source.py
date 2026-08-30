"""Authoritative source adapter for participant decision journeys.

This module is read-only. It does not own participant state and does not
write experimental data. It projects already-authoritative judgement,
round-completion, portfolio-transaction and canonical market-price sources
into the frozen pure Journey v1 projection contract.
"""

from __future__ import annotations

import json
import math

from collections.abc import Mapping
from typing import Any

from marketlens.human.feedback.journey import (
    JourneyJudgementInput,
    JourneyPeriodInput,
    JourneyTransactionInput,
    ParticipantDecisionJourney,
    build_participant_decision_journey,
)


class JourneySourceError(ValueError):
    """Raised when authoritative journey source data is incomplete or inconsistent."""


def _field(row: object, name: str) -> Any:
    if isinstance(row, Mapping):
        try:
            return row[name]
        except KeyError as exc:
            raise JourneySourceError(
                f"authoritative source row is missing {name!r}"
            ) from exc

    if not hasattr(row, name):
        raise JourneySourceError(
            f"authoritative source object is missing {name!r}"
        )

    return getattr(row, name)


def _nonempty(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise JourneySourceError(f"{name} must be a string")

    resolved = value.strip()

    if not resolved:
        raise JourneySourceError(f"{name} must not be empty")

    return resolved


def _finite_number(
    name: str,
    value: object,
    *,
    minimum: float | None = None,
) -> float:
    if isinstance(value, bool):
        raise JourneySourceError(
            f"{name} must be a finite number"
        )

    try:
        resolved = float(value)
    except (TypeError, ValueError) as exc:
        raise JourneySourceError(
            f"{name} must be a finite number"
        ) from exc

    if not math.isfinite(resolved):
        raise JourneySourceError(
            f"{name} must be a finite number"
        )

    if minimum is not None and resolved < minimum:
        raise JourneySourceError(
            f"{name} must be >= {minimum}"
        )

    return resolved


def _strict_int(
    name: str,
    value: object,
    *,
    minimum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise JourneySourceError(
            f"{name} must be an integer"
        )

    if minimum is not None and value < minimum:
        raise JourneySourceError(
            f"{name} must be >= {minimum}"
        )

    return value


class JourneyAuthoritativeSourceAdapter:
    """Build Journey v1 from existing authoritative participant sources.

    Source-of-truth ownership remains with the injected stores/providers:
    judgements
        formal participant judgement persistence
    portfolios
        participant initial portfolio and settled transactions
    rounds
        completed/locked participant rounds
    contract
        frozen experiment checkpoint dates
    calendar
        authorised market/trading state
    price_provider
        exact-date canonical close prices

    This adapter performs no writes and creates no second persistence layer.
    """

    def __init__(
        self,
        *,
        judgements: object,
        portfolios: object,
        rounds: object,
        price_provider: object,
        calendar: object,
        contract: object,
        target_stock_id: str,
    ):
        self.judgements = judgements
        self.portfolios = portfolios
        self.rounds = rounds
        self.price_provider = price_provider
        self.calendar = calendar
        self.contract = contract
        self.target_stock_id = _nonempty(
            "target_stock_id",
            target_stock_id,
        )

    def _read_locked_rounds(
        self,
        session_id: str,
    ) -> dict[int, object]:
        try:
            rows = tuple(
                self.rounds.list_for_session(
                    session_id
                )
            )
        except Exception as exc:
            raise JourneySourceError(
                "failed to read authoritative round completions"
            ) from exc

        locked: dict[int, object] = {}

        for row in rows:
            row_session = _nonempty(
                "round session_id",
                _field(row, "session_id"),
            )

            if row_session != session_id:
                raise JourneySourceError(
                    "round reader returned another session"
                )

            step = _field(row, "step")

            if isinstance(step, bool) or not isinstance(step, int) or step < 0:
                raise JourneySourceError(
                    "round step must be a non-negative integer"
                )

            if step in locked:
                raise JourneySourceError(
                    f"duplicate locked completion for period {step + 1}"
                )

            locked[step] = row

        return locked

    def _read_judgements(
        self,
        session_id: str,
    ) -> tuple[object, ...]:
        try:
            rows = tuple(
                self.judgements.list_for_session(
                    session_id
                )
            )
        except Exception as exc:
            raise JourneySourceError(
                "failed to read authoritative judgements"
            ) from exc

        for row in rows:
            row_session = _nonempty(
                "judgement session_id",
                _field(row, "session_id"),
            )

            if row_session != session_id:
                raise JourneySourceError(
                    "judgement reader returned another session"
                )

        return rows

    def _judgement_inputs(
        self,
        session_id: str,
    ) -> tuple[JourneyJudgementInput, ...]:
        inputs: list[JourneyJudgementInput] = []

        for row in self._read_judgements(
            session_id
        ):
            step = _strict_int(
                "judgement experiment_step",
                _field(row, "experiment_step"),
                minimum=0,
            )
            period_number = step + 1

            persisted_date = _nonempty(
                "judgement agent_world_date",
                _field(
                    row,
                    "agent_world_date",
                ),
            )

            if persisted_date != self._checkpoint_date(
                period_number
            ):
                raise JourneySourceError(
                    "judgement agent_world_date disagrees "
                    "with the frozen checkpoint date"
                )

            raw_evidence = _field(
                row,
                "evidence_sources",
            )

            if not isinstance(raw_evidence, str):
                raise JourneySourceError(
                    "judgement evidence_sources must be persisted JSON text"
                )

            try:
                decoded = json.loads(
                    raw_evidence
                )
            except json.JSONDecodeError as exc:
                raise JourneySourceError(
                    "judgement evidence_sources is invalid JSON"
                ) from exc

            if not isinstance(decoded, list) or any(
                not isinstance(item, str)
                or not item.strip()
                for item in decoded
            ):
                raise JourneySourceError(
                    "judgement evidence_sources must be a JSON string list"
                )

            rationale = _field(
                row,
                "rationale",
            )

            if rationale is not None and not isinstance(
                rationale,
                str,
            ):
                raise JourneySourceError(
                    "judgement rationale must be text or null"
                )

            inputs.append(
                JourneyJudgementInput(
                    period_number=period_number,
                    stock_id=_nonempty(
                        "judgement stock_id",
                        _field(row, "stock_id"),
                    ),
                    action=_nonempty(
                        "judgement action",
                        _field(row, "action"),
                    ).upper(),
                    confidence=_finite_number(
                        "judgement confidence",
                        _field(row, "confidence"),
                    ),
                    evidence_sources=tuple(
                        item.strip()
                        for item in decoded
                    ),
                    rationale=rationale,
                    submitted_at=_nonempty(
                        "judgement submitted_at",
                        str(_field(row, "submitted_at")),
                    ),
                )
            )

        return tuple(inputs)

    def _checkpoint_date(
        self,
        period_number: int,
    ) -> str:
        try:
            raw = self.contract.checkpoint_date(
                period_number - 1
            )
        except Exception as exc:
            raise JourneySourceError(
                f"cannot resolve checkpoint date for "
                f"period {period_number}"
            ) from exc

        return _nonempty(
            "checkpoint date",
            str(raw),
        )

    def _read_transactions(
        self,
        session_id: str,
    ) -> tuple[object, ...]:
        try:
            rows = tuple(
                self.portfolios.list_transactions_for_session(
                    session_id
                )
            )
        except Exception as exc:
            raise JourneySourceError(
                "failed to read authoritative participant transactions"
            ) from exc

        checked: list[tuple[tuple[int, str, str], object]] = []

        for row in rows:
            row_session = _nonempty(
                "transaction session_id",
                _field(row, "session_id"),
            )

            if row_session != session_id:
                raise JourneySourceError(
                    "transaction reader returned another session"
                )

            step = _field(row, "step")

            if isinstance(step, bool) or not isinstance(step, int) or step < 0:
                raise JourneySourceError(
                    "transaction step must be a non-negative integer"
                )

            submitted_at = _nonempty(
                "transaction submitted_at",
                _field(row, "submitted_at"),
            )

            transaction_id = _nonempty(
                "transaction_id",
                _field(row, "transaction_id"),
            )

            checked.append(
                (
                    (
                        step,
                        submitted_at,
                        transaction_id,
                    ),
                    row,
                )
            )

        checked.sort(
            key=lambda item: item[0]
        )

        return tuple(
            row
            for _, row in checked
        )

    def _market_status(
        self,
        period_number: int,
    ) -> object:
        checkpoint_date = self._checkpoint_date(
            period_number
        )

        try:
            return self.calendar.status(
                checkpoint_date
            )
        except Exception as exc:
            raise JourneySourceError(
                "cannot resolve authoritative market status "
                f"for period {period_number}"
            ) from exc

    def _canonical_price(
        self,
        *,
        stock_id: str,
        market_state_date: str,
    ) -> float:
        try:
            record = self.price_provider.get_close(
                stock_id,
                market_state_date,
            )
        except Exception as exc:
            raise JourneySourceError(
                "canonical close price unavailable "
                f"for {stock_id!r} on {market_state_date}"
            ) from exc

        return _finite_number(
            "canonical close price",
            _field(record, "close"),
            minimum=0.000000000001,
        )

    def _transaction_inputs(
        self,
        session_id: str,
    ) -> tuple[JourneyTransactionInput, ...]:
        inputs: list[JourneyTransactionInput] = []

        for row in self._read_transactions(
            session_id
        ):
            step = _strict_int(
                "transaction step",
                _field(row, "step"),
                minimum=0,
            )
            period_number = step + 1

            stock_id = _nonempty(
                "transaction stock_id",
                _field(row, "stock_id"),
            )

            action = _nonempty(
                "transaction action",
                str(_field(row, "action")),
            ).upper()

            if action not in {
                "BUY",
                "SELL",
            }:
                raise JourneySourceError(
                    f"unsupported transaction action {action!r}"
                )

            expected_price_date = (
                self._checkpoint_date(
                    period_number
                )
            )

            persisted_price_date = _nonempty(
                "transaction price_date",
                str(_field(row, "price_date")),
            )

            if persisted_price_date != expected_price_date:
                raise JourneySourceError(
                    "transaction price_date disagrees "
                    "with the frozen checkpoint date"
                )

            settlement_price = _finite_number(
                "transaction settlement_price",
                _field(row, "settlement_price"),
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
                raise JourneySourceError(
                    "canonical settlement price is unavailable "
                    "for the persisted transaction date"
                ) from exc

            canonical_price = _finite_number(
                "canonical settlement price",
                _field(canonical_record, "close"),
                minimum=0.000000000001,
            )

            if not math.isclose(
                settlement_price,
                canonical_price,
                rel_tol=1e-9,
                abs_tol=1e-9,
            ):
                raise JourneySourceError(
                    "transaction settlement price mismatch; "
                    "persisted settlement_price disagrees "
                    "with the canonical exact-date close"
                )

            holding_before = _strict_int(
                "transaction holding_before",
                _field(row, "holding_before"),
                minimum=0,
            )
            holding_after = _strict_int(
                "transaction holding_after",
                _field(row, "holding_after"),
                minimum=0,
            )

            if (
                action == "BUY"
                and holding_after <= holding_before
            ):
                raise JourneySourceError(
                    "BUY transaction does not increase "
                    "authoritative holding"
                )

            if (
                action == "SELL"
                and holding_after >= holding_before
            ):
                raise JourneySourceError(
                    "SELL transaction does not decrease "
                    "authoritative holding"
                )

            inputs.append(
                JourneyTransactionInput(
                    transaction_id=_nonempty(
                        "transaction_id",
                        _field(row, "transaction_id"),
                    ),
                    period_number=period_number,
                    stock_id=stock_id,
                    action=action,
                    requested_amount=_finite_number(
                        "transaction requested_amount",
                        _field(row, "requested_amount"),
                        minimum=0.0,
                    ),
                    requested_units=_finite_number(
                        "transaction requested_units",
                        _field(row, "requested_units"),
                        minimum=0.0,
                    ),
                    executed_units=_strict_int(
                        "transaction executed_units",
                        _field(row, "executed_units"),
                        minimum=0,
                    ),
                    executed_notional=_finite_number(
                        "transaction executed_notional",
                        _field(row, "executed_notional"),
                        minimum=0.0,
                    ),
                    settlement_price=settlement_price,
                    fee=_finite_number(
                        "transaction fee",
                        _field(row, "fee"),
                        minimum=0.0,
                    ),
                    cash_before=_finite_number(
                        "transaction cash_before",
                        _field(row, "cash_before"),
                        minimum=0.0,
                    ),
                    cash_after=_finite_number(
                        "transaction cash_after",
                        _field(row, "cash_after"),
                        minimum=0.0,
                    ),
                    holding_before=holding_before,
                    holding_after=holding_after,
                    submitted_at=_nonempty(
                        "transaction submitted_at",
                        _field(row, "submitted_at"),
                    ),
                )
            )

        return tuple(inputs)

    def _locked_period_numbers(
        self,
        session_id: str,
    ) -> tuple[int, ...]:
        locked = self._read_locked_rounds(
            session_id
        )

        if not locked:
            raise JourneySourceError(
                "journey requires at least one locked participant round"
            )

        ordered_steps = tuple(
            sorted(locked)
        )

        expected_steps = tuple(
            range(
                len(ordered_steps)
            )
        )

        if ordered_steps != expected_steps:
            raise JourneySourceError(
                "locked participant rounds must begin at P1 "
                "and be contiguous"
            )

        return tuple(
            step + 1
            for step in ordered_steps
        )

    def build(
        self,
        session_id: str,
    ) -> ParticipantDecisionJourney:
        """Build the contiguous locked participant journey for one session."""

        session_id = _nonempty(
            "session_id",
            session_id,
        )

        period_numbers = self._locked_period_numbers(
            session_id
        )
        final_period = period_numbers[-1]

        try:
            portfolio_row = self.portfolios.get_portfolio(
                session_id
            )
        except Exception as exc:
            raise JourneySourceError(
                "failed to read authoritative participant portfolio"
            ) from exc

        if portfolio_row is None:
            raise JourneySourceError(
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

        initial_holdings: dict[str, int] = {}
        initial_portfolio_value = initial_cash

        judgement_inputs = self._judgement_inputs(
            session_id
        )
        transaction_inputs = self._transaction_inputs(
            session_id
        )

        for item in judgement_inputs:
            if item.period_number > final_period:
                raise JourneySourceError(
                    "authoritative judgement exists beyond "
                    "the contiguous locked journey boundary"
                )

        for item in transaction_inputs:
            if item.period_number > final_period:
                raise JourneySourceError(
                    "authoritative transaction exists beyond "
                    "the contiguous locked journey boundary"
                )

        judgements_by_period: dict[
            int,
            list[JourneyJudgementInput],
        ] = {}

        for item in judgement_inputs:
            judgements_by_period.setdefault(
                item.period_number,
                [],
            ).append(item)

        transactions_by_period: dict[
            int,
            list[JourneyTransactionInput],
        ] = {}

        for item in transaction_inputs:
            transactions_by_period.setdefault(
                item.period_number,
                [],
            ).append(item)

        cash = initial_cash
        positions: dict[str, int] = {}

        periods: list[JourneyPeriodInput] = []

        for period_number in period_numbers:
            status = self._market_status(
                period_number
            )

            market_open = _field(
                status,
                "market_open",
            )
            trading_enabled = _field(
                status,
                "participant_trading_enabled",
            )
            market_state_date = _nonempty(
                "market_state_date",
                _field(
                    status,
                    "market_state_date",
                ),
            )

            if not isinstance(
                market_open,
                bool,
            ):
                raise JourneySourceError(
                    "market_open must be boolean"
                )

            if not isinstance(
                trading_enabled,
                bool,
            ):
                raise JourneySourceError(
                    "participant_trading_enabled must be boolean"
                )

            checkpoint_date = self._checkpoint_date(
                period_number
            )

            period_transactions = tuple(
                transactions_by_period.get(
                    period_number,
                    (),
                )
            )

            if (
                period_transactions
                and not trading_enabled
            ):
                raise JourneySourceError(
                    "authoritative transaction exists during "
                    "a participant-trading-disabled period"
                )

            for transaction in period_transactions:
                current_holding = positions.get(
                    transaction.stock_id,
                    0,
                )

                if not math.isclose(
                    cash,
                    transaction.cash_before,
                    rel_tol=1e-9,
                    abs_tol=1e-6,
                ):
                    raise JourneySourceError(
                        "transaction cash continuity mismatch "
                        "during historical replay"
                    )

                if (
                    current_holding
                    != transaction.holding_before
                ):
                    raise JourneySourceError(
                        "transaction holding continuity mismatch "
                        "during historical replay"
                    )

                cash = transaction.cash_after

                if transaction.holding_after == 0:
                    positions.pop(
                        transaction.stock_id,
                        None,
                    )
                else:
                    positions[
                        transaction.stock_id
                    ] = transaction.holding_after

            required_assets = set(
                positions
            )
            required_assets.add(
                self.target_stock_id
            )

            canonical_close_prices = {
                stock_id: self._canonical_price(
                    stock_id=stock_id,
                    market_state_date=market_state_date,
                )
                for stock_id in sorted(
                    required_assets
                )
            }

            periods.append(
                JourneyPeriodInput(
                    period_number=period_number,
                    agent_world_date=checkpoint_date,
                    market_open=market_open,
                    participant_trading_enabled=trading_enabled,
                    round_locked=True,
                    judgements=tuple(
                        judgements_by_period.get(
                            period_number,
                            (),
                        )
                    ),
                    transactions=period_transactions,
                    canonical_close_prices=canonical_close_prices,
                )
            )

        return build_participant_decision_journey(
            target_stock_id=self.target_stock_id,
            initial_cash=initial_cash,
            initial_holdings=initial_holdings,
            initial_portfolio_value=initial_portfolio_value,
            periods=tuple(periods),
        )
