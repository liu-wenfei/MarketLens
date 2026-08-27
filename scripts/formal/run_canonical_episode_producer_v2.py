#!/usr/bin/env python3
"""MarketLens v2 canonical episode producer.

Default invocation is dry-run / zero LLM. Paid formal execution remains limited
to one explicit v2 episode slot and requires explicit acknowledgement.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.episode.contract_v2 import EPISODE_IDS  # noqa: E402
from marketlens.episode.producer_v2 import (  # noqa: E402
    CanonicalEpisodeProducerError,
    dry_run_summary,
    execute_formal_episode_slot,
    finalize_formal_episode_pool,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run the MarketLens v2 English-forum producer, execute exactly "
            "one paid predeclared v2 episode slot, or zero-LLM finalize the v2 pool."
        )
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--execute-slot",
        choices=EPISODE_IDS,
        help=(
            "execute exactly one paid v2 formal episode slot; there is intentionally "
            "no execute-all option"
        ),
    )
    group.add_argument(
        "--finalize-pool",
        action="store_true",
        help="zero-LLM: freeze the v2 pool manifest after all three slots validate",
    )
    parser.add_argument(
        "--acknowledge-formal-execution",
        action="store_true",
        help="required with --execute-slot; acknowledges paid/irreversible v2 generation",
    )
    parser.add_argument(
        "--runtime-db",
        default=None,
        help="optional explicit path to the already-prepared frozen N30 runtime DB",
    )
    parser.add_argument(
        "--population-manifest",
        default=None,
        help="optional explicit path to the frozen N30 population manifest",
    )
    parser.add_argument("--config-path", default="config/api.yaml")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.execute_slot:
            result = execute_formal_episode_slot(
                repo_root=REPO_ROOT,
                episode_id=args.execute_slot,
                acknowledge_formal_execution=args.acknowledge_formal_execution,
                runtime_db=args.runtime_db,
                population_manifest=args.population_manifest,
                config_path=args.config_path,
            )
        elif args.finalize_pool:
            if args.acknowledge_formal_execution:
                raise CanonicalEpisodeProducerError(
                    "--acknowledge-formal-execution is only valid with --execute-slot"
                )
            result = finalize_formal_episode_pool(repo_root=REPO_ROOT)
        else:
            if args.acknowledge_formal_execution:
                raise CanonicalEpisodeProducerError(
                    "--acknowledge-formal-execution requires --execute-slot"
                )
            result = dry_run_summary(
                repo_root=REPO_ROOT,
                config_path=args.config_path,
                runtime_db=args.runtime_db,
                population_manifest=args.population_manifest,
            )
    except Exception as exc:
        print(f"MARKETLENS V2 PRODUCER ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(result.get("banner", "MARKETLENS V2"))
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
