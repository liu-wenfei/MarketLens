"""Phase 8: thin, inherited-first Agent-world measurement facade.

This module DOES NOT execute the market or Agent reasoning.  It reads outputs
that already exist after a Phase 7 run and produces one comparable measurement
record for later Phase 9 feasibility work.

Priority order:
1. authoritative trading calendar for market-open state;
2. existing Phase 7 summary / frozen Phase 3-7 metadata;
3. inherited TwinMarket read-only parser for Agent decision -> order semantics;
4. inherited TwinMarket-generated CSV / SQLite outputs;
5. mechanical counting / hashing / serialisation only.

If an observation is unavailable, the measurement records ``None`` /
``not_observed`` rather than inventing replacement market logic.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import importlib
import io
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Iterable, Mapping

SCHEMA_VERSION = "marketlens_agent_world_measurement/1.0"


class MeasurementError(RuntimeError):
    """Raised when Phase 8 cannot safely measure inherited evidence."""


InheritedOrderParser = Callable[[str], list[dict[str, Any]]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _normalise_date(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) < 10:
        raise MeasurementError(f"invalid Agent-world date: {value!r}")
    return text[:10]


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _numeric(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number.is_integer():
        return int(number)
    return number


def _sum_numeric(values: Iterable[Any]) -> int | float:
    total = 0.0
    for value in values:
        number = _numeric(value)
        if number is not None:
            total += float(number)
    return int(total) if total.is_integer() else total


def discover_latest_phase7c_run(
    artifact_root: str | Path = "artifacts/preflight/phase07",
) -> Path:
    root = Path(artifact_root)
    if not root.exists():
        raise MeasurementError(f"Phase 7 artifact root does not exist: {root}")

    candidates = sorted(
        (
            path
            for path in root.iterdir()
            if path.is_dir() and path.name.endswith("_phase07_full_chain")
        ),
        key=lambda path: path.name,
    )
    if not candidates:
        raise MeasurementError(
            f"no Phase 7C full-chain run found under {root}; "
            "pass --phase7-run-dir explicitly"
        )
    return candidates[-1]


def find_phase7c_summary(run_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    """Find the existing Phase 7C summary without depending on its filename."""

    root = Path(run_dir)
    if not root.is_dir():
        raise MeasurementError(f"Phase 7 run directory does not exist: {root}")

    preferred = [
        root / "summary.json",
        root / "preflight_summary.json",
        root / "run_summary.json",
        root / "manifest.json",
    ]

    seen: set[Path] = set()
    candidates: list[Path] = []
    for path in preferred:
        if path.exists():
            candidates.append(path)
            seen.add(path)

    for path in sorted(root.glob("*.json")):
        if path not in seen:
            candidates.append(path)

    for path in candidates:
        try:
            payload = _read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(payload, Mapping)
            and payload.get("phase") == "7C"
            and isinstance(payload.get("run_id"), str)
        ):
            return path, dict(payload)

    raise MeasurementError(
        f"could not find a root-level Phase 7C summary JSON in {root}"
    )


def _calendar_dates(trading_calendar: str | Path) -> set[str]:
    path = Path(trading_calendar)
    if not path.exists():
        raise MeasurementError(f"trading calendar does not exist: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise MeasurementError(f"trading calendar has no header: {path}")

        date_column = next(
            (
                column
                for column in ("pretrade_date", "trade_date", "date")
                if column in reader.fieldnames
            ),
            None,
        )
        if date_column is None:
            raise MeasurementError(
                "trading calendar must contain one of: "
                "pretrade_date, trade_date, date"
            )

        result: set[str] = set()
        for row in reader:
            value = str(row.get(date_column) or "").strip()
            if value:
                result.add(_normalise_date(value))
        return result


def is_market_open(
    current_date: str,
    trading_calendar: str | Path,
) -> bool:
    """Authoritative market availability comes only from the trading calendar."""

    date = _normalise_date(current_date)
    return date in _calendar_dates(trading_calendar)


def load_inherited_order_parser() -> InheritedOrderParser:
    """Load TwinMarket's existing decision JSON parser.

    Phase 8 deliberately does not reproduce ``stock_decisions`` / ``sub_orders``
    semantics.  If the inherited parser is unavailable, measurement fails closed
    when a decision file needs parsing.
    """

    module = importlib.import_module("trader.matching_engine")
    parser = getattr(module, "read_json", None)
    if not callable(parser):
        raise MeasurementError(
            "inherited trader.matching_engine.read_json is unavailable"
        )
    return parser


def _measure_agent_orders(
    decision_json: Path,
    parser: InheritedOrderParser | None,
) -> dict[str, Any]:
    if not decision_json.exists():
        return {
            "status": "not_observed",
            "source": str(decision_json),
            "parser": "trader.matching_engine.read_json",
            "total": None,
            "buy": None,
            "sell": None,
            "symbols": [],
            "submitted_quantity": None,
        }

    inherited_parser = parser or load_inherited_order_parser()

    # The inherited parser prints its own diagnostics.  We call it unchanged but
    # suppress those prints so the Phase 8 CLI can emit one clean JSON document.
    with contextlib.redirect_stdout(io.StringIO()):
        orders = inherited_parser(str(decision_json))

    if not isinstance(orders, list):
        raise MeasurementError("inherited read_json did not return a list")

    buy = 0
    sell = 0
    symbols: set[str] = set()
    quantities: list[Any] = []

    for order in orders:
        if not isinstance(order, Mapping):
            raise MeasurementError("inherited order parser returned non-mapping item")
        direction = str(order.get("direction") or "").lower()
        if direction == "buy":
            buy += 1
        elif direction == "sell":
            sell += 1
        symbols.add(str(order.get("stock_code") or ""))
        quantities.append(order.get("amount"))

    symbols.discard("")
    return {
        "status": "observed",
        "source": str(decision_json),
        "source_sha256": _sha256(decision_json),
        "parser": "trader.matching_engine.read_json",
        "total": len(orders),
        "buy": buy,
        "sell": sell,
        "symbols": sorted(symbols),
        "submitted_quantity": _sum_numeric(quantities),
    }


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _measure_market_outputs(run_dir: Path, current_date: str) -> dict[str, Any]:
    output_dir = run_dir / "simulation_results" / current_date
    summary_path = output_dir / f"daily_summary_{current_date}.csv"
    transactions_path = output_dir / f"transactions_{current_date}.csv"

    daily_rows: list[dict[str, str]] | None = None
    execution_rows: list[dict[str, str]] | None = None

    if summary_path.exists():
        daily_rows = _read_csv_rows(summary_path)
    if transactions_path.exists():
        execution_rows = _read_csv_rows(transactions_path)

    matched_volume = (
        _sum_numeric(row.get("volume") for row in daily_rows)
        if daily_rows is not None
        else None
    )
    execution_quantity_sum = (
        _sum_numeric(row.get("executed_quantity") for row in execution_rows)
        if execution_rows is not None
        else None
    )

    return {
        "daily_summary": {
            "status": "observed" if daily_rows is not None else "not_observed",
            "source": str(summary_path),
            "source_sha256": _sha256(summary_path) if summary_path.exists() else None,
            "rows": len(daily_rows) if daily_rows is not None else None,
            "matched_volume": matched_volume,
            "matched_volume_semantics": (
                "sum of inherited TwinMarket daily_summary.volume"
                if daily_rows is not None
                else None
            ),
            "symbols": (
                sorted(
                    {
                        str(row.get("stock_code") or "")
                        for row in daily_rows
                        if row.get("stock_code")
                    }
                )
                if daily_rows is not None
                else []
            ),
        },
        "transactions": {
            "status": "observed"
            if execution_rows is not None
            else "not_observed",
            "source": str(transactions_path),
            "source_sha256": (
                _sha256(transactions_path) if transactions_path.exists() else None
            ),
            "execution_rows": (
                len(execution_rows) if execution_rows is not None else None
            ),
            "execution_quantity_sum": execution_quantity_sum,
            "semantics": (
                "execution-side rows; buyer and seller records are not "
                "automatically interpreted as separate economic matches"
            ),
        },
    }


def _discover_runtime_db(run_dir: Path) -> Path | None:
    preferred = [run_dir / "runtime.db", run_dir / "user.db"]
    for path in preferred:
        if path.exists():
            return path

    for path in sorted(run_dir.glob("*.db")):
        try:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
                names = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
            if {"Profiles", "StockData", "TradingDetails"}.issubset(names):
                return path
        except sqlite3.DatabaseError:
            continue
    return None


def _measure_runtime_db(run_dir: Path, current_date: str) -> dict[str, Any]:
    db_path = _discover_runtime_db(run_dir)
    if db_path is None:
        return {
            "status": "not_observed",
            "source": None,
            "trading_details_rows_for_date": None,
            "profiles_rows_for_date": None,
            "stock_data_rows_for_date": None,
        }

    uri = f"file:{db_path.resolve()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as conn:
            trading_details = conn.execute(
                "SELECT COUNT(*) FROM TradingDetails WHERE date(date_time) = date(?)",
                (current_date,),
            ).fetchone()[0]
            profiles = conn.execute(
                "SELECT COUNT(*) FROM Profiles WHERE date(created_at) = date(?)",
                (current_date,),
            ).fetchone()[0]
            stock_data = conn.execute(
                "SELECT COUNT(*) FROM StockData WHERE date(date) = date(?)",
                (current_date,),
            ).fetchone()[0]
    except sqlite3.DatabaseError as exc:
        raise MeasurementError(
            f"could not read inherited runtime DB {db_path}: {exc}"
        ) from exc

    return {
        "status": "observed",
        "source": str(db_path),
        "source_sha256": _sha256(db_path),
        "trading_details_rows_for_date": int(trading_details),
        "profiles_rows_for_date": int(profiles),
        "stock_data_rows_for_date": int(stock_data),
    }



def _measure_reasoning_summary(reasoning: Mapping[str, Any]) -> dict[str, Any]:
    if not reasoning:
        return {
            "attempted": None,
            "completed": None,
            "failed": None,
            "all_active_agents_completed": None,
            "status": "not_observed",
        }

    attempted = _numeric(_first(reasoning, "attempted", "n_attempted"))
    completed = _numeric(
        _first(reasoning, "completed", "passed", "n_completed")
    )
    failed = _numeric(_first(reasoning, "failed", "n_failed"))

    # Phase 7C stores attempted and passed but no explicit failed count.
    # Deriving failed = attempted - passed is mechanical accounting only.
    if failed is None and attempted is not None and completed is not None:
        failed = max(0, int(attempted) - int(completed))

    return {
        "attempted": attempted,
        "completed": completed,
        "failed": failed,
        "all_active_agents_completed": reasoning.get(
            "all_active_agents_completed"
        ),
        "status": "observed_from_phase7_summary",
    }


def _measure_phase7_market_summary(market: Mapping[str, Any]) -> dict[str, Any]:
    """Read the market evidence Phase 7C already persisted in summary.json.

    The Phase 7C temporary runtime DB and TwinMarket simulation_results directory
    were intentionally not preserved as durable artifacts.  Their validated
    postconditions *were* preserved in the Phase 7 summary.  Phase 8 reads those
    facts instead of rerunning the market or pretending the deleted temp DB is
    still available.
    """

    if not market:
        return {
            "status": "not_observed",
            "inherited_function": None,
            "runtime_db_changed": None,
            "runtime_db_sha256_before": None,
            "runtime_db_sha256_after": None,
            "agent_decisions_applied_to_agent_market": None,
            "participant_decisions_applied_to_agent_market": None,
            "day_state": {},
        }

    day_state = _as_dict(market.get("day_state"))
    return {
        "status": "observed_from_phase7_summary",
        "inherited_function": market.get("inherited_function"),
        "runtime_db_reported_path": market.get("runtime_db"),
        "runtime_db_sha256_before": market.get("runtime_db_sha256_before"),
        "runtime_db_sha256_after": market.get("runtime_db_sha256_after"),
        "runtime_db_changed": market.get("runtime_db_changed"),
        "agent_decisions_applied_to_agent_market": market.get(
            "agent_decisions_applied_to_agent_market"
        ),
        "participant_decisions_applied_to_agent_market": market.get(
            "participant_decisions_applied_to_agent_market"
        ),
        "day_state": {
            "expected_stock_count": day_state.get("expected_stock_count"),
            "stockdata_rows_on_date": day_state.get("stockdata_rows_on_date"),
            "stockdata_distinct_stocks_on_date": day_state.get(
                "stockdata_distinct_stocks_on_date"
            ),
            "profiles_rows_on_date": day_state.get("profiles_rows_on_date"),
            "profiles_distinct_agents_on_date": day_state.get(
                "profiles_distinct_agents_on_date"
            ),
            "tradingdetails_rows_on_date": day_state.get(
                "tradingdetails_rows_on_date"
            ),
        },
        "tradingdetails_may_be_zero_if_no_orders_match": market.get(
            "tradingdetails_may_be_zero_if_no_orders_match"
        ),
    }


def _augment_runtime_observation(
    runtime: dict[str, Any],
    phase7_market: Mapping[str, Any],
) -> dict[str, Any]:
    if runtime.get("status") == "observed":
        return runtime

    if phase7_market.get("runtime_db_sha256_after"):
        return {
            **runtime,
            "status": "not_preserved_post_run",
            "source_reported_by_phase7": phase7_market.get("runtime_db"),
            "sha256_before_reported_by_phase7": phase7_market.get(
                "runtime_db_sha256_before"
            ),
            "sha256_after_reported_by_phase7": phase7_market.get(
                "runtime_db_sha256_after"
            ),
            "runtime_db_changed_reported_by_phase7": phase7_market.get(
                "runtime_db_changed"
            ),
            "note": (
                "Phase 7C used an isolated temporary runtime DB. The durable "
                "Phase 7 summary preserves its validated hashes/postconditions; "
                "Phase 8 does not recreate or rerun that state."
            ),
        }
    return runtime

def collect_agent_world_measurement(
    *,
    phase7_run_dir: str | Path,
    trading_calendar: str | Path,
    inherited_order_parser: InheritedOrderParser | None = None,
) -> dict[str, Any]:
    """Collect a read-only Phase 8 record from an existing Phase 7C run."""

    run_dir = Path(phase7_run_dir)
    summary_path, phase7 = find_phase7c_summary(run_dir)

    if phase7.get("status") != "PASS":
        raise MeasurementError(
            f"Phase 8 accepts only PASS Phase 7C evidence, got: "
            f"{phase7.get('status')!r}"
        )

    day = _as_dict(phase7.get("day"))
    current_date = _normalise_date(
        _first(day, "current_date", "agent_world_date")
    )

    market_open = is_market_open(current_date, trading_calendar)

    # Cross-check only; the authoritative value remains the trading calendar.
    inherited_day_flag = _first(day, "is_trading_day", "market_open")
    if inherited_day_flag is not None and bool(inherited_day_flag) != market_open:
        raise MeasurementError(
            "Phase 7 day flag disagrees with authoritative trading calendar"
        )

    population = _as_dict(phase7.get("population"))
    activation = _as_dict(phase7.get("activation"))
    graph = _as_dict(phase7.get("graph"))
    news = _as_dict(phase7.get("news"))
    # Phase 7C's frozen summary uses ``agent_reasoning``.  Keep the older
    # ``reasoning`` alias only for fixture/backward compatibility.
    reasoning = _as_dict(phase7.get("agent_reasoning"))
    if not reasoning:
        reasoning = _as_dict(phase7.get("reasoning"))
    market = _as_dict(phase7.get("market"))
    scope = _as_dict(phase7.get("scope"))

    active_ids = [
        str(value) for value in _as_list(activation.get("active_agent_ids"))
    ]
    top_user_ids = [str(value) for value in _as_list(graph.get("top_user_ids"))]
    active_top_ids = [
        str(value) for value in _as_list(activation.get("active_top_user_ids"))
    ]

    decision_json = run_dir / "trading_records" / f"{current_date}.json"
    orders = _measure_agent_orders(decision_json, inherited_order_parser)
    inherited_market_outputs = _measure_market_outputs(run_dir, current_date)
    phase7_market_summary = _measure_phase7_market_summary(market)
    runtime = _augment_runtime_observation(
        _measure_runtime_db(run_dir, current_date),
        market,
    )

    participant_used = bool(
        phase7.get("participant_database_used", False)
        or phase7.get("participant_state_read", False)
        or scope.get("participant_data_used", False)
        or market.get("participant_data_used", False)
    )
    custom_market = bool(
        scope.get("custom_market_logic_used", False)
        or market.get("custom_market_logic_used", False)
    )

    result = {
        "schema_version": SCHEMA_VERSION,
        "phase": "8",
        "status": "PASS",
        "measurement_mode": "read_only_inherited_output_facade",
        "formal_experiment_evidence": False,
        "source_phase7": {
            "run_id": phase7.get("run_id"),
            "summary": str(summary_path),
            "summary_sha256": _sha256(summary_path),
            "git_commit": _as_dict(phase7.get("git")).get("commit"),
            "duration_seconds": phase7.get("duration_seconds"),
        },
        "day": {
            "agent_world_date": current_date,
            "market_open": market_open,
            "market_status_source": str(Path(trading_calendar)),
            "market_status_source_sha256": _sha256(Path(trading_calendar)),
            "participant_trading_rule": (
                "future participant trading is disabled only when the "
                "authoritative Agent-world market calendar is closed; zero "
                "Agent activity/orders/executions on an open day does not "
                "close participant trading"
            ),
        },
        "population": {
            "n_population": population.get("n_population"),
            "manifest_status": population.get("manifest_status"),
            "population_manifest_sha256": population.get(
                "population_manifest_sha256"
            ),
        },
        "activation": {
            "n_active": _first(
                activation,
                "n_active",
                default=len(active_ids) if active_ids else 0,
            ),
            "active_agent_ids": active_ids,
            "seed": activation.get("seed"),
            "policy_version": activation.get("policy_version"),
            "resampled_for_coverage": activation.get("resampled_for_coverage"),
        },
        "graph": {
            "n_nodes": graph.get("n_nodes"),
            "n_edges": graph.get("n_edges"),
            "graph_sha256": graph.get("graph_sha256"),
            "top_user_ids": top_user_ids,
            "active_top_user_ids": active_top_ids,
            "top_user_status_definition": graph.get(
                "top_user_status_definition",
                "dynamic graph prominence; not credibility/correctness",
            ),
        },
        "news": {
            "daily_background_news_items": _first(
                news,
                "n_items_supplied_to_each_active_pipeline",
                "daily_background_news_count",
                "n_items",
                "count",
            ),
            "source": news.get("source"),
        },
        "reasoning": _measure_reasoning_summary(reasoning),
        "agent_orders": orders,
        "market_outputs": {
            **inherited_market_outputs,
            "phase7_summary": phase7_market_summary,
        },
        "runtime_db": runtime,
        "integrity": {
            "participant_data_used": participant_used,
            "custom_market_logic_used": custom_market,
            "extra_llm_calls_introduced_by_phase8": False,
            "market_reexecuted_by_phase8": False,
            "inherited_order_semantics_owner": (
                "trader.matching_engine.read_json"
            ),
            "market_output_owner": "inherited TwinMarket matching engine",
        },
        "deferred": [
            "final Agent population N",
            "multi-day activation continuity",
            "multi-day graph continuity",
            "multi-day forum propagation",
            "multi-day belief propagation",
            "formal experiment duration",
            "controlled experimental stimulus timing",
        ],
    }

    if participant_used:
        raise MeasurementError("participant data unexpectedly present in Agent-world run")
    if custom_market:
        raise MeasurementError("Phase 7 evidence reports custom market logic")

    raw_market_observed = any(
        result["market_outputs"][key].get("status") == "observed"
        for key in ("daily_summary", "transactions")
    )
    summary_market_observed = (
        result["market_outputs"]["phase7_summary"].get("status")
        == "observed_from_phase7_summary"
    )
    runtime_observed = result["runtime_db"].get("status") in {
        "observed",
        "not_preserved_post_run",
    }
    if not (raw_market_observed or summary_market_observed or runtime_observed):
        raise MeasurementError(
            "no inherited market evidence is observable from the Phase 7 run"
        )
    return result


def write_measurement(path: str | Path, measurement: Mapping[str, Any]) -> Path:
    output = Path(path)
    _write_json(output, measurement)
    return output
