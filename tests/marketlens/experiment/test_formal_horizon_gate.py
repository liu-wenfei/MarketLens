from __future__ import annotations

from pathlib import Path

from marketlens.agents.population.fixture import build_population_bundle
from marketlens.experiment.formal_horizon import (
    decide_population,
    evaluate_candidate,
    formal_horizon_seeds,
)
from marketlens.experiment.protocol import load_protocol


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_formal_horizon_seed_grid_is_predeclared_and_complete():
    seeds = formal_horizon_seeds(load_protocol())
    assert len(seeds) == 100
    assert seeds[0] == "marketlens-phase10-formal-horizon-activation-000"
    assert seeds[-1] == "marketlens-phase10-formal-horizon-activation-099"
    assert len(set(seeds)) == 100


def test_exact_horizon_comparison_uses_full_14_tick_state_carry_forward(tmp_path):
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
        assert outcomes[n].n_world_ticks == 14
        assert outcomes[n].n_seeds == 100
        assert set(outcomes[n].critical_date_mean_active) == set(
            protocol["participant_critical_dates"]
        )

    decision = decide_population(outcomes[20], outcomes[30])
    assert decision["decision"] in {
        "SELECT_N20",
        "N30_REQUIRES_NARROW_REAL_VALIDATION",
        "NO_CANDIDATE_SUFFICIENT",
    }
    if outcomes[20].sufficient:
        assert decision["decision"] == "SELECT_N20"
        assert decision["final_n"] == 20
