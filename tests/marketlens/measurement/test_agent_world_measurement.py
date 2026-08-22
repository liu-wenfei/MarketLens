import csv
import json
from pathlib import Path
import sqlite3

import pytest

from marketlens.measurement.agent_world import (
    MeasurementError,
    collect_agent_world_measurement,
    find_phase7c_summary,
    is_market_open,
)


def _write_calendar(path: Path, dates: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["pretrade_date"])
        writer.writeheader()
        for date in dates:
            writer.writerow({"pretrade_date": date})


def _write_phase7_fixture(
    root: Path,
    *,
    date: str = "2023-06-15",
    trading_flag: bool = True,
    decision_payload: dict | None = None,
    transactions: list[dict] | None = None,
    daily_volume: int | None = 0,
) -> None:
    root.mkdir(parents=True)

    summary = {
        "phase": "7C",
        "status": "PASS",
        "run_id": "fixture_phase07_full_chain",
        "formal_experiment_evidence": False,
        "duration_seconds": 1.5,
        "git": {"commit": "abc123"},
        "participant_state_read": False,
        "participant_database_used": False,
        "population": {
            "n_population": 20,
            "manifest_status": "PROVISIONAL / DEVELOPMENT / NOT FORMAL POPULATION FREEZE",
            "population_manifest_sha256": "manifest",
        },
        "day": {
            "current_date": date,
            "is_trading_day": trading_flag,
        },
        "graph": {
            "n_nodes": 20,
            "n_edges": 46,
            "graph_sha256": "graph",
            "top_user_ids": ["1", "2"],
        },
        "activation": {
            "n_active": 3,
            "active_agent_ids": ["3", "4", "5"],
            "active_top_user_ids": [],
            "seed": "seed",
            "policy_version": "policy",
            "resampled_for_coverage": False,
        },
        "news": {
            "n_items_supplied_to_each_active_pipeline": 19,
        },
        "agent_reasoning": {
            "attempted": 3,
            "expected": 3,
            "passed": 3,
            "all_active_agents_completed": True,
        },
        "market": {
            "inherited_function": "trader.matching_engine.test_matching_system",
            "runtime_db": "/tmp/deleted_phase7_runtime.db",
            "runtime_db_sha256_before": "before",
            "runtime_db_sha256_after": "after",
            "runtime_db_changed": True,
            "participant_data_used": False,
            "custom_market_logic_used": False,
            "agent_decisions_applied_to_agent_market": True,
            "participant_decisions_applied_to_agent_market": False,
            "day_state": {
                "expected_stock_count": 10,
                "stockdata_rows_on_date": 10,
                "stockdata_distinct_stocks_on_date": 10,
                "profiles_rows_on_date": 20,
                "profiles_distinct_agents_on_date": 20,
                "tradingdetails_rows_on_date": 0
            },
            "tradingdetails_may_be_zero_if_no_orders_match": True
        },
        "scope": {
            "custom_market_logic_used": False,
            "participant_data_used": False,
        },
    }
    (root / "summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )

    records = root / "trading_records"
    records.mkdir()
    (records / f"{date}.json").write_text(
        json.dumps(decision_payload or {}), encoding="utf-8"
    )

    output = root / "simulation_results" / date
    output.mkdir(parents=True)

    with (output / f"daily_summary_{date}.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "date",
                "stock_code",
                "closing_price",
                "volume",
                "transaction_count",
                "large_order_net_inflow",
            ],
        )
        writer.writeheader()
        if daily_volume is not None:
            writer.writerow(
                {
                    "date": date,
                    "stock_code": "CGEI",
                    "closing_price": "9.75",
                    "volume": str(daily_volume),
                    "transaction_count": "0",
                    "large_order_net_inflow": "0",
                }
            )

    tx_rows = transactions or []
    with (output / f"transactions_{date}.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "stock_code",
                "user_id",
                "direction",
                "executed_price",
                "executed_quantity",
                "original_quantity",
                "unfilled_quantity",
                "timestamp",
            ],
        )
        writer.writeheader()
        writer.writerows(tx_rows)

    db = root / "runtime.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE Profiles (user_id TEXT, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE StockData (stock_id TEXT, date TEXT)"
        )
        conn.execute(
            "CREATE TABLE TradingDetails (user_id TEXT, date_time TEXT)"
        )
        conn.commit()


