from __future__ import annotations

from pathlib import Path

from marketlens.market.multiday_n20_real import (
    ACTIVATION_SEED,
    EXPECTED_ACTIVE_IDS,
    EXPECTED_DATES,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_MARKET_OPEN,
    EXPECTED_RUNTIME_SHA256,
    POPULATION_SIZE,
    validate_n20_real_summary,
)


def _summary(*, forum=True, closed_active=True):
    return {
        "population": {"size": 20},
        "horizon": {
            "dates": list(EXPECTED_DATES),
            "market_open": list(EXPECTED_MARKET_OPEN),
        },
        "integrity": {
            "protected_sources_unchanged": True,
            "verified_n20_fixture_unchanged": True,
            "participant_data_used": False,
            "custom_market_logic_used": False,
            "custom_forum_logic_used": False,
            "custom_belief_logic_used": False,
        },
        "continuity": {
            "activation_state_chain_valid": True,
            "all_graphs_bounded_n20": True,
            "same_working_runtime_across_all_days": True,
            "same_working_forum_across_all_days": True,
        },
        "days": [
            {
                "agent_world_date": EXPECTED_DATES[0],
                "market_open": True,
                "reasoning": {"active_agents": 5, "failed_agents": 0},
                "post_day_validation_failures": [],
            },
            {
                "agent_world_date": EXPECTED_DATES[1],
                "market_open": True,
                "reasoning": {"active_agents": 3, "failed_agents": 0},
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


def test_contract_reuses_verified_n20_fixture_and_phase9b_seed():
    assert POPULATION_SIZE == 20
    assert ACTIVATION_SEED == "marketlens-phase09b-activation-01"
    assert EXPECTED_DATES == ("2023-06-15", "2023-06-16", "2023-06-17")
    assert EXPECTED_MARKET_OPEN == (True, True, False)
    assert [len(day) for day in EXPECTED_ACTIVE_IDS] == [5, 3, 3]


def test_verified_fixture_hashes_are_frozen_reference_values():
    assert EXPECTED_RUNTIME_SHA256 == (
        "b617769f590cadb00b0db28f80ec78bfd3b620f0f06bbc0bb254030ea3cb2d9c"
    )
    assert EXPECTED_MANIFEST_SHA256 == (
        "da18bff98886c218f69c65960ad3246b3a207bb89c467c122bf6fa50d549a0c8"
    )


def test_real_summary_passes_expected_n20_multiday_coverage():
    status, reasons = validate_n20_real_summary(_summary())
    assert status == "PASS"
    assert reasons == []


def test_missing_forum_belief_coverage_is_inconclusive_not_silently_passed():
    status, reasons = validate_n20_real_summary(_summary(forum=False))
    assert status == "INCONCLUSIVE_NATURAL_MULTIDAY_COVERAGE"
    assert reasons


def test_closed_day_without_active_agent_is_inconclusive():
    status, reasons = validate_n20_real_summary(_summary(closed_active=False))
    assert status == "INCONCLUSIVE_NATURAL_MULTIDAY_COVERAGE"
    assert any("closed day" in reason for reason in reasons)


def test_integrity_failure_is_fail():
    summary = _summary()
    summary["integrity"]["verified_n20_fixture_unchanged"] = False
    status, reasons = validate_n20_real_summary(summary)
    assert status == "FAIL"
    assert reasons


def test_source_contains_no_population_regeneration_or_direct_matching():
    source = Path("marketlens/market/multiday_n20_real.py").read_text(encoding="utf-8")
    assert "runtime_cli" not in source
    assert "test_matching_system(" not in source
    assert "calculate_closing_price(" not in source
    assert "advance_trading_day(" in source
    assert "advance_non_trading_day(" in source


def test_runner_does_not_expose_population_size_or_date_override():
    source = Path("scripts/preflight/run_phase09c_n20_multiday_validation.py").read_text(
        encoding="utf-8"
    )
    assert "--population-size" not in source
    assert "--start-date" not in source
    assert "--end-date" not in source
