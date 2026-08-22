#!/usr/bin/env python3
"""Phase 7D-1: zero-LLM matched-trade branch coverage for inherited TwinMarket.

The script creates a temporary copy of the bounded N20 Agent runtime, writes a
small inherited-shape decision fixture, and delegates the market transition to
MarketLens ``advance_trading_day()``, which directly calls inherited TwinMarket
``test_matching_system()``.

No participant state is read. No custom matching, price formation, Agent
portfolio mutation, StockData write, TradingDetails write, or Profiles write is
implemented here. Arithmetic below is postcondition auditing only.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.agents.runtime.preflight import create_empty_forum_db
from marketlens.market.runtime.inherited_market import advance_trading_day, reset_agent_world


BANNER = "NON-FORMAL / INHERITED MATCHED-TRADE COVERAGE GATE / NOT FORMAL EXPERIMENT EVIDENCE"
GATE_VERSION = "marketlens_phase07d1_matched_trade_gate/1.0"

CURRENT_DATE = "2023-06-15"
PREVIOUS_PROFILE_DATE = "2023-06-14 00:00:00"
CURRENT_PROFILE_DATE = "2023-06-15 00:00:00"
STOCK_ID = "CGEI"
BUYER_ID = "22543333014"
SELLER_ID = "25901251490"
PRICE = 9.75
QUANTITY = 100


class Phase07D1Error(RuntimeError):
    """Raised when the deterministic inherited matched-trade gate fails."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit(repo_root: Path) -> str:
    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _git_status(repo_root: Path) -> str:
    import subprocess

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _profile(conn: sqlite3.Connection, user_id: str, created_at: str) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT user_id, current_cash, cur_positions, created_at
        FROM Profiles
        WHERE user_id = ? AND created_at = ?
        """,
        (user_id, created_at),
    ).fetchone()
    if row is None:
        raise Phase07D1Error(
            f"missing Profiles row for user={user_id}, created_at={created_at}"
        )
    return dict(row)


def _position_shares(profile: dict[str, Any], stock_id: str) -> int:
    positions = json.loads(profile["cur_positions"] or "{}")
    value = positions.get(stock_id)
    if value is None:
        return 0
    if isinstance(value, dict):
        return int(value.get("shares", 0))
    # Defensive compatibility with older/simple fixtures; read-only audit only.
    return int(value)


def _close_enough(actual: float, expected: float, *, tol: float = 1e-6) -> bool:
    return abs(float(actual) - float(expected)) <= tol


def _write_decisions(path: Path) -> None:
    payload = {
        BUYER_ID: {
            "stock_decisions": {
                STOCK_ID: {
                    "action": "buy",
                    "sub_orders": [{"quantity": QUANTITY, "price": PRICE}],
                }
            }
        },
        SELLER_ID: {
            "stock_decisions": {
                STOCK_ID: {
                    "action": "sell",
                    "sub_orders": [{"quantity": QUANTITY, "price": PRICE}],
                }
            }
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _inspect_after(
    runtime_db: Path,
    *,
    buyer_before: dict[str, Any],
    seller_before: dict[str, Any],
) -> dict[str, Any]:
    with sqlite3.connect(runtime_db) as conn:
        conn.row_factory = sqlite3.Row

        stock_row = conn.execute(
            """
            SELECT stock_id, date, close_price, pre_close, vol
            FROM StockData
            WHERE stock_id = ? AND date = ?
            """,
            (STOCK_ID, CURRENT_DATE),
        ).fetchone()
        if stock_row is None:
            raise Phase07D1Error("inherited market did not create target StockData row")
        stock = dict(stock_row)

        trading_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT user_id, date_time, stock_id, price, trading_direction, volume, valid
                FROM TradingDetails
                WHERE date_time = ? AND stock_id = ?
                ORDER BY user_id, trading_direction
                """,
                (CURRENT_DATE, STOCK_ID),
            ).fetchall()
        ]

        buyer_after = _profile(conn, BUYER_ID, CURRENT_PROFILE_DATE)
        seller_after = _profile(conn, SELLER_ID, CURRENT_PROFILE_DATE)

        stockdata_count = conn.execute(
            "SELECT COUNT(*) FROM StockData WHERE date = ?",
            (CURRENT_DATE,),
        ).fetchone()[0]
        profile_count = conn.execute(
            "SELECT COUNT(*) FROM Profiles WHERE created_at = ?",
            (CURRENT_PROFILE_DATE,),
        ).fetchone()[0]

    if not _close_enough(stock["close_price"], PRICE):
        raise Phase07D1Error(
            f"unexpected inherited CGEI close: {stock['close_price']} != {PRICE}"
        )

    expected_trades = {
        (BUYER_ID, "buy"): (PRICE, QUANTITY),
        (SELLER_ID, "sell"): (PRICE, QUANTITY),
    }
    observed: dict[tuple[str, str], tuple[float, int]] = {}
    for row in trading_rows:
        key = (str(row["user_id"]), str(row["trading_direction"]))
        observed[key] = (float(row["price"]), int(row["volume"]))

    if set(observed) != set(expected_trades):
        raise Phase07D1Error(
            f"unexpected inherited TradingDetails participants/directions: {observed}"
        )
    for key, (expected_price, expected_volume) in expected_trades.items():
        actual_price, actual_volume = observed[key]
        if not _close_enough(actual_price, expected_price) or actual_volume != expected_volume:
            raise Phase07D1Error(
                f"unexpected TradingDetails execution for {key}: "
                f"price={actual_price}, volume={actual_volume}"
            )

    notional = PRICE * QUANTITY  # audit expectation only; never used for mutation
    buyer_cash_before = float(buyer_before["current_cash"])
    seller_cash_before = float(seller_before["current_cash"])
    buyer_cash_after = float(buyer_after["current_cash"])
    seller_cash_after = float(seller_after["current_cash"])

    if not _close_enough(buyer_cash_after, buyer_cash_before - notional):
        raise Phase07D1Error("buyer cash did not reflect inherited matched BUY execution")
    if not _close_enough(seller_cash_after, seller_cash_before + notional):
        raise Phase07D1Error("seller cash did not reflect inherited matched SELL execution")

    buyer_shares_before = _position_shares(buyer_before, STOCK_ID)
    seller_shares_before = _position_shares(seller_before, STOCK_ID)
    buyer_shares_after = _position_shares(buyer_after, STOCK_ID)
    seller_shares_after = _position_shares(seller_after, STOCK_ID)

    if buyer_shares_after != buyer_shares_before + QUANTITY:
        raise Phase07D1Error("buyer CGEI holdings did not increase by inherited execution volume")
    if seller_shares_after != seller_shares_before - QUANTITY:
        raise Phase07D1Error("seller CGEI holdings did not decrease by inherited execution volume")

    if int(stockdata_count) != 10:
        raise Phase07D1Error(f"expected 10 StockData rows on {CURRENT_DATE}, got {stockdata_count}")
    if int(profile_count) != 20:
        raise Phase07D1Error(f"expected 20 Profiles rows on {CURRENT_DATE}, got {profile_count}")

    return {
        "stockdata": stock,
        "trading_details": trading_rows,
        "profiles": {
            "buyer": {
                "user_id": BUYER_ID,
                "cash_before": buyer_cash_before,
                "cash_after": buyer_cash_after,
                "cgei_shares_before": buyer_shares_before,
                "cgei_shares_after": buyer_shares_after,
            },
            "seller": {
                "user_id": SELLER_ID,
                "cash_before": seller_cash_before,
                "cash_after": seller_cash_after,
                "cgei_shares_before": seller_shares_before,
                "cgei_shares_after": seller_shares_after,
            },
        },
        "day_state": {
            "stockdata_rows_on_date": int(stockdata_count),
            "profiles_rows_on_date": int(profile_count),
            "tradingdetails_rows_for_target_stock": len(trading_rows),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-db",
        default="artifacts/preflight/phase05b/dev_population_n20/population_runtime.db",
    )
    parser.add_argument(
        "--artifact-root",
        default="artifacts/preflight/phase07",
    )
    parser.add_argument(
        "--acknowledge-non-formal",
        action="store_true",
        help="required acknowledgement that this is branch-coverage preflight only",
    )
    args = parser.parse_args()

    if not args.acknowledge_non_formal:
        raise SystemExit("refusing to run without --acknowledge-non-formal")

    repo_root = REPO_ROOT
    source_runtime = Path(args.runtime_db).expanduser().resolve()
    if not source_runtime.is_file():
        raise SystemExit(f"runtime DB not found: {source_runtime}")

    status_at_start = _git_status(repo_root)
    if status_at_start:
        raise SystemExit(
            "Phase 7D-1 requires a clean git tree so the artifact maps to one commit:\n"
            + status_at_start
        )

    commit = _git_commit(repo_root)
    started = datetime.now(timezone.utc)
    run_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}_{commit[:8]}_phase07_matched_trade"
    run_dir = Path(args.artifact_root).expanduser().resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    print(BANNER)

    source_sha_before = _sha256(source_runtime)
    decision_path = run_dir / "controlled_decisions.json"
    _write_decisions(decision_path)

    with tempfile.TemporaryDirectory(prefix="marketlens_phase07d1_") as tmp:
        workspace = Path(tmp)
        runtime = workspace / "runtime.db"
        forum = workspace / "forum.db"
        shutil.copy2(source_runtime, runtime)
        create_empty_forum_db(forum)

        reset_result = reset_agent_world(
            current_date=CURRENT_DATE,
            runtime_db=runtime,
            forum_db=forum,
            protected_paths=(source_runtime,),
        )

        with sqlite3.connect(runtime) as conn:
            buyer_before = _profile(conn, BUYER_ID, PREVIOUS_PROFILE_DATE)
            seller_before = _profile(conn, SELLER_ID, PREVIOUS_PROFILE_DATE)

        seller_available = _position_shares(seller_before, STOCK_ID)
        buyer_cash = float(buyer_before["current_cash"])
        required_cash = PRICE * QUANTITY
        if seller_available < QUANTITY:
            raise Phase07D1Error(
                f"audited seller no longer has enough {STOCK_ID}: {seller_available}"
            )
        if buyer_cash < required_cash:
            raise Phase07D1Error(
                f"audited buyer no longer has enough cash: {buyer_cash} < {required_cash}"
            )

        market_result = advance_trading_day(
            current_date=CURRENT_DATE,
            runtime_db=runtime,
            decision_json=decision_path,
            log_dir=run_dir,
            protected_paths=(source_runtime,),
        )
        if not market_result.runtime_db_changed:
            raise Phase07D1Error("inherited market call did not change the temporary runtime DB")

        postconditions = _inspect_after(
            runtime,
            buyer_before=buyer_before,
            seller_before=seller_before,
        )

    source_sha_after = _sha256(source_runtime)
    if source_sha_after != source_sha_before:
        raise Phase07D1Error("protected source runtime DB changed")

    finished = datetime.now(timezone.utc)
    summary = {
        "banner": BANNER,
        "phase": "7D-1",
        "gate_version": GATE_VERSION,
        "status": "PASS",
        "formal_experiment_evidence": False,
        "run_id": run_id,
        "started_at_utc": started.isoformat(),
        "finished_at_utc": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "git": {
            "commit": commit,
            "clean_at_start": True,
        },
        "fixture": {
            "current_date": CURRENT_DATE,
            "stock_id": STOCK_ID,
            "buyer_id": BUYER_ID,
            "seller_id": SELLER_ID,
            "price": PRICE,
            "quantity": QUANTITY,
            "fixture_purpose": "deterministic matched-trade branch coverage only",
            "natural_activation_evidence": False,
            "llm_backend_used": False,
        },
        "delegation": {
            "reset": reset_result.to_dict(),
            "market": market_result.to_dict(),
            "inherited_market_function": "trader.matching_engine.test_matching_system",
            "custom_market_logic_used": False,
            "participant_data_used": False,
        },
        "postconditions": postconditions,
        "protected_source_runtime": {
            "path": str(source_runtime),
            "sha256_before": source_sha_before,
            "sha256_after": source_sha_after,
            "unchanged": source_sha_before == source_sha_after,
        },
        "scope": {
            "verified_here": [
                "controlled inherited-shape Agent BUY/SELL decisions reach inherited matching",
                "one real matched trade is produced by TwinMarket",
                "TradingDetails contains the real buyer and seller executions",
                "Profiles cash and CGEI holdings reflect inherited execution",
                "StockData advances for the target trading day",
                "protected bounded source runtime remains unchanged",
            ],
            "not_verified_here": [
                "natural Phase 4 activation",
                "LLM reasoning",
                "dynamic top-user direct-news branch",
                "multi-day forum or belief propagation",
                "formal experiment evidence",
            ],
        },
    }

    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"Artifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
