#!/usr/bin/env python3
"""Run the MarketLens Phase 5B one-day real-backend preflight.

This command is intentionally expensive and non-formal.  It refuses to execute
unless both explicit acknowledgement flags are supplied and the Git worktree is
clean, so every paid run is tied to an exact committed implementation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.agents.runtime.preflight import (  # noqa: E402
    BANNER,
    Phase05BPreflightError,
    run_phase05b_preflight,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        required=True,
        choices=("one-agent", "activation"),
        help="one-agent is Gate 5B-1; activation is Gate 5B-2 using Phase 4 sampling",
    )
    parser.add_argument(
        "--runtime-db",
        required=True,
        help="Phase 3B bounded population_runtime.db; never data/sys_1000.db directly",
    )
    parser.add_argument(
        "--population-manifest",
        default=None,
        help="paired Phase 3B population_manifest.json; defaults to runtime DB sibling",
    )
    parser.add_argument(
        "--belief-csv",
        default="util/belief/belief_1000_0129.csv",
        help="inherited Day-1 initial belief source (read-only)",
    )
    parser.add_argument(
        "--config-path",
        default="config/api.yaml",
        help="inherited TwinMarket backend config; contents/API keys are never copied to artifacts",
    )
    parser.add_argument(
        "--artifact-root",
        default="artifacts/preflight/phase05b",
        help="non-formal output root; generated run directories are git-ignored",
    )
    parser.add_argument("--user-id", default=None, help="required only for one-agent mode")
    parser.add_argument("--seed", default=None, help="required only for activation mode")
    parser.add_argument(
        "--preserve-failed-workspace",
        action="store_true",
        help="copy temporary runtime/forum state into the failed run directory for debugging",
    )
    parser.add_argument(
        "--execute-real-backend",
        action="store_true",
        help="explicitly allow inherited TwinMarket to contact its configured real backend",
    )
    parser.add_argument(
        "--acknowledge-non-formal",
        action="store_true",
        help="acknowledge that this is non-formal engineering preflight, not experiment evidence",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.execute_real_backend or not args.acknowledge_non_formal:
        raise SystemExit(
            "REAL BACKEND NOT STARTED. Phase 5B requires BOTH "
            "--execute-real-backend and --acknowledge-non-formal. "
            "Run the local pytest gate before using these flags."
        )

    print(BANNER)
    try:
        outcome = run_phase05b_preflight(
            repo_root=REPO_ROOT,
            runtime_db=Path(args.runtime_db),
            population_manifest=(
                Path(args.population_manifest) if args.population_manifest else None
            ),
            belief_csv=Path(args.belief_csv),
            config_path=Path(args.config_path),
            artifact_root=Path(args.artifact_root),
            mode=args.mode,
            user_id=args.user_id,
            seed=args.seed,
            preserve_failed_workspace=bool(args.preserve_failed_workspace),
        )
    except Phase05BPreflightError as exc:
        print(f"PRE-FLIGHT ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(outcome.summary, ensure_ascii=False, indent=2, default=str))
    print(f"Artifacts: {outcome.run_dir}")
    status = str(outcome.summary.get("status"))
    if status == "PASS":
        return 0
    if status == "NO_ACTIVE_AGENTS":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
