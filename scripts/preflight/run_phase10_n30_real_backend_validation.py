#!/usr/bin/env python3
"""Run the bounded Phase 10 N30 real-backend feasibility validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.market.phase10_n30_real_validation import (  # noqa: E402
    BANNER,
    DEFAULT_POPULATION_MANIFEST,
    DEFAULT_RUNTIME_DB,
    DRY_BANNER,
    run_phase10_n30,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the fixed same-seed N30 candidate on exactly "
            "2023-06-15..17 (OPEN/OPEN/CLOSED). This is bounded engineering "
            "feasibility only, not the 27-tick formal episode."
        )
    )
    parser.add_argument("--runtime-db", default=DEFAULT_RUNTIME_DB)
    parser.add_argument("--population-manifest", default=DEFAULT_POPULATION_MANIFEST)
    parser.add_argument("--source-db", default="data/sys_1000.db")
    parser.add_argument("--belief-csv", default="util/belief/belief_1000_0129.csv")
    parser.add_argument("--config-path", default="config/api.yaml")
    parser.add_argument("--news-pickle", default="data/sorted_impact_news.pkl")
    parser.add_argument("--trading-calendar", default="data/trading_days.csv")
    parser.add_argument("--artifact-root", default="artifacts/preflight/phase10")
    parser.add_argument(
        "--execute-real-backend",
        action="store_true",
        help="execute inherited Agent reasoning and Agent-world state updates",
    )
    parser.add_argument(
        "--acknowledge-non-formal",
        action="store_true",
        help="acknowledge this is engineering feasibility, not formal evidence",
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
        summary = run_phase10_n30(
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
        print(f"PHASE 10 N30 ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    compact = {
        "status": summary.get("status"),
        "mode": summary.get("mode"),
        "formal_experiment_evidence": summary.get("formal_experiment_evidence"),
        "population": summary.get("population"),
        "activation": summary.get("activation"),
        "horizon": summary.get("horizon"),
        "natural_multiday_coverage": summary.get("natural_multiday_coverage"),
        "continuity": summary.get("continuity"),
        "status_reasons": summary.get("status_reasons"),
        "duration_seconds": summary.get("duration_seconds"),
        "artifact": summary.get("artifact"),
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False, default=str))
    if args.execute_real_backend:
        print(f"\nPHASE 10 N30 REAL FEASIBILITY: {summary['status']}")
    else:
        print("\nPHASE 10 N30 DRY RUN: READY (0 LLM)")
    print(f"Artifact: {summary.get('artifact')}")

    return 0 if summary.get("status") in {
        "PASS",
        "READY / 0 LLM / NO MARKET OR FORUM MUTATION",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
