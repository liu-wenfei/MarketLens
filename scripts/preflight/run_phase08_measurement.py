#!/usr/bin/env python3
"""Generate a zero-LLM Phase 8 measurement from existing Phase 7C evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.measurement.agent_world import (
    MeasurementError,
    collect_agent_world_measurement,
    discover_latest_phase7c_run,
    write_measurement,
)


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 8 read-only measurement facade over existing Phase 7C "
            "inherited TwinMarket outputs. No LLM or market execution."
        )
    )
    parser.add_argument(
        "--phase7-run-dir",
        default=None,
        help=(
            "existing Phase 7C *_phase07_full_chain artifact directory; "
            "defaults to latest matching directory"
        ),
    )
    parser.add_argument(
        "--phase7-artifact-root",
        default="artifacts/preflight/phase07",
    )
    parser.add_argument(
        "--trading-calendar",
        default="data/trading_days.csv",
    )
    parser.add_argument(
        "--artifact-root",
        default="artifacts/preflight/phase08",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    run_dir = (
        Path(args.phase7_run_dir)
        if args.phase7_run_dir
        else discover_latest_phase7c_run(args.phase7_artifact_root)
    )

    try:
        measurement = collect_agent_world_measurement(
            phase7_run_dir=run_dir,
            trading_calendar=args.trading_calendar,
        )
    except MeasurementError as exc:
        print(f"PHASE 8 FAIL: {exc}", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    commit = _git_commit()
    run_id = (
        f"{now.strftime('%Y%m%dT%H%M%SZ')}_{commit[:8]}_phase08_measurement"
    )
    output_dir = Path(args.artifact_root) / run_id
    measurement["phase8_run"] = {
        "run_id": run_id,
        "generated_at_utc": now.isoformat(),
        "git_commit": commit,
        "new_llm_calls": 0,
        "market_execution": False,
    }

    output = write_measurement(output_dir / "measurement.json", measurement)
    print(json.dumps(measurement, indent=2, ensure_ascii=False))
    print(f"Artifact: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
