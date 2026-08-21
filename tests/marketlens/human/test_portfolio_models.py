from __future__ import annotations

import pytest

from marketlens.human.portfolio.models import AccountState, DEFAULT_DEV_INITIAL_CASH


def test_empty_account_uses_explicit_development_default_only():
    account = AccountState.empty()
    assert account.cash == pytest.approx(DEFAULT_DEV_INITIAL_CASH)
    assert account.positions == {}


def test_account_value_and_weights_are_deterministic():
    account = AccountState(cash=1000.0, positions={"TLEI": 10, "FSEI": 20})
    prices = {"TLEI": 10.0, "FSEI": 20.0}

    assert account.total_value(prices) == pytest.approx(1500.0)
    assert account.weights(prices) == {
        "TLEI": pytest.approx(100.0 / 1500.0),
        "FSEI": pytest.approx(400.0 / 1500.0),
    }


def test_account_copy_does_not_share_positions_mapping():
    original = AccountState(cash=1000.0, positions={"TLEI": 1})
    copied = original.copy()

    copied.positions["TLEI"] = 99
    assert original.positions["TLEI"] == 1
