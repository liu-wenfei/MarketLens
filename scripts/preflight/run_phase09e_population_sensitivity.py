#!/usr/bin/env python3
"""One-click Phase 9E N10/N20/N30/N40 zero-LLM comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.market.population_sensitivity import BANNER, run_phase09e  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", default="data/sys_1000.db")
    parser.add_argument("--trading-calendar", default="data/trading_days.csv")
    parser.add_argument("--artifact-root", default="artifacts/preflight/phase09")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(BANNER)
    try:
        summary = run_phase09e(
            repo_root=REPO_ROOT,
            source_db=args.source_db,
            trading_calendar=args.trading_calendar,
            artifact_root=args.artifact_root,
        )
    except Exception as exc:
        print(f"PHASE 9E ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    compact = {
        "phase": summary["phase"],
        "status": summary["status"],
        "llm_calls": summary["llm_calls"],
        "market_execution": summary["market_execution"],
        "forum_mutation": summary["forum_mutation"],
        "final_population_size_frozen": summary["final_population_size_frozen"],
        "membership": summary["membership"],
        "candidates": {
            n: {
                "population": {
                    "strategy_counts": row["population"]["strategy_counts"],
                    "user_type_counts": row["population"]["user_type_counts"],
                    "selected_agent_ids_sha256": row["population"][
                        "selected_agent_ids_sha256"
                    ],
                    "runtime_sha256": row["population"]["runtime_sha256"],
                },
                "graph": {
                    "n_nodes": row["graph"]["n_nodes"],
                    "n_edges": row["graph"]["n_edges"],
                    "density": row["graph"]["density"],
                    "degree_mean": row["graph"]["degree_mean"],
                    "isolated_nodes": row["graph"]["isolated_nodes"],
                    "connected_components": row["graph"]["connected_components"],
                    "top_n": row["graph"]["prominence"]["top_n"],
                    "top_user_ids": row["graph"]["prominence"]["top_user_ids"],
                },
                "activation_reference_counts": row["activation"][
                    "reference_active_counts"
                ],
                "activation_100_seed": row["activation"]["aggregate"],
            }
            for n, row in summary["candidates"].items()
        },
        "marginal_comparisons": summary["marginal_comparisons"],
        "decision": summary["decision"],
        "validation_failures": summary["validation_failures"],
        "duration_seconds": summary["duration_seconds"],
        "artifact_report": summary["artifact_report"],
        "artifact_summary": summary["artifact_summary"],
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False))
    print(f"\nPHASE 9E: {summary['status']}")
    print(f"Report: {summary['artifact_report']}")
    print(f"Summary: {summary['artifact_summary']}")
    return 0 if summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
