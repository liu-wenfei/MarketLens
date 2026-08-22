from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from marketlens.market.multiday_real import (
    EXPECTED_DATES,
    EXPECTED_MARKET_OPEN,
    POPULATION_SIZE,
    activation_state_digest,
    build_forum_belief_args,
    capture_runtime_metrics,
    fixed_dates,
    make_activation_mapping,
    validate_real_summary,
    write_daily_records,
)


def test_phase09c_contract_is_hard_limited_to_n10_three_calendar_days():
    assert POPULATION_SIZE == 10
    assert fixed_dates() == EXPECTED_DATES
    assert EXPECTED_MARKET_OPEN == (True, True, False)


def test_activation_mapping_rejects_out_of_population_agent():
    population = ("1", "2")
    try:
        make_activation_mapping(population, ("3",))
    except Exception as exc:
        assert "outside bounded N10 population" in str(exc)
    else:
        raise AssertionError("expected safety error")


def test_activation_mapping_marks_only_active_ids():
    assert make_activation_mapping(("1", "2", "3"), ("2",)) == {
        "1": False,
        "2": True,
        "3": False,
    }


def test_activation_state_digest_is_stable_for_mapping_order():
    class State:
        steps_since_last_activation = {"2": 3, "1": 1}

    class State2:
        steps_since_last_activation = {"1": 1, "2": 3}

    assert activation_state_digest(State()) == activation_state_digest(State2())


def test_forum_belief_args_prefers_forum_and_falls_back_to_initial(tmp_path: Path):
    initial = pd.DataFrame(
        [
            {"user_id": "1", "belief": 0.1},
            {"user_id": "2", "belief": 0.2},
            {"user_id": "3", "belief": 0.3},
        ]
    )

    def reader(**kwargs):
        assert kwargs["db_path"].endswith("forum.db")
        return {
            1: [{"belief": 0.9}],
            2: [{"content": "missing belief"}],
        }

    mapping, stats = build_forum_belief_args(
        forum_db=tmp_path / "forum.db",
        current_date=pd.Timestamp("2023-06-16"),
        initial_beliefs=initial,
        population_ids=("1", "2", "3"),
        forum_reader=reader,
    )
    assert mapping["1"][0]["belief"] == 0.9
    assert mapping["2"][0]["belief"] == 0.2
    assert mapping["3"][0]["belief"] == 0.3
    assert stats == {
        "population": 3,
        "forum_with_belief": 1,
        "fallback_no_post": 1,
        "fallback_missing_belief": 1,
    }


def test_daily_record_writer_uses_twinmarket_record_families(tmp_path: Path):
    written = write_daily_records(
        log_dir=tmp_path,
        current_date="2023-06-15",
        agent_results=[
            {
                "user_id": "1",
                "decision_result": {"x": 1},
                "forum_args": {"y": 2},
                "post_response_args": {"z": 3},
            }
        ],
    )
    assert set(written) == {"trading_records", "reaction_records", "post_records"}
    for path in written.values():
        assert Path(path).is_file()


def test_capture_runtime_metrics_counts_rows_by_date(tmp_path: Path):
    db = tmp_path / "runtime.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE Profiles (user_id TEXT, created_at TEXT)")
        conn.execute("CREATE TABLE StockData (ts_code TEXT, date TEXT)")
        conn.execute("CREATE TABLE TradingDetails (user_id TEXT, created_at TEXT)")
        conn.execute("INSERT INTO Profiles VALUES ('1', '2023-06-15 00:00:00')")
        conn.execute("INSERT INTO StockData VALUES ('X', '2023-06-15 00:00:00')")
        conn.commit()
    metrics = capture_runtime_metrics(db, "2023-06-15")
    assert metrics["Profiles"]["rows_for_date"] == 1
    assert metrics["StockData"]["rows_for_date"] == 1
    assert metrics["TradingDetails"]["rows_for_date"] == 0


def _summary(*, forum_coverage: bool = True):
    return {
        "population": {"size": 10},
        "horizon": {
            "dates": list(EXPECTED_DATES),
            "market_open": list(EXPECTED_MARKET_OPEN),
        },
        "integrity": {
            "protected_sources_unchanged": True,
            "generated_fixture_unchanged": True,
            "participant_data_used": False,
            "custom_market_logic_used": False,
        },
        "continuity": {
            "activation_state_chain_valid": True,
            "all_graphs_bounded_n10": True,
        },
        "days": [
            {"agent_world_date": d, "post_day_validation_failures": [], "reasoning": {"failed_agents": 0}}
            for d in EXPECTED_DATES
        ],
        "natural_multiday_coverage": {
            "posts_created_total": 1 if forum_coverage else 0,
            "forum_belief_agents_observed": 1 if forum_coverage else 0,
            "later_day_forum_action_calls": 1 if forum_coverage else 0,
        },
    }


def test_validate_real_summary_passes_complete_natural_coverage():
    status, reasons = validate_real_summary(_summary())
    assert status == "PASS"
    assert reasons == []


def test_validate_real_summary_marks_missing_forum_belief_coverage_inconclusive():
    status, reasons = validate_real_summary(_summary(forum_coverage=False))
    assert status == "INCONCLUSIVE_NATURAL_FORUM_BELIEF_COVERAGE"
    assert reasons


def test_phase09c_source_contains_no_direct_matching_engine_reimplementation():
    source = Path("marketlens/market/multiday_real.py").read_text(encoding="utf-8")
    assert "test_matching_system(" not in source
    assert "calculate_closing_price(" not in source
    assert "process_trading_day(" not in source
    assert "advance_trading_day(" in source
    assert "advance_non_trading_day(" in source
