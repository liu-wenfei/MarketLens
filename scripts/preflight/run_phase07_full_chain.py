#!/usr/bin/env python3
"""Run the one-day MarketLens Phase 7C real-backend full-chain preflight."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.market.runtime.full_chain import (
    BANNER,
    DEFAULT_ACTIVATION_SEED,
    Phase07FullChainError,
    SUPPORTED_DATE,
    SUPPORTED_HISTORY_CUTOFF,
    run_phase07_full_chain,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "One-day NON-FORMAL Phase 7C preflight: Phase 6 graph/top users + "
            "Phase 4 activation + TwinMarket news/reasoning + inherited market."
        )
    )
    parser.add_argument(
        "--runtime-db",
        default="artifacts/preflight/phase05b/dev_population_n20/population_runtime.db",
    )
    parser.add_argument(
        "--population-manifest",
        default="artifacts/preflight/phase05b/dev_population_n20/population_manifest.json",
    )
    parser.add_argument(
        "--belief-csv",
        default="util/belief/belief_1000_0129.csv",
    )
    parser.add_argument("--config-path", default="config/api.yaml")
    parser.add_argument("--news-pickle", default="data/sorted_impact_news.pkl")
    parser.add_argument("--trading-calendar", default="data/trading_days.csv")
    parser.add_argument("--market-reference-csv", default="data/stock_data.csv")
    parser.add_argument("--artifact-root", default="artifacts/preflight/phase07")
    parser.add_argument("--current-date", default=SUPPORTED_DATE)
    parser.add_argument("--history-cutoff", default=SUPPORTED_HISTORY_CUTOFF)
    parser.add_argument("--seed", default=DEFAULT_ACTIVATION_SEED)
    parser.add_argument("--expected-news-count", type=int, default=19)
    parser.add_argument("--graph-start-date", default="2023-01-01")
    parser.add_argument("--similarity-threshold", type=float, default=0.1)
    parser.add_argument("--time-decay-factor", type=float, default=0.05)
    parser.add_argument("--top-fraction", type=float, default=0.10)
    parser.add_argument(
        "--execute-real-backend",
        action="store_true",
        help="required acknowledgement that inherited Agent reasoning will use the configured backend",
    )
    parser.add_argument(
        "--acknowledge-non-formal",
        action="store_true",
        help="required acknowledgement that this is engineering preflight, not formal evidence",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute_real_backend:
        raise SystemExit(
            "Refusing to run: --execute-real-backend is required. "
            "This runner has no paid dry-run mode."
        )
    if not args.acknowledge_non_formal:
        raise SystemExit(
            "Refusing to run: --acknowledge-non-formal is required."
        )

    print(BANNER)
    try:
        outcome = run_phase07_full_chain(
            repo_root=Path.cwd(),
            runtime_db=args.runtime_db,
            population_manifest=args.population_manifest,
            belief_csv=args.belief_csv,
            config_path=args.config_path,
            news_pickle=args.news_pickle,
            trading_calendar=args.trading_calendar,
            market_reference_csv=args.market_reference_csv,
            artifact_root=args.artifact_root,
            current_date=args.current_date,
            history_cutoff=args.history_cutoff,
            seed=args.seed,
            expected_news_count=args.expected_news_count,
            graph_start_date=args.graph_start_date,
            similarity_threshold=args.similarity_threshold,
            time_decay_factor=args.time_decay_factor,
            top_fraction=args.top_fraction,
        )
    except Phase07FullChainError as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps(outcome.summary, ensure_ascii=False, indent=2, default=str))
    print(f"Artifacts: {outcome.run_dir}")


if __name__ == "__main__":
    main()
