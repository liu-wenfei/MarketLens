from __future__ import annotations

from pathlib import Path

import pandas as pd

from marketlens.agents.population.fixture import build_population_bundle
from marketlens.experiment.formal_horizon import (
    decide_population,
    evaluate_candidate,
    evaluate_warm_up_candidates,
    formal_horizon_seeds,
    select_warm_up,
)
from marketlens.experiment.protocol import load_protocol


REPO_ROOT = Path(__file__).resolve().parents[3]


def _calendar_and_news_dates() -> tuple[set[str], set[str]]:
    calendar = pd.read_csv(REPO_ROOT / "data" / "trading_days.csv")
    opens = {
        pd.Timestamp(value).date().isoformat()
        for value in calendar["pretrade_date"].dropna().tolist()
    }
    news = pd.read_pickle(REPO_ROOT / "data" / "sorted_impact_news.pkl")
    news_dates = {
        pd.Timestamp(value).date().isoformat()
        for value in news["cal_date"].tolist()
    }
    return opens, news_dates


def test_formal_horizon_seed_grid_is_predeclared_and_complete():
    seeds = formal_horizon_seeds(load_protocol())
    assert len(seeds) == 100
    assert seeds[0] == "marketlens-phase10-formal-horizon-activation-000"
    assert seeds[-1] == "marketlens-phase10-formal-horizon-activation-099"
    assert len(set(seeds)) == 100


def test_warm_up_structural_gate_selects_w4_as_smallest_sufficient_candidate():
    protocol = load_protocol()
    opens, news_dates = _calendar_and_news_dates()
    results = evaluate_warm_up_candidates(
        protocol=protocol,
        trading_open_dates=opens,
        news_dates=news_dates,
    )
    assert [(value.calendar_days, value.sufficient) for value in results] == [
        (2, False),
        (3, False),
        (4, True),
        (5, True),
        (6, True),
    ]
    selected = select_warm_up(results, protocol)
    assert selected.calendar_days == 4
    assert selected.visible_date == "2023-06-19"
    assert selected.open_ticks_before_entry == 2
    assert selected.closed_ticks_before_entry == 2


def test_exact_horizon_comparison_uses_full_27_tick_state_carry_forward(tmp_path):
    protocol = load_protocol()
    outcomes = {}
    for n in (20, 30):
        bundle = tmp_path / f"n{n}"
        build_population_bundle(
            source_db=REPO_ROOT / "data" / "sys_1000.db",
            population_size=n,
            seed="marketlens-dev-population-01",
            output_dir=bundle,
        )
        outcomes[n] = evaluate_candidate(
            runtime_db=bundle / "population_runtime.db",
            population_size=n,
            protocol=protocol,
        )
        assert outcomes[n].n_world_ticks == 27
        assert outcomes[n].n_seeds == 100
        assert set(outcomes[n].critical_date_mean_active) == set(
            protocol["participant_critical_dates"]
        )

    assert outcomes[20].sufficient is False
    assert outcomes[20].critical_any_zero_trajectories == 9
    assert outcomes[20].minimum_critical_mean_active == 3.88
    assert outcomes[30].sufficient is True
    assert outcomes[30].critical_any_zero_trajectories == 0
    assert outcomes[30].minimum_critical_mean_active == 6.26

    pending = decide_population(outcomes[20], outcomes[30])
    assert pending["decision"] == "N30_REQUIRES_NARROW_REAL_VALIDATION"
    assert pending["final_n"] is None
    assert pending["requires_n30_real_validation"] is True

    decision = decide_population(
        outcomes[20],
        outcomes[30],
        n30_real_backend_validated=True,
    )
    assert decision["decision"] == "SELECT_N30"
    assert decision["final_n"] == 30
    assert decision["requires_n30_real_validation"] is False


def test_population_gate_thresholds_are_predeclared_in_protocol():
    rule = load_protocol()["population"]["selection_rule"]
    assert rule["critical_date_any_zero_max_trajectories"] == 5
    assert rule["critical_date_min_mean_active_agents"] == 3.0
    assert rule["full_horizon_state_carry_forward"] is True
    assert rule["parsimony"] == "choose_smallest_sufficient_population"


def test_generated_preflight_report_states_predeclared_gate_thresholds():
    from scripts.preflight.run_phase10_formal_horizon_population_gate import markdown_report

    summary = {
        "banner": "NON-FORMAL",
        "status": "PASS",
        "git": {"commit": "abc", "status_porcelain": ""},
        "protocol": {
            "T_init": "2023-06-15",
            "warm_up_calendar_days": 4,
            "T_visible": "2023-06-19",
            "T_end": "2023-07-11",
            "formal_world_ticks": 27,
            "participant_decision_days": 15,
            "formal_judgement_events": 5,
            "formal_judgement_dates": 3,
            "participant_critical_dates": ["2023-06-19"],
        },
        "warm_up_gate": {
            "candidates": [
                {
                    "calendar_days": 4,
                    "visible_date": "2023-06-19",
                    "sufficient": True,
                    "open_ticks_before_entry": 2,
                    "closed_ticks_before_entry": 2,
                    "visible_date_open": True,
                    "news_coverage_complete": True,
                }
            ],
            "selected": {"calendar_days": 4, "visible_date": "2023-06-19"},
        },
        "population_gate": {
            "critical_date_any_zero_max_trajectories": 5,
            "critical_date_min_mean_active_agents": 3.0,
        },
        "candidates": {
            "20": {
                "sufficient": False,
                "critical_any_zero_trajectories": 9,
                "n_seeds": 100,
                "minimum_critical_mean_active": 3.88,
                "overall_mean_active": 4.07,
            },
            "30": {
                "sufficient": True,
                "critical_any_zero_trajectories": 0,
                "n_seeds": 100,
                "minimum_critical_mean_active": 6.26,
                "overall_mean_active": 6.68,
            },
        },
        "decision": {"decision": "SELECT_N30", "reason": "N30 real-backend PASS already recorded"},
    }
    report = markdown_report(summary)
    assert "<= 5/100" in report
    assert ">= 3.0" in report
    assert "smallest sufficient candidate" in report