def test_market_open_is_calendar_driven_not_agent_activity(tmp_path):
    calendar = tmp_path / "calendar.csv"
    _write_calendar(calendar, ["2023-06-15"])

    assert is_market_open("2023-06-15", calendar) is True
    assert is_market_open("2023-06-17", calendar) is False


def test_inherited_parser_is_used_before_order_aggregation(tmp_path):
    run = tmp_path / "run"
    calendar = tmp_path / "calendar.csv"
    _write_calendar(calendar, ["2023-06-15"])
    _write_phase7_fixture(run)

    calls = []

    def inherited_parser(path: str):
        calls.append(path)
        return [
            {
                "stock_code": "CGEI",
                "direction": "buy",
                "amount": 100,
                "target_price": 9.75,
                "user_id": "1_CGEI",
            },
            {
                "stock_code": "CGEI",
                "direction": "sell",
                "amount": 100,
                "target_price": 9.75,
                "user_id": "2_CGEI",
            },
        ]

    measured = collect_agent_world_measurement(
        phase7_run_dir=run,
        trading_calendar=calendar,
        inherited_order_parser=inherited_parser,
    )

    assert len(calls) == 1
    assert measured["agent_orders"]["parser"] == "trader.matching_engine.read_json"
    assert measured["agent_orders"]["total"] == 2
    assert measured["agent_orders"]["buy"] == 1
    assert measured["agent_orders"]["sell"] == 1


def test_zero_orders_do_not_close_an_open_market(tmp_path):
    run = tmp_path / "run"
    calendar = tmp_path / "calendar.csv"
    _write_calendar(calendar, ["2023-06-15"])
    _write_phase7_fixture(run)

    measured = collect_agent_world_measurement(
        phase7_run_dir=run,
        trading_calendar=calendar,
        inherited_order_parser=lambda _path: [],
    )

    assert measured["day"]["market_open"] is True
    assert measured["agent_orders"]["total"] == 0
    assert measured["market_outputs"]["transactions"]["execution_rows"] == 0


def test_execution_rows_are_not_reported_as_economic_trade_count(tmp_path):
    run = tmp_path / "run"
    calendar = tmp_path / "calendar.csv"
    _write_calendar(calendar, ["2023-06-15"])

    tx = [
        {
            "stock_code": "CGEI",
            "user_id": "buyer",
            "direction": "buy",
            "executed_price": "9.75",
            "executed_quantity": "100",
            "original_quantity": "100",
            "unfilled_quantity": "0",
            "timestamp": "2023-06-15 10:00:00",
        },
        {
            "stock_code": "CGEI",
            "user_id": "seller",
            "direction": "sell",
            "executed_price": "9.75",
            "executed_quantity": "100",
            "original_quantity": "100",
            "unfilled_quantity": "0",
            "timestamp": "2023-06-15 10:00:00",
        },
    ]
    _write_phase7_fixture(run, transactions=tx, daily_volume=100)

    measured = collect_agent_world_measurement(
        phase7_run_dir=run,
        trading_calendar=calendar,
        inherited_order_parser=lambda _path: [],
    )

    market = measured["market_outputs"]
    assert market["transactions"]["execution_rows"] == 2
    assert market["transactions"]["execution_quantity_sum"] == 200
    assert market["daily_summary"]["matched_volume"] == 100
    assert "economic" in market["transactions"]["semantics"]


