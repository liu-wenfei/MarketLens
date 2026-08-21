from __future__ import annotations

import pytest

from marketlens.human.portfolio.models import AccountState
from marketlens.human.portfolio.policy import PortfolioPolicy, PortfolioPolicyError
from marketlens.human.portfolio.preview import PortfolioAction, PreviewReason, preview_order
from marketlens.human.portfolio.settlement import execute_preview


def test_policy_defaults_are_long_only_unlevered_and_whole_unit():
    policy = PortfolioPolicy()
    assert policy.transaction_cost_bps == 0.0
    assert policy.max_position_weight is None
    assert policy.whole_units is True
    assert policy.allow_short is False
    assert policy.allow_leverage is False


def test_policy_rejects_unsupported_short_leverage_or_fractional_accounts():
    with pytest.raises(PortfolioPolicyError):
        PortfolioPolicy(allow_short=True)
    with pytest.raises(PortfolioPolicyError):
        PortfolioPolicy(allow_leverage=True)
    with pytest.raises(PortfolioPolicyError):
        PortfolioPolicy(whole_units=False)


def test_buy_preview_is_side_effect_free_and_uses_cash_only():
    account = AccountState(cash=1000.0, positions={"TLEI": 2, "FSEI": 3})
    original = account.copy()
    prices = {"TLEI": 10.0, "FSEI": 20.0}

    preview = preview_order(
        account=account,
        stock_id="TLEI",
        action=PortfolioAction.BUY,
        requested_amount=105.0,
        price=10.0,
        prices=prices,
        policy=PortfolioPolicy(),
    )

    assert preview.valid is True
    assert preview.executable_units == 10
    assert preview.executed_notional == pytest.approx(100.0)
    assert preview.cash_after == pytest.approx(900.0)
    assert preview.holding_after == 12
    assert account == original


def test_settlement_changes_only_selected_asset_and_cash():
    account = AccountState(cash=1000.0, positions={"TLEI": 2, "FSEI": 3})
    prices = {"TLEI": 10.0, "FSEI": 20.0}
    preview = preview_order(
        account=account,
        stock_id="TLEI",
        action=PortfolioAction.BUY,
        requested_amount=100.0,
        price=10.0,
        prices=prices,
        policy=PortfolioPolicy(),
    )

    result = execute_preview(account, preview)

    assert result.cash == pytest.approx(900.0)
    assert result.positions["TLEI"] == 12
    assert result.positions["FSEI"] == 3
    assert account.positions == {"TLEI": 2, "FSEI": 3}


def test_sell_returns_cash_and_leaves_other_holdings_untouched():
    account = AccountState(cash=100.0, positions={"TLEI": 10, "FSEI": 3})
    prices = {"TLEI": 10.0, "FSEI": 20.0}
    preview = preview_order(
        account=account,
        stock_id="TLEI",
        action=PortfolioAction.SELL,
        requested_amount=40.0,
        price=10.0,
        prices=prices,
        policy=PortfolioPolicy(),
    )
    result = execute_preview(account, preview)

    assert result.cash == pytest.approx(140.0)
    assert result.positions["TLEI"] == 6
    assert result.positions["FSEI"] == 3


def test_whole_unit_flooring_preserves_requested_vs_executed_values():
    account = AccountState(cash=1000.0, positions={})
    preview = preview_order(
        account=account,
        stock_id="TLEI",
        action=PortfolioAction.BUY,
        requested_amount=105.0,
        price=10.0,
        prices={"TLEI": 10.0},
        policy=PortfolioPolicy(),
    )

    assert preview.requested_amount == pytest.approx(105.0)
    assert preview.requested_units == pytest.approx(10.5)
    assert preview.executable_units == 10
    assert preview.executed_notional == pytest.approx(100.0)


def test_overspend_is_invalid_and_is_not_silently_clamped():
    preview = preview_order(
        account=AccountState(cash=100.0, positions={}),
        stock_id="TLEI",
        action=PortfolioAction.BUY,
        requested_amount=101.0,
        price=10.0,
        prices={"TLEI": 10.0},
        policy=PortfolioPolicy(),
    )

    assert preview.valid is False
    assert preview.reason_code == PreviewReason.INSUFFICIENT_CASH
    assert preview.executable_units == 0
    assert preview.maximum_valid_amount == pytest.approx(100.0)


def test_oversell_is_invalid_and_is_not_silently_clamped():
    preview = preview_order(
        account=AccountState(cash=100.0, positions={"TLEI": 10}),
        stock_id="TLEI",
        action=PortfolioAction.SELL,
        requested_amount=101.0,
        price=10.0,
        prices={"TLEI": 10.0},
        policy=PortfolioPolicy(),
    )

    assert preview.valid is False
    assert preview.reason_code == PreviewReason.INSUFFICIENT_HOLDINGS
    assert preview.maximum_valid_amount == pytest.approx(100.0)


def test_amount_below_one_whole_unit_is_invalid():
    preview = preview_order(
        account=AccountState(cash=1000.0, positions={}),
        stock_id="TLEI",
        action=PortfolioAction.BUY,
        requested_amount=9.99,
        price=10.0,
        prices={"TLEI": 10.0},
        policy=PortfolioPolicy(),
    )
    assert preview.valid is False
    assert preview.reason_code == PreviewReason.BELOW_ONE_UNIT


def test_transaction_fee_is_applied_deterministically():
    preview = preview_order(
        account=AccountState(cash=1000.0, positions={}),
        stock_id="TLEI",
        action=PortfolioAction.BUY,
        requested_amount=100.0,
        price=10.0,
        prices={"TLEI": 10.0},
        policy=PortfolioPolicy(transaction_cost_bps=10.0),
    )

    assert preview.executed_notional == pytest.approx(100.0)
    assert preview.fee == pytest.approx(0.10)
    assert preview.cash_after == pytest.approx(899.90)
    assert preview.portfolio_value_after == pytest.approx(999.90)


def test_optional_position_cap_rejects_request_instead_of_projecting_it():
    preview = preview_order(
        account=AccountState(cash=1000.0, positions={}),
        stock_id="TLEI",
        action=PortfolioAction.BUY,
        requested_amount=300.0,
        price=10.0,
        prices={"TLEI": 10.0},
        policy=PortfolioPolicy(max_position_weight=0.20),
    )

    assert preview.valid is False
    assert preview.reason_code == PreviewReason.POSITION_LIMIT
    assert preview.maximum_valid_amount == pytest.approx(200.0)


def test_same_input_produces_same_preview():
    kwargs = dict(
        account=AccountState(cash=1000.0, positions={"TLEI": 5}),
        stock_id="TLEI",
        action=PortfolioAction.BUY,
        requested_amount=123.0,
        price=10.0,
        prices={"TLEI": 10.0},
        policy=PortfolioPolicy(transaction_cost_bps=10.0),
    )
    assert preview_order(**kwargs) == preview_order(**kwargs)
