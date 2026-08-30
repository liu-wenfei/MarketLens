from __future__ import annotations

from dataclasses import dataclass

import pytest

from marketlens.human.feedback.journey_source import (
    JourneyAuthoritativeSourceAdapter,
    JourneySourceError,
)


SESSION_ID = "session-journey-source-test"
TARGET = "AAPL"


class FakeJudgements:
    def __init__(self, rows=()):
        self.rows = tuple(rows)

    def list_for_session(self, session_id):
        assert session_id == SESSION_ID
        return self.rows


class FakePortfolios:
    def __init__(
        self,
        *,
        initial_cash=1000.0,
        transactions=(),
    ):
        self.initial_cash = initial_cash
        self.transactions = tuple(transactions)

    def get_portfolio(self, session_id):
        assert session_id == SESSION_ID
        return {
            "session_id": session_id,
            "initial_cash": self.initial_cash,
            "cash": self.initial_cash,
        }

    def list_transactions_for_session(
        self,
        session_id,
    ):
        assert session_id == SESSION_ID
        return self.transactions


class FakeRounds:
    def __init__(self, steps):
        self.steps = tuple(steps)

    def list_for_session(self, session_id):
        assert session_id == SESSION_ID
        return tuple(
            {
                "session_id": session_id,
                "step": step,
                "completion_id": f"completion-{step}",
            }
            for step in self.steps
        )


@dataclass(frozen=True)
class FakeStatus:
    market_open: bool
    participant_trading_enabled: bool
    market_state_date: str


class FakeCalendar:
    def status(self, current_date):
        return FakeStatus(
            market_open=True,
            participant_trading_enabled=True,
            market_state_date=current_date,
        )


@dataclass(frozen=True)
class FakeClose:
    close: float


class FakePriceProvider:
    def __init__(self):
        self.prices = {
            TARGET: 100.0,
        }

    def get_close(self, stock_id, trading_date):
        return FakeClose(
            close=self.prices[stock_id]
        )


class FakeContract:
    def checkpoint_date(self, step):
        return (
            "2023-06-15",
            "2023-06-16",
            "2023-06-19",
        )[step]


def make_adapter(
    *,
    judgements=(),
    transactions=(),
    locked_steps=(0,),
):
    return JourneyAuthoritativeSourceAdapter(
        judgements=FakeJudgements(judgements),
        portfolios=FakePortfolios(
            transactions=transactions,
        ),
        rounds=FakeRounds(locked_steps),
        price_provider=FakePriceProvider(),
        calendar=FakeCalendar(),
        contract=FakeContract(),
        target_stock_id=TARGET,
    )


def p1_judgements():
    return (
        {
            "session_id": SESSION_ID,
            "judgement_id": "judgement-p1-1",
            "experiment_step": 0,
            "agent_world_date": "2023-06-15",
            "stock_id": TARGET,
            "action": "BUY",
            "confidence": 70.0,
            "evidence_sources": '["market information"]',
            "rationale": "Initial assessment.",
            "submitted_at": "2023-06-15T12:01:00+00:00",
        },
        {
            "session_id": SESSION_ID,
            "judgement_id": "judgement-p1-2",
            "experiment_step": 0,
            "agent_world_date": "2023-06-15",
            "stock_id": TARGET,
            "action": "HOLD",
            "confidence": 60.0,
            "evidence_sources": '["market information"]',
            "rationale": "Second formal assessment.",
            "submitted_at": "2023-06-15T12:02:00+00:00",
        },
    )


def transaction_row(
    *,
    transaction_id,
    step=0,
    stock_id=TARGET,
    action="BUY",
    requested_amount=100.0,
    requested_units=1.0,
    executed_units=1,
    executed_notional=100.0,
    settlement_price=100.0,
    price_date="2023-06-15",
    fee=0.0,
    cash_before=1000.0,
    cash_after=900.0,
    holding_before=0,
    holding_after=1,
    submitted_at="2023-06-15T13:00:00+00:00",
):
    return {
        "session_id": SESSION_ID,
        "transaction_id": transaction_id,
        "step": step,
        "stock_id": stock_id,
        "action": action,
        "requested_amount": requested_amount,
        "requested_units": requested_units,
        "executed_units": executed_units,
        "executed_notional": executed_notional,
        "settlement_price": settlement_price,
        "price_date": price_date,
        "fee": fee,
        "cash_before": cash_before,
        "cash_after": cash_after,
        "holding_before": holding_before,
        "holding_after": holding_after,
        "submitted_at": submitted_at,
    }



