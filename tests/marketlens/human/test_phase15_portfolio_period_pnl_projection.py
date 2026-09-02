from __future__ import annotations

from types import SimpleNamespace

import pytest

from marketlens.human.routers.portfolio import (
    PortfolioPeriodPnlUnavailableError,
    _current_period_pnl,
    _previous_locked_portfolio_value,
)
from marketlens.human.schemas import PortfolioRead


def _portfolio(
    *,
    step: int,
    total_value: float,
) -> PortfolioRead:
    return PortfolioRead(
        session_id="session-1",
        step=step,
        price_date="2023-06-26",
        initial_cash=10000.0,
        cash=9000.0,
        total_value=total_value,
        holdings=[],
    )


def _asset(
    stock_id: str,
    closes: tuple[float, ...],
):
    dates = (
        "2023-06-19",
        "2023-06-20",
        "2023-06-21",
        "2023-06-26",
    )

    history = tuple(
        SimpleNamespace(
            participant_date=date,
            price_date=date,
            close=close,
        )
        for date, close in zip(
            dates,
            closes,
            strict=True,
        )
    )

    return SimpleNamespace(
        stock_id=stock_id,
        price_history=history,
    )


def _overview():
    return SimpleNamespace(
        current_date="2023-06-26",
        price_date="2023-06-26",
        assets=(
            _asset(
                "MEI",
                (9.50, 9.60, 12.00, 13.00),
            ),
            _asset(
                "IEEI",
                (10.00, 10.00, 20.00, 21.00),
            ),
        ),
    )


class FakePortfolioStore:
    def __init__(
        self,
        transactions,
    ):
        self.transactions = tuple(
            transactions
        )

    def get_portfolio(
        self,
        session_id,
    ):
        assert session_id == "session-1"

        return {
            "session_id": session_id,
            "initial_cash": 10000.0,
            "cash": 0.0,
        }

    def list_transactions_for_session(
        self,
        session_id,
    ):
        assert session_id == "session-1"
        return self.transactions


class FakeRoundStore:
    def __init__(
        self,
        steps,
    ):
        self.steps = tuple(
            steps
        )

    def list_for_session(
        self,
        session_id,
    ):
        assert session_id == "session-1"

        return tuple(
            {
                "step": step,
            }
            for step in self.steps
        )


def _runtime(
    *,
    transactions=(),
    locked_steps=(0, 1, 2),
):
    return SimpleNamespace(
        journey=SimpleNamespace(
            portfolios=FakePortfolioStore(
                transactions
            ),
            rounds=FakeRoundStore(
                locked_steps
            ),
        )
    )


def test_p1_has_no_period_pnl():
    amount, percentage = (
        _current_period_pnl(
            _portfolio(
                step=0,
                total_value=10020.0,
            ),
            None,
        )
    )

    assert amount is None
    assert percentage is None


def test_p4_baseline_replays_only_locked_p1_to_p3_transactions():
    transactions = (
        {
            "step": 0,
            "stock_id": "MEI",
            "cash_before": 10000.0,
            "cash_after": 9900.0,
            "holding_before": 0,
            "holding_after": 10,
        },

        # This is a genuine current P4 transaction.
        # It MUST NOT alter the P3 historical baseline.
        {
            "step": 3,
            "stock_id": "IEEI",
            "cash_before": 9900.0,
            "cash_after": 9800.0,
            "holding_before": 0,
            "holding_after": 5,
        },
    )

    previous_value = (
        _previous_locked_portfolio_value(
            session_id="session-1",
            current_step=3,
            runtime=_runtime(
                transactions=transactions
            ),
            overview=_overview(),
        )
    )

    # P3:
    # cash 9900 + 10 MEI * P3 close 12 = 10020
    assert previous_value == pytest.approx(
        10020.0
    )


def test_p4_period_pnl_uses_reconstructed_p3_end():
    amount, percentage = (
        _current_period_pnl(
            _portfolio(
                step=3,
                total_value=9990.0,
            ),
            10020.0,
        )
    )

    assert amount == pytest.approx(
        -30.0
    )

    assert percentage == pytest.approx(
        -30.0 / 10020.0 * 100.0
    )


def test_missing_previous_locked_step_fails_closed():
    with pytest.raises(
        PortfolioPeriodPnlUnavailableError
    ):
        _previous_locked_portfolio_value(
            session_id="session-1",
            current_step=3,
            runtime=_runtime(
                locked_steps=(0, 1),
            ),
            overview=_overview(),
        )


def test_historical_cash_continuity_mismatch_fails_closed():
    transactions = (
        {
            "step": 0,
            "stock_id": "MEI",
            "cash_before": 9999.0,
            "cash_after": 9900.0,
            "holding_before": 0,
            "holding_after": 10,
        },
    )

    with pytest.raises(
        PortfolioPeriodPnlUnavailableError
    ):
        _previous_locked_portfolio_value(
            session_id="session-1",
            current_step=3,
            runtime=_runtime(
                transactions=transactions
            ),
            overview=_overview(),
        )


def test_current_step_transaction_does_not_require_historical_continuity():
    transactions = (
        {
            "step": 3,
            "stock_id": "MEI",
            "cash_before": 1234.0,
            "cash_after": 1000.0,
            "holding_before": 999,
            "holding_after": 1000,
        },
    )

    previous_value = (
        _previous_locked_portfolio_value(
            session_id="session-1",
            current_step=3,
            runtime=_runtime(
                transactions=transactions
            ),
            overview=_overview(),
        )
    )

    assert previous_value == pytest.approx(
        10000.0
    )
