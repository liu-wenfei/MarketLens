from __future__ import annotations

import json

import pytest

from marketlens.human.portfolio.formal_account import (
    FORMAL_PARTICIPANT_ACCOUNT,
    FORMAL_PARTICIPANT_ACCOUNT_CONFIG_PATH,
    FormalParticipantAccountError,
    assert_formal_participant_account_runtime,
    load_formal_participant_account,
)
from marketlens.human.portfolio.models import (
    AccountState,
    DEFAULT_DEV_INITIAL_CASH,
)
from marketlens.human.portfolio.policy import PortfolioPolicy


def test_formal_manifest_freezes_cash_only_account():
    raw = json.loads(
        FORMAL_PARTICIPANT_ACCOUNT_CONFIG_PATH.read_text(encoding="utf-8")
    )
    assert raw["profile_id"] == "marketlens-participant-cash-only-v1"
    assert raw["status"] == "formal_frozen"
    assert raw["initial_cash"] == pytest.approx(10_000.0)
    assert raw["initial_holdings"] == {}
    assert raw["transaction_cost_bps"] == pytest.approx(0.0)
    assert raw["max_position_weight"] is None
    assert raw["whole_units"] is True
    assert raw["allow_short"] is False
    assert raw["allow_leverage"] is False


def test_current_engineering_defaults_match_formal_freeze():
    account = AccountState.empty()
    policy = PortfolioPolicy()

    assert DEFAULT_DEV_INITIAL_CASH == pytest.approx(
        FORMAL_PARTICIPANT_ACCOUNT.initial_cash
    )
    assert account.cash == pytest.approx(
        FORMAL_PARTICIPANT_ACCOUNT.initial_cash
    )
    assert account.positions == {}

    assert_formal_participant_account_runtime(
        initial_cash=DEFAULT_DEV_INITIAL_CASH,
        policy=policy,
    )


@pytest.mark.parametrize(
    ("initial_cash", "policy"),
    [
        (9_999.0, PortfolioPolicy()),
        (10_000.0, PortfolioPolicy(transaction_cost_bps=10.0)),
        (
            10_000.0,
            PortfolioPolicy(max_position_weight=0.20),
        ),
    ],
)
def test_formal_runtime_assertion_rejects_parameter_drift(
    initial_cash,
    policy,
):
    with pytest.raises(
        FormalParticipantAccountError,
        match="runtime drift",
    ):
        assert_formal_participant_account_runtime(
            initial_cash=initial_cash,
            policy=policy,
        )


def test_manifest_loader_rejects_nonempty_initial_holdings(
    tmp_path,
):
    raw = json.loads(
        FORMAL_PARTICIPANT_ACCOUNT_CONFIG_PATH.read_text(encoding="utf-8")
    )
    raw["initial_holdings"] = {"MEI": 1}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(
        FormalParticipantAccountError,
        match="no holdings",
    ):
        load_formal_participant_account(path)
