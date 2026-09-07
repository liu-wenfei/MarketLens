from __future__ import annotations

import pytest

from marketlens.human.portfolio.preview import PortfolioAction
from marketlens.validation.cash_only_account import (
    CashEndowmentProfile,
    CashOnlyValidationConfig,
    build_initial_account,
    deterministic_stress_paths,
    granularity_probe_rows,
    monte_carlo_resolution_summary,
    run_deterministic_path,
)

ASSETS = ("CGEI","CPEI","EREI","FSEI","IEEI","MEI","REEI","TLEI","TSEI","TTEI")
DATES = (
    "2023-06-19","2023-06-20","2023-06-21","2023-06-26","2023-06-27",
    "2023-06-28","2023-06-29","2023-06-30","2023-07-03","2023-07-04",
    "2023-07-05","2023-07-06","2023-07-07","2023-07-10","2023-07-11",
)


def profile(cash: float) -> CashEndowmentProfile:
    return CashEndowmentProfile(
        profile_id=f"cash-{int(cash)}",
        initial_cash=cash,
        transaction_cost_bps=10.0,
        max_position_weight=None,
    )


def cfg(p: CashEndowmentProfile) -> CashOnlyValidationConfig:
    return CashOnlyValidationConfig(
        family_id="test",
        family_description="test",
        target_stock_id="MEI",
        asset_ids=ASSETS,
        period_dates=DATES,
        critical_periods=frozenset({1,8,15}),
        order_fraction_probes=(0.01,0.025,0.05,0.10),
        profiles=(p,),
    )


def matrix(price: float = 100.0):
    return {date: {asset: price for asset in ASSETS} for date in DATES}


def test_initial_account_is_cash_only():
    p = profile(100000)
    account = build_initial_account(p)
    assert account.cash == pytest.approx(100000)
    assert account.positions == {}


def test_endowment_sweep_has_no_position_cap():
    p = profile(100000)
    policy = p.policy()
    assert policy.max_position_weight is None
    assert policy.transaction_cost_bps == pytest.approx(10.0)
    assert policy.whole_units is True
    assert policy.allow_short is False
    assert policy.allow_leverage is False


def test_higher_cash_improves_whole_unit_resolution():
    low = profile(10000)
    high = profile(100000)
    low_rows = granularity_probe_rows(
        profile=low, episode_id="e", price_matrix=matrix(333), config=cfg(low)
    )
    high_rows = granularity_probe_rows(
        profile=high, episode_id="e", price_matrix=matrix(333), config=cfg(high)
    )
    assert max(r["one_unit_fraction_pp"] for r in high_rows) < max(
        r["one_unit_fraction_pp"] for r in low_rows
    )


def test_research_path_starts_empty_and_can_buy():
    p = profile(100000)
    c = cfg(p)
    summary, rows = run_deterministic_path(
        profile=p,
        episode_id="e",
        price_matrix=matrix(100),
        config=c,
        path_id="focal",
        intents=deterministic_stress_paths(c)["focal_buy10_p1"],
    )
    assert summary["orders_requested"] == 1
    assert summary["orders_executed"] == 1
    assert rows[0]["holding_before"] == 0
    assert rows[0]["action"] == PortfolioAction.BUY.value


def test_same_resolution_probe_space_improves_with_more_cash():
    probes = [(1,"MEI",0.01),(8,"FSEI",0.025),(15,"TLEI",0.05)]
    low = profile(10000)
    high = profile(100000)
    low_r = monte_carlo_resolution_summary(
        profile=low, episode_id="e", price_matrix=matrix(333), config=cfg(low), probes=probes
    )
    high_r = monte_carlo_resolution_summary(
        profile=high, episode_id="e", price_matrix=matrix(333), config=cfg(high), probes=probes
    )
    assert high_r["mean_shortfall_fraction_of_initial_wealth"] < low_r[
        "mean_shortfall_fraction_of_initial_wealth"
    ]