def test_builds_single_locked_no_trade_period():
    journey = make_adapter(
        judgements=p1_judgements(),
    ).build(
        SESSION_ID
    )

    assert len(journey.periods) == 1

    period = journey.periods[0]

    assert period.period_number == 1
    assert period.agent_world_date == "2023-06-15"
    assert period.market_open is True
    assert period.participant_trading_enabled is True
    assert period.transactions == ()
    assert period.behaviour_summary == "NO_TRADE"


def test_requires_at_least_one_locked_round():
    adapter = make_adapter(
        locked_steps=(),
    )

    with pytest.raises(
        JourneySourceError,
        match="at least one locked",
    ):
        adapter.build(
            SESSION_ID
        )


def test_requires_contiguous_locked_rounds():
    adapter = make_adapter(
        locked_steps=(0, 2),
    )

    with pytest.raises(
        JourneySourceError,
        match="contiguous",
    ):
        adapter.build(
            SESSION_ID
        )


def test_maps_authoritative_buy_transaction():
    row = transaction_row(
        transaction_id="tx-buy-1",
    )

    journey = make_adapter(
        judgements=p1_judgements(),
        transactions=(row,),
    ).build(SESSION_ID)

    period = journey.periods[0]

    assert period.behaviour_summary == "BUY_ONLY"
    assert len(period.transactions) == 1

    transaction = period.transactions[0]

    assert transaction.transaction_id == "tx-buy-1"
    assert transaction.stock_id == TARGET
    assert transaction.action == "BUY"
    assert transaction.executed_units == 1
    assert transaction.executed_notional == 100.0
    assert transaction.settlement_price == 100.0
    assert transaction.cash_before == 1000.0
    assert transaction.cash_after == 900.0
    assert transaction.holding_before == 0
    assert transaction.holding_after == 1

    assert period.portfolio_end.cash == 900.0
    assert period.portfolio_end.holdings[TARGET] == 1


def test_rejects_transaction_price_date_mismatch():
    row = transaction_row(
        transaction_id="tx-wrong-date",
        price_date="2023-06-16",
    )

    adapter = make_adapter(
        judgements=p1_judgements(),
        transactions=(row,),
    )

    with pytest.raises(
        JourneySourceError,
        match="price_date disagrees",
    ):
        adapter.build(SESSION_ID)


def test_rejects_canonical_settlement_price_mismatch():
    row = transaction_row(
        transaction_id="tx-wrong-price",
        settlement_price=99.0,
    )

    adapter = make_adapter(
        judgements=p1_judgements(),
        transactions=(row,),
    )

    with pytest.raises(
        JourneySourceError,
        match="settlement price mismatch",
    ):
        adapter.build(SESSION_ID)


def test_rejects_transaction_cash_continuity_mismatch():
    row = transaction_row(
        transaction_id="tx-bad-cash",
        cash_before=999.0,
        cash_after=899.0,
    )

    adapter = make_adapter(
        judgements=p1_judgements(),
        transactions=(row,),
    )

    with pytest.raises(
        JourneySourceError,
        match="cash continuity mismatch",
    ):
        adapter.build(SESSION_ID)


def test_rejects_transaction_holding_continuity_mismatch():
    row = transaction_row(
        transaction_id="tx-bad-holding",
        holding_before=1,
        holding_after=2,
    )

    adapter = make_adapter(
        judgements=p1_judgements(),
        transactions=(row,),
    )

    with pytest.raises(
        JourneySourceError,
        match="holding continuity mismatch",
    ):
        adapter.build(SESSION_ID)


def test_rejects_transaction_beyond_locked_boundary():
    row = transaction_row(
        transaction_id="tx-future",
        step=1,
        price_date="2023-06-16",
        submitted_at="2023-06-16T13:00:00+00:00",
    )

    adapter = make_adapter(
        judgements=p1_judgements(),
        transactions=(row,),
    )

    with pytest.raises(
        JourneySourceError,
        match="beyond",
    ):
        adapter.build(SESSION_ID)


def test_rejects_transaction_when_participant_trading_disabled():
    row = transaction_row(
        transaction_id="tx-disabled",
    )

    adapter = make_adapter(
        judgements=p1_judgements(),
        transactions=(row,),
    )

    adapter.calendar.status = lambda date: {
        "market_open": False,
        "participant_trading_enabled": False,
        "market_state_date": "2023-06-14",
    }

    with pytest.raises(
        JourneySourceError,
        match="trading-disabled",
    ):
        adapter.build(SESSION_ID)