def test_calendar_disagreement_fails_closed(tmp_path):
    run = tmp_path / "run"
    calendar = tmp_path / "calendar.csv"
    _write_calendar(calendar, [])
    _write_phase7_fixture(run, trading_flag=True)

    with pytest.raises(MeasurementError, match="disagrees"):
        collect_agent_world_measurement(
            phase7_run_dir=run,
            trading_calendar=calendar,
            inherited_order_parser=lambda _path: [],
        )


def test_collector_does_not_modify_inputs(tmp_path):
    run = tmp_path / "run"
    calendar = tmp_path / "calendar.csv"
    _write_calendar(calendar, ["2023-06-15"])
    _write_phase7_fixture(run)

    before = {
        path: path.read_bytes()
        for path in run.rglob("*")
        if path.is_file()
    }
    calendar_before = calendar.read_bytes()

    collect_agent_world_measurement(
        phase7_run_dir=run,
        trading_calendar=calendar,
        inherited_order_parser=lambda _path: [],
    )

    after = {
        path: path.read_bytes()
        for path in run.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert calendar.read_bytes() == calendar_before


def test_summary_discovery_is_root_level_and_phase7c_only(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "other.json").write_text(
        json.dumps({"phase": "7D-1", "run_id": "wrong"}),
        encoding="utf-8",
    )
    expected = {"phase": "7C", "run_id": "right", "status": "PASS"}
    (run / "summary.json").write_text(
        json.dumps(expected), encoding="utf-8"
    )

    path, payload = find_phase7c_summary(run)
    assert path.name == "summary.json"
    assert payload["run_id"] == "right"


def test_integrity_flags_fail_closed(tmp_path):
    run = tmp_path / "run"
    calendar = tmp_path / "calendar.csv"
    _write_calendar(calendar, ["2023-06-15"])
    _write_phase7_fixture(run)

    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    summary["scope"]["participant_data_used"] = True
    (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(MeasurementError, match="participant"):
        collect_agent_world_measurement(
            phase7_run_dir=run,
            trading_calendar=calendar,
            inherited_order_parser=lambda _path: [],
        )


def test_actual_phase7c_reasoning_schema_is_observed(tmp_path):
    run = tmp_path / "run"
    calendar = tmp_path / "calendar.csv"
    _write_calendar(calendar, ["2023-06-15"])
    _write_phase7_fixture(run)

    measured = collect_agent_world_measurement(
        phase7_run_dir=run,
        trading_calendar=calendar,
        inherited_order_parser=lambda _path: [],
    )

    assert measured["reasoning"]["attempted"] == 3
    assert measured["reasoning"]["completed"] == 3
    assert measured["reasoning"]["failed"] == 0
    assert measured["reasoning"]["all_active_agents_completed"] is True
    assert measured["reasoning"]["status"] == "observed_from_phase7_summary"


def test_phase7_market_summary_is_used_when_temp_runtime_is_not_preserved(tmp_path):
    run = tmp_path / "run"
    calendar = tmp_path / "calendar.csv"
    _write_calendar(calendar, ["2023-06-15"])
    _write_phase7_fixture(run)

    # Remove the fixture runtime DB to reproduce the durable Phase 7C artifact:
    # summary/trading records are kept, isolated temp runtime is not.
    (run / "runtime.db").unlink()

    measured = collect_agent_world_measurement(
        phase7_run_dir=run,
        trading_calendar=calendar,
        inherited_order_parser=lambda _path: [],
    )

    summary = measured["market_outputs"]["phase7_summary"]
    assert summary["status"] == "observed_from_phase7_summary"
    assert summary["runtime_db_changed"] is True
    assert summary["day_state"]["stockdata_rows_on_date"] == 10
    assert summary["day_state"]["profiles_rows_on_date"] == 20
    assert summary["day_state"]["tradingdetails_rows_on_date"] == 0

    assert measured["runtime_db"]["status"] == "not_preserved_post_run"
    assert measured["runtime_db"]["sha256_before_reported_by_phase7"] == "before"
    assert measured["runtime_db"]["sha256_after_reported_by_phase7"] == "after"
