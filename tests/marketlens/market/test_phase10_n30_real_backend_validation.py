from __future__ import annotations

from pathlib import Path

from marketlens.market.phase10_n30_real_validation import (
    ACTIVATION_SEED,
    EXPECTED_ACTIVE_IDS,
    EXPECTED_DATES,
    EXPECTED_MARKET_OPEN,
    EXPECTED_ROW_COUNTS,
    EXPECTED_TABLE_DIGESTS_SHA256,
    EXPECTED_SELECTED_IDS_SHA256,
    POPULATION_SEED,
    POPULATION_SIZE,
    extract_phase6_top_user_ids,
    validate_n30_real_summary,
)


def _summary(*, forum: bool = True, closed_active: bool = True):
    return {
        "population": {"size": 30},
        "horizon": {
            "dates": list(EXPECTED_DATES),
            "market_open": list(EXPECTED_MARKET_OPEN),
        },
        "integrity": {
            "protected_sources_unchanged": True,
            "candidate_n30_fixture_unchanged": True,
            "participant_data_used": False,
            "custom_market_logic_used": False,
            "custom_forum_logic_used": False,
            "custom_belief_logic_used": False,
        },
        "continuity": {
            "activation_state_chain_valid": True,
            "all_graphs_bounded_n30": True,
            "same_working_runtime_across_all_days": True,
            "same_working_forum_across_all_days": True,
        },
        "days": [
            {
                "agent_world_date": EXPECTED_DATES[0],
                "market_open": True,
                "reasoning": {"active_agents": 10, "failed_agents": 0},
                "post_day_validation_failures": [],
            },
            {
                "agent_world_date": EXPECTED_DATES[1],
                "market_open": True,
                "reasoning": {"active_agents": 7, "failed_agents": 0},
                "post_day_validation_failures": [],
            },
            {
                "agent_world_date": EXPECTED_DATES[2],
                "market_open": False,
                "reasoning": {
                    "active_agents": 3 if closed_active else 0,
                    "failed_agents": 0,
                },
                "post_day_validation_failures": [],
            },
        ],
        "natural_multiday_coverage": {
            "posts_created_total": 2 if forum else 0,
            "forum_belief_agents_observed": 1 if forum else 0,
            "later_day_forum_action_calls": 1 if forum else 0,
        },
    }


def test_n30_contract_is_fixed_before_paid_validation():
    assert POPULATION_SIZE == 30
    assert POPULATION_SEED == "marketlens-dev-population-01"
    assert ACTIVATION_SEED == "marketlens-phase09b-activation-01"
    assert EXPECTED_DATES == ("2023-06-15", "2023-06-16", "2023-06-17")
    assert EXPECTED_MARKET_OPEN == (True, True, False)
    assert [len(day) for day in EXPECTED_ACTIVE_IDS] == [10, 7, 3]
    assert sum(len(day) for day in EXPECTED_ACTIVE_IDS) == 20


def test_n30_phase9e_membership_and_semantic_fixture_reference_are_frozen():
    assert EXPECTED_SELECTED_IDS_SHA256 == (
        "60d846b21c15e2213f6f897a17a7ea98039fbf461abe54ee89e1b6779d24b2d4"
    )
    assert EXPECTED_ROW_COUNTS["Profiles"] == 30
    assert EXPECTED_ROW_COUNTS["TradingDetails"] == 1304
    assert EXPECTED_TABLE_DIGESTS_SHA256["Profiles"] == (
        "a9c59d685756ef8370d9bf7a9460bdbd593c4ffd96ac3061c59e83cb5385ff27"
    )
    assert EXPECTED_TABLE_DIGESTS_SHA256["StockData"] == (
        "80d31d17c0e8fade532194e6e9afb465615b885495f31b398a69b8b9649bb542"
    )



def test_rebuilt_n30_candidate_matches_frozen_semantic_reference(tmp_path):
    from marketlens.agents.population.fixture import build_population_bundle

    manifest = build_population_bundle(
        source_db=Path("data/sys_1000.db"),
        population_size=POPULATION_SIZE,
        seed=POPULATION_SEED,
        output_dir=tmp_path / "n30",
    )
    assert manifest["selection"]["selected_agent_ids_sha256"] == EXPECTED_SELECTED_IDS_SHA256
    assert manifest["runtime_fixture"]["row_counts"] == EXPECTED_ROW_COUNTS
    assert (
        manifest["runtime_fixture"]["table_digests_sha256"]
        == EXPECTED_TABLE_DIGESTS_SHA256
    )

def test_real_summary_passes_expected_n30_multiday_coverage():
    status, reasons = validate_n30_real_summary(_summary())
    assert status == "PASS"
    assert reasons == []


def test_missing_natural_forum_coverage_is_inconclusive_not_retried_by_seed():
    status, reasons = validate_n30_real_summary(_summary(forum=False))
    assert status == "INCONCLUSIVE_NATURAL_MULTIDAY_COVERAGE"
    assert reasons


def test_closed_day_without_active_agent_is_inconclusive():
    status, reasons = validate_n30_real_summary(_summary(closed_active=False))
    assert status == "INCONCLUSIVE_NATURAL_MULTIDAY_COVERAGE"
    assert any("closed day" in reason for reason in reasons)


def test_integrity_failure_is_fail():
    summary = _summary()
    summary["integrity"]["candidate_n30_fixture_unchanged"] = False
    status, reasons = validate_n30_real_summary(summary)
    assert status == "FAIL"
    assert reasons


def test_runner_exposes_no_population_seed_or_date_override():
    source = Path(
        "scripts/preflight/run_phase10_n30_real_backend_validation.py"
    ).read_text(encoding="utf-8")
    assert "--population-size" not in source
    assert "--seed" not in source
    assert "--start-date" not in source
    assert "--end-date" not in source


def test_real_runner_does_not_regenerate_population_or_reimplement_market_logic():
    source = Path("marketlens/market/phase10_n30_real_validation.py").read_text(
        encoding="utf-8"
    )
    assert "build_population_bundle(" not in source
    assert "runtime_cli" not in source
    assert "test_matching_system(" not in source
    assert "calculate_closing_price(" not in source
    assert "advance_trading_day(" in source
    assert "advance_non_trading_day(" in source
    assert "simulation.process_user_input" in source


def test_phase6_top_users_are_read_from_nested_prominence_record():
    snapshot = {
        "prominence": {
            "top_n": 3,
            "top_user_ids": ["1", "2", "3"],
        },
    }
    assert extract_phase6_top_user_ids(snapshot, expected_top_n=3) == (
        "1",
        "2",
        "3",
    )