def test_sell_to_zero_non_target_asset_retains_required_price():
    other_stock = "OTHER"

    buy = transaction_row(
        transaction_id="tx-other-buy",
        stock_id=other_stock,
        action="BUY",
        executed_units=1,
        executed_notional=50.0,
        settlement_price=50.0,
        cash_before=1000.0,
        cash_after=950.0,
        holding_before=0,
        holding_after=1,
        submitted_at="2023-06-15T13:00:00+00:00",
    )

    sell = transaction_row(
        transaction_id="tx-other-sell",
        stock_id=other_stock,
        action="SELL",
        executed_units=1,
        executed_notional=50.0,
        settlement_price=50.0,
        cash_before=950.0,
        cash_after=1000.0,
        holding_before=1,
        holding_after=0,
        submitted_at="2023-06-15T14:00:00+00:00",
    )

    adapter = make_adapter(
        judgements=p1_judgements(),
        transactions=(buy, sell),
    )

    adapter.price_provider.prices[other_stock] = 50.0

    journey = adapter.build(SESSION_ID)

    period = journey.periods[0]

    assert period.behaviour_summary == "MIXED_TRADING"
    assert period.portfolio_end.holdings.get(other_stock, 0) == 0
    assert len(period.transactions) == 2


def test_rejects_judgement_agent_world_date_mismatch():
    rows = list(p1_judgements())
    rows[0] = {
        **rows[0],
        "agent_world_date": "2023-06-16",
    }

    adapter = make_adapter(
        judgements=tuple(rows),
    )

    with pytest.raises(
        JourneySourceError,
        match="agent_world_date disagrees",
    ):
        adapter.build(SESSION_ID)


def test_rejects_judgement_beyond_locked_boundary():
    future = {
        "session_id": SESSION_ID,
        "judgement_id": "judgement-future",
        "experiment_step": 1,
        "agent_world_date": "2023-06-16",
        "stock_id": TARGET,
        "action": "BUY",
        "confidence": 50.0,
        "evidence_sources": '["market information"]',
        "rationale": "Future judgement.",
        "submitted_at": "2023-06-16T12:00:00+00:00",
    }

    adapter = make_adapter(
        judgements=p1_judgements() + (future,),
    )

    with pytest.raises(
        JourneySourceError,
        match="beyond",
    ):
        adapter.build(SESSION_ID)


def test_closed_locked_period_is_not_trading_enabled():
    adapter = make_adapter(
        judgements=p1_judgements(),
    )

    adapter.calendar.status = lambda date: {
        "market_open": False,
        "participant_trading_enabled": False,
        "market_state_date": "2023-06-14",
    }

    journey = adapter.build(SESSION_ID)

    period = journey.periods[0]

    assert period.market_open is False
    assert period.participant_trading_enabled is False
    assert period.transactions == ()


def test_multi_asset_transaction_replay():
    first = transaction_row(
        transaction_id="tx-target-buy",
        stock_id=TARGET,
        action="BUY",
        executed_units=1,
        executed_notional=100.0,
        settlement_price=100.0,
        cash_before=1000.0,
        cash_after=900.0,
        holding_before=0,
        holding_after=1,
        submitted_at="2023-06-15T13:00:00+00:00",
    )

    second = transaction_row(
        transaction_id="tx-other-buy",
        stock_id="OTHER",
        action="BUY",
        executed_units=2,
        executed_notional=100.0,
        settlement_price=50.0,
        cash_before=900.0,
        cash_after=800.0,
        holding_before=0,
        holding_after=2,
        submitted_at="2023-06-15T14:00:00+00:00",
    )

    adapter = make_adapter(
        judgements=p1_judgements(),
        transactions=(first, second),
    )

    adapter.price_provider.prices["OTHER"] = 50.0

    journey = adapter.build(SESSION_ID)

    period = journey.periods[0]

    assert period.portfolio_end.cash == 800.0
    assert period.portfolio_end.holdings[TARGET] == 1
    assert period.portfolio_end.holdings["OTHER"] == 2


def test_transaction_order_is_authoritatively_replayed():
    later = transaction_row(
        transaction_id="tx-2",
        cash_before=900.0,
        cash_after=800.0,
        holding_before=1,
        holding_after=2,
        submitted_at="2023-06-15T14:00:00+00:00",
    )

    earlier = transaction_row(
        transaction_id="tx-1",
        cash_before=1000.0,
        cash_after=900.0,
        holding_before=0,
        holding_after=1,
        submitted_at="2023-06-15T13:00:00+00:00",
    )

    journey = make_adapter(
        judgements=p1_judgements(),
        transactions=(later, earlier),
    ).build(SESSION_ID)

    assert tuple(
        tx.transaction_id
        for tx in journey.periods[0].transactions
    ) == (
        "tx-1",
        "tx-2",
    )
