from __future__ import annotations

from pathlib import Path

import pytest

from marketlens.market.population_sensitivity import (
    ACTIVATION_GRID_SEEDS,
    ACTIVATION_GRID_SIZE,
    EXPECTED_DATES,
    EXPECTED_MARKET_OPEN,
    POPULATION_SEED,
    POPULATION_SIZES,
    REFERENCE_ACTIVATION_SEED,
    marginal_comparison,
    nested_membership_report,
    summarize_activation_windows,
)


def test_contract_is_fixed_before_results():
    assert POPULATION_SIZES == (10, 20, 30, 40)
    assert POPULATION_SEED == "marketlens-dev-population-01"
    assert REFERENCE_ACTIVATION_SEED == "marketlens-phase09b-activation-01"
    assert ACTIVATION_GRID_SIZE == 100
    assert len(ACTIVATION_GRID_SEEDS) == 100
    assert len(set(ACTIVATION_GRID_SEEDS)) == 100
    assert ACTIVATION_GRID_SEEDS[0].endswith("-000")
    assert ACTIVATION_GRID_SEEDS[-1].endswith("-099")
    assert EXPECTED_DATES == ("2023-06-15", "2023-06-16", "2023-06-17")
    assert EXPECTED_MARKET_OPEN == (True, True, False)


def test_activation_summary_keeps_all_zero_events():
    result = summarize_activation_windows(
        population_size=10,
        windows=[[0, 2, 0], [1, 1, 1], [2, 0, 1], [1, 2, 3]],
    )
    assert result["zero_active_day_frequency"] == pytest.approx(3 / 12)
    assert result["window_with_any_zero_active_day_frequency"] == pytest.approx(2 / 4)
    assert result["window_with_all_days_active_frequency"] == pytest.approx(2 / 4)
    assert result["closed_day_active_frequency"] == pytest.approx(3 / 4)


def test_activation_density_uses_all_agent_day_slots():
    result = summarize_activation_windows(
        population_size=20, windows=[[5, 3, 3], [4, 4, 2]]
    )
    assert result["activation_density"] == pytest.approx(21 / 120)
    assert result["mean_active_agent_days_per_3day_window"] == pytest.approx(10.5)


def test_nested_membership_detects_expanding_family():
    rows = {
        10: {"selected_agent_ids": [str(i) for i in range(10)]},
        20: {"selected_agent_ids": [str(i) for i in range(20)]},
        30: {"selected_agent_ids": [str(i) for i in range(30)]},
        40: {"selected_agent_ids": [str(i) for i in range(40)]},
    }
    assert nested_membership_report(rows)["strict_nested_family"] is True


def test_non_nested_membership_is_reported_not_repaired():
    rows = {
        10: {"selected_agent_ids": [str(i) for i in range(10)]},
        20: {"selected_agent_ids": [str(i) for i in range(10, 30)]},
        30: {"selected_agent_ids": [str(i) for i in range(30)]},
        40: {"selected_agent_ids": [str(i) for i in range(40)]},
    }
    assert nested_membership_report(rows)["strict_nested_family"] is False


def _row(active, zero, closed, edges, density, user_types=1):
    return {
        "population": {"n_user_types_observed": user_types},
        "graph": {"n_edges": edges, "density": density},
        "activation": {
            "aggregate": {
                "mean_active_agent_days_per_3day_window": active,
                "window_with_any_zero_active_day_frequency": zero,
                "closed_day_active_frequency": closed,
            }
        },
    }


def test_marginal_comparison_uses_workload_proxy_not_backend_calls():
    rows = {
        10: _row(4, .6, .7, 10, .22),
        20: _row(8, .2, .9, 46, .24),
        30: _row(12, .1, .95, 90, .21),
        40: _row(16, .05, .98, 150, .19),
    }
    result = marginal_comparison(rows, 20, 30)
    assert result["population_increase_fraction"] == pytest.approx(.5)
    assert result["mean_active_agent_days_per_window"]["increase_fraction"] == pytest.approx(.5)
    assert "not an HTTP/backend-call count" in result["note"]


def test_source_contains_no_agent_reasoning_or_market_execution():
    source = Path("marketlens/market/population_sensitivity.py").read_text(
        encoding="utf-8"
    )
    assert "process_user_input" not in source
    assert "advance_trading_day(" not in source
    assert "advance_non_trading_day(" not in source
    assert "chat/completions" not in source


def test_runner_does_not_offer_size_or_seed_cherry_picking():
    source = Path(
        "scripts/preflight/run_phase09e_population_sensitivity.py"
    ).read_text(encoding="utf-8")
    assert "--population-size" not in source
    assert "--activation-seed" not in source
    assert "--grid-size" not in source
