#!/usr/bin/env python3
"""Phase 10 zero-LLM exact-horizon N20/N30 adequacy preflight."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.agents.population.fixture import build_population_bundle  # noqa: E402
from marketlens.experiment.formal_horizon import (  # noqa: E402
    decide_population,
    evaluate_candidate,
    formal_horizon_seeds,
)
from marketlens.experiment.protocol import load_protocol  # noqa: E402


BANNER = (
    "NON-FORMAL / PHASE 10 EXACT-HORIZON ZERO-LLM N20-N30 GATE / "
    "NOT FORMAL EXPERIMENT EVIDENCE"
)
POPULATION_SEED = "marketlens-dev-population-01"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state() -> dict[str, str]:
    return {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "branch": subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "status_porcelain": subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
        ).strip(),
    }


def validate_calendar_and_news(protocol: dict, trading_calendar: Path, news_path: Path) -> dict:
    calendar = pd.read_csv(trading_calendar)
    if "pretrade_date" not in calendar.columns:
        raise RuntimeError("trading calendar is missing inherited pretrade_date field")
    trading_days = {
        pd.Timestamp(value).date().isoformat()
        for value in calendar["pretrade_date"].dropna().tolist()
    }

    news = pd.read_pickle(news_path)
    if "cal_date" not in news.columns or "news" not in news.columns:
        raise RuntimeError("background-news source is missing cal_date/news")
    news = news.copy()
    news["cal_date"] = pd.to_datetime(news["cal_date"])

    rows = []
    missing_news_dates = []
    calendar_mismatches = []
    for row in protocol["timeline"]:
        current_date = row["agent_world_date"]
        inherited_open = current_date in trading_days
        protocol_open = row["market_status"] == "OPEN"
        if inherited_open != protocol_open:
            calendar_mismatches.append(current_date)
        matches = news[news["cal_date"] == pd.Timestamp(current_date)]
        if len(matches) != 1:
            missing_news_dates.append(current_date)
            news_items = None
        else:
            payload = matches.iloc[0]["news"]
            news_items = len(payload) if isinstance(payload, list) else None
        rows.append(
            {
                "world_tick": row["world_tick"],
                "agent_world_date": current_date,
                "protocol_market_status": row["market_status"],
                "inherited_pretrade_date_open": inherited_open,
                "background_news_rows": len(matches),
                "background_news_items": news_items,
            }
        )

    if calendar_mismatches:
        raise RuntimeError(f"protocol OPEN/CLOSED mismatch: {calendar_mismatches}")
    if missing_news_dates:
        raise RuntimeError(f"background-news coverage missing/duplicated: {missing_news_dates}")
    return {
        "calendar_authority": "data/trading_days.csv:pretrade_date",
        "calendar_mismatches": calendar_mismatches,
        "background_news_complete": True,
        "days": rows,
    }


def markdown_report(summary: dict) -> str:
    lines = [
        "# Phase 10 — Exact-Horizon Zero-LLM N20/N30 Gate",
        "",
        f"**Evidence class:** {summary['banner']}",
        f"**Status:** {summary['status']}",
        f"**Git commit:** `{summary['git']['commit']}`",
        f"**Git working tree dirty during run:** `{bool(summary['git']['status_porcelain'])}`",
        "",
        "## Frozen horizon",
        "",
        f"- T_init: `{summary['protocol']['T_init']}`",
        f"- T_visible: `{summary['protocol']['T_visible']}`",
        f"- T_end: `{summary['protocol']['T_end']}`",
        f"- world ticks: `{summary['protocol']['formal_world_ticks']}`",
        f"- participant-critical dates: `{', '.join(summary['protocol']['participant_critical_dates'])}`",
        "",
        "## Candidate results",
        "",
        "| Candidate | Sufficient | Critical trajectories with any zero | Minimum critical-date mean active | Overall mean active |",
        "|---|---:|---:|---:|---:|",
    ]
    for n in (20, 30):
        row = summary["candidates"][str(n)]
        lines.append(
            f"| N{n} | {row['sufficient']} | {row['critical_any_zero_trajectories']}/{row['n_seeds']} | "
            f"{row['minimum_critical_mean_active']:.3f} | {row['overall_mean_active']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- `{summary['decision']['decision']}`",
            f"- {summary['decision']['reason']}",
            "",
            "This preflight does not generate the canonical Agent world, does not call an LLM, does not mutate the inherited market/forum, and is not formal experiment evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", default="data/sys_1000.db")
    parser.add_argument("--trading-calendar", default="data/trading_days.csv")
    parser.add_argument("--background-news", default="data/sorted_impact_news.pkl")
    parser.add_argument("--protocol", default="marketlens/experiment/protocol_v1.json")
    parser.add_argument("--artifact-root", default="artifacts/preflight/phase10")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(BANNER)
    started = time.monotonic()
    try:
        protocol = load_protocol(REPO_ROOT / args.protocol)
        source_db = (REPO_ROOT / args.source_db).resolve()
        source_before = sha256_file(source_db)
        environment = validate_calendar_and_news(
            protocol,
            (REPO_ROOT / args.trading_calendar).resolve(),
            (REPO_ROOT / args.background_news).resolve(),
        )
        git = git_state()
        seeds = formal_horizon_seeds(protocol)

        with tempfile.TemporaryDirectory(prefix="marketlens_phase10_population_") as temp:
            temp_root = Path(temp)
            results = {}
            manifests = {}
            for n in (20, 30):
                output = temp_root / f"n{n}"
                manifest = build_population_bundle(
                    source_db=source_db,
                    population_size=n,
                    seed=POPULATION_SEED,
                    output_dir=output,
                )
                result = evaluate_candidate(
                    runtime_db=output / "population_runtime.db",
                    population_size=n,
                    protocol=protocol,
                    seeds=seeds,
                )
                results[n] = result
                manifests[n] = {
                    "selected_agent_ids_sha256": manifest["selection"]["selected_agent_ids_sha256"],
                    "runtime_sha256": manifest["runtime_fixture"]["fixture_sha256"],
                    "strategy_allocation": manifest["selection"]["strategy_allocation"],
                    "user_type_counts": manifest["selected_population"]["user_type_counts"],
                }

        source_after = sha256_file(source_db)
        if source_before != source_after:
            raise RuntimeError("source Agent database changed during zero-LLM preflight")

        decision = decide_population(results[20], results[30])
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"{timestamp}_{git['commit'][:8]}_phase10_formal_horizon"
        artifact_dir = (REPO_ROOT / args.artifact_root / run_id).resolve()
        artifact_dir.mkdir(parents=True, exist_ok=False)

        summary = {
            "banner": BANNER,
            "phase": "10",
            "status": "PASS",
            "formal_experiment_evidence": False,
            "llm_api_calls": 0,
            "market_execution": False,
            "forum_mutation": False,
            "participant_data_used": False,
            "git": git,
            "protocol": {
                "version": protocol["protocol_version"],
                "T_init": protocol["world"]["initialization_date"],
                "T_visible": protocol["world"]["participant_visible_start_date"],
                "T_end": protocol["world"]["end_date"],
                "formal_world_ticks": protocol["world"]["formal_world_ticks"],
                "participant_critical_dates": protocol["participant_critical_dates"],
            },
            "environment_validation": environment,
            "population_seed": POPULATION_SEED,
            "activation_seed_count": len(seeds),
            "activation_seed_first": seeds[0],
            "activation_seed_last": seeds[-1],
            "fixtures": {str(n): manifests[n] for n in (20, 30)},
            "candidates": {str(n): results[n].as_dict() for n in (20, 30)},
            "decision": decision,
            "source_integrity": {
                "source_db": str(source_db),
                "sha256_before": source_before,
                "sha256_after": source_after,
                "unchanged": source_before == source_after,
            },
            "duration_seconds": round(time.monotonic() - started, 3),
            "run_id": run_id,
        }
        summary_path = artifact_dir / "summary.json"
        report_path = artifact_dir / "report.md"
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        report_path.write_text(markdown_report(summary), encoding="utf-8")
    except Exception as exc:
        print(f"PHASE 10 PREFLIGHT ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    compact = {
        "status": summary["status"],
        "llm_api_calls": summary["llm_api_calls"],
        "formal_world_ticks": summary["protocol"]["formal_world_ticks"],
        "critical_dates": summary["protocol"]["participant_critical_dates"],
        "N20": summary["candidates"]["20"],
        "N30": summary["candidates"]["30"],
        "decision": summary["decision"],
        "artifact_dir": str(artifact_dir),
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
