#!/usr/bin/env python3
"""One-click Phase 9C N20 three-day validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.market.multiday_n20_real import (  # noqa: E402
    BANNER,
    DEFAULT_POPULATION_MANIFEST,
    DEFAULT_RUNTIME_DB,
    DRY_BANNER,
    run_phase09c_n20,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reuse the verified N20 fixture and exact Phase 9B activation "
            "sequence for the fixed 2023-06-15..17 engineering validation."
        )
    )
    parser.add_argument("--runtime-db", default=DEFAULT_RUNTIME_DB)
    parser.add_argument("--population-manifest", default=DEFAULT_POPULATION_MANIFEST)
    parser.add_argument("--source-db", default="data/sys_1000.db")
    parser.add_argument("--belief-csv", default="util/belief/belief_1000_0129.csv")
    parser.add_argument("--config-path", default="config/api.yaml")
    parser.add_argument("--news-pickle", default="data/sorted_impact_news.pkl")
    parser.add_argument("--trading-calendar", default="data/trading_days.csv")
    parser.add_argument("--artifact-root", default="artifacts/preflight/phase09")
    parser.add_argument(
        "--execute-real-backend",
        action="store_true",
        help="execute inherited Agent reasoning and Agent-world state updates",
    )
    parser.add_argument(
        "--acknowledge-non-formal",
        action="store_true",
        help="acknowledge this is engineering validation, not formal evidence",
    )
    parser.add_argument(
        "--preserve-workspace",
        action="store_true",
        help="preserve isolated runtime/forum DBs only when a real run is non-PASS",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(BANNER if args.execute_real_backend else DRY_BANNER)
    try:
        summary = run_phase09c_n20(
            repo_root=REPO_ROOT,
            runtime_db=args.runtime_db,
            population_manifest=args.population_manifest,
            source_db=args.source_db,
            belief_csv=args.belief_csv,
            config_path=args.config_path,
            news_pickle=args.news_pickle,
            trading_calendar=args.trading_calendar,
            artifact_root=args.artifact_root,
            execute_real_backend=args.execute_real_backend,
            acknowledge_non_formal=args.acknowledge_non_formal,
            preserve_workspace=args.preserve_workspace,
        )
    except Exception as exc:
        print(f"PHASE 9C-N20 ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    if args.execute_real_backend:
        print(f"\nPHASE 9C-N20: {summary['status']}")
    else:
        print("\nPHASE 9C-N20 DRY RUN: READY (0 LLM)")
    print(f"Artifact: {summary.get('artifact')}")

    return 0 if summary.get("status") in {
        "PASS",
        "READY / 0 LLM / NO MARKET OR FORUM MUTATION",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
