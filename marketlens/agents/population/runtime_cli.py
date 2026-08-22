"""Command-line entry point for MarketLens Phase 3B runtime population bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .fixture import build_population_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze a deterministic Phase 3A bounded Agent selection into a "
            "TwinMarket-compatible runtime database and audit manifest."
        )
    )
    parser.add_argument(
        "--source-db",
        default="data/sys_1000.db",
        help="read-only inherited TwinMarket persona source database",
    )
    parser.add_argument(
        "--population-size",
        type=int,
        required=True,
        help="provisional bounded population size N; final formal N is not frozen here",
    )
    parser.add_argument("--seed", required=True, help="explicit Phase 3A selection seed")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="new directory for manifest, selected IDs and bounded runtime database",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest = build_population_bundle(
        source_db=Path(args.source_db),
        population_size=args.population_size,
        seed=args.seed,
        output_dir=Path(args.output_dir),
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "population_size": manifest["selection"]["population_size"],
                "strategy_allocation": manifest["selection"]["strategy_allocation"],
                "user_type_counts": manifest["selected_population"]["user_type_counts"],
                "selected_agent_ids_sha256": manifest["selection"][
                    "selected_agent_ids_sha256"
                ],
                "output_dir": str(Path(args.output_dir).resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
