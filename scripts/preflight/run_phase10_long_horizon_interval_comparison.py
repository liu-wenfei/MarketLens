#!/usr/bin/env python3
"""Zero-cost Phase 10 long-horizon interval comparison.

Compares 11/13/15/17 participant decision-day symmetric dynamic designs.
No LLM is called, no participant outcome is generated or inspected, and the
frozen protocol is not modified.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.agents.population.fixture import build_population_bundle  # noqa: E402
from marketlens.experiment.decision_day_design import (  # noqa: E402
    calendar_dates,
    evaluate_activation_design,
)
from marketlens.experiment.formal_horizon import formal_horizon_seeds  # noqa: E402
from marketlens.experiment.long_horizon_design import (  # noqa: E402
    LONG_HORIZON_DECISION_DAY_CANDIDATES,
    build_long_horizon_candidates,
)
from marketlens.experiment.protocol import load_protocol  # noqa: E402


BANNER = (
    "NON-FORMAL / PHASE 10 LONG-HORIZON INTERVAL COMPARISON / ZERO-LLM / "
    "NOT FORMAL EXPERIMENT EVIDENCE"
)
POPULATION_SEED = "marketlens-dev-population-01"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state() -> dict[str, object]:
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
    ).strip()
    return {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "branch": subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "working_tree_dirty": bool(status),
        "status_porcelain": status,
    }


def environment_sources(trading_calendar: Path, news_path: Path) -> tuple[set[str], set[str]]:
    calendar = pd.read_csv(trading_calendar)
    if "pretrade_date" not in calendar.columns:
        raise RuntimeError("trading calendar missing inherited pretrade_date")
    open_dates = {
        pd.Timestamp(value).date().isoformat()
        for value in calendar["pretrade_date"].dropna().tolist()
    }

    news = pd.read_pickle(news_path)
    if "cal_date" not in news.columns or "news" not in news.columns:
        raise RuntimeError("background-news source missing cal_date/news")
    dates = pd.to_datetime(news["cal_date"])
    counts = dates.dt.date.astype(str).value_counts()
    duplicate_dates = sorted(counts[counts != 1].index.tolist())
    if duplicate_dates:
        raise RuntimeError(
            f"background-news daily rows are not unique: {duplicate_dates[:10]}"
        )
    return open_dates, set(dates.dt.date.astype(str).tolist())


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError("cannot write empty comparison CSV")
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def markdown_report(summary: dict[str, object]) -> str:
    rows = summary["candidates"]
    assert isinstance(rows, list)
    lines = [
        "# Phase 10 — Long-Horizon Interval Comparison",
        "",
        f"**Evidence class:** {BANNER}",
        "",
        "**Purpose:** Compare longer symmetric behavioural observation windows without using participant outcomes or LLM-generated content.",
        "",
        "## Interpretation rule",
        "",
        "- Candidate decision-day counts are `11/13/15/17`.",
        "- They map to `5/6/7/8` OPEN-state transitions per phase.",
        "- Participant makes one BUY/SELL/HOLD decision on every participant-visible OPEN date.",
        "- J0/J1 share the first OPEN state, J2/J3 share the central correction OPEN state, and J4 occurs on the final OPEN state.",
        "- Formal judgement events remain 5 across 3 dates.",
        "- Calendar-span fields describe simulated time, not real participant wall-clock retention.",
        "- No candidate is selected from behavioural effect size; no behavioural outcome is generated here.",
        "",
        "## Candidate comparison",
        "",
        "| Decision days | OPEN transitions / phase | Intermediate points / phase | Correction date | J4 date | Misinfo→correction elapsed calendar days | Correction→J4 elapsed calendar days | Visible calendar days (inclusive) | CLOSED ticks phase 1 / phase 2 | World ticks | Participant response events | N20 zero trajectories | N20 min mean active | N20 expected active-Agent calls | N20 PASS | Workload vs 11-day |",
        "|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    baseline_workload = rows[0]["N20"]["expected_active_agent_calls_per_episode"]
    for row in rows:
        n20 = row["N20"]
        workload_delta = n20["expected_active_agent_calls_per_episode"] / baseline_workload - 1
        lines.append(
            f"| {row['decision_days']} | {row['open_transitions_per_phase']} | "
            f"{row['intermediate_points_per_phase']} | {row['correction_date']} | "
            f"{row['later_measurement_date']} | {row['misinformation_to_correction_calendar_days']} | "
            f"{row['correction_to_later_calendar_days']} | {row['visible_calendar_days_inclusive']} | "
            f"{row['phase1_closed_ticks']} / {row['phase2_closed_ticks']} | {row['world_ticks']} | "
            f"{row['participant_response_events']} | "
            f"{n20['any_zero_on_decision_dates_trajectories']}/{n20['n_seeds']} | "
            f"{n20['minimum_decision_date_mean_active']:.3f} | "
            f"{n20['expected_active_agent_calls_per_episode']:.1f} | "
            f"{n20['sufficient_under_phase10_gate']} | {workload_delta:+.1%} |"
        )

    lines.extend([
        "",
        "## Exact decision dates",
        "",
    ])
    for row in rows:
        lines.append(
            f"- **{row['decision_days']} decisions:** " + ", ".join(row["decision_dates"])
        )

    lines.extend([
        "",
        "## Data interpretation",
        "",
        "- `open_transitions_per_phase`: experimental delay measured in participant-visible OPEN-state transitions.",
        "- `intermediate_points_per_phase`: behavioural-only observations strictly between formal anchor dates.",
        "- `misinformation_to_correction_calendar_days`: elapsed simulated calendar days from misinformation/J0-J1 date to correction/J2-J3 date.",
        "- `correction_to_later_calendar_days`: elapsed simulated calendar days from correction/J2-J3 date to J4.",
        "- `phase1_closed_ticks` / `phase2_closed_ticks`: CLOSED calendar ticks traversed by the Agent world inside each phase; these advance the world but do not permit participant trading.",
        "- `participant_response_events`: five formal judgement submissions plus behavioural decision submissions; burden proxy only, not measured completion time.",
        "- `world_ticks`: canonical Agent-world calendar ticks from T_init through J4 inclusive.",
        "- `expected_active_agent_calls_per_episode`: zero-LLM workload proxy equal to mean active Agents × world ticks.",
        "- N20/N30 diagnostics reuse the existing 100 predeclared activation seeds and Phase 10 adequacy thresholds.",
        "",
        "## What this comparison cannot decide",
        "",
        "It cannot establish which interval creates the strongest misinformation or correction effect, and it does not measure real human fatigue or real-time memory retention. Final interval choice remains a methodological trade-off informed by these structural/engineering diagnostics and later participant-flow pilot evidence.",
        "",
    ])
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

    protocol = load_protocol(REPO_ROOT / args.protocol)
    git = git_state()
    source_db = (REPO_ROOT / args.source_db).resolve()
    source_before = sha256_file(source_db)
    open_dates, news_dates = environment_sources(
        (REPO_ROOT / args.trading_calendar).resolve(),
        (REPO_ROOT / args.background_news).resolve(),
    )

    t_init = protocol["world"]["initialization_date"]
    t_visible = protocol["world"]["participant_visible_start_date"]
    candidates = build_long_horizon_candidates(
        initialization_date=t_init,
        visible_start_date=t_visible,
        open_dates=open_dates,
        news_dates=news_dates,
    )
    if not all(candidate.news_coverage_complete for candidate in candidates):
        raise RuntimeError("background-news coverage is incomplete for a long-horizon candidate")

    seeds = formal_horizon_seeds(protocol)
    selection_rule = protocol["population"]["selection_rule"]
    max_zero = int(selection_rule["critical_date_any_zero_max_trajectories"])
    minimum_mean = float(selection_rule["critical_date_min_mean_active_agents"])

    with tempfile.TemporaryDirectory(prefix="marketlens_phase10_long_horizon_") as temp:
        temp_root = Path(temp)
        runtime_dbs: dict[int, Path] = {}
        fixture_info: dict[str, dict[str, object]] = {}
        for n in (20, 30):
            output = temp_root / f"n{n}"
            manifest = build_population_bundle(
                source_db=source_db,
                population_size=n,
                seed=POPULATION_SEED,
                output_dir=output,
            )
            runtime_dbs[n] = output / "population_runtime.db"
            fixture_info[str(n)] = {
                "selected_agent_ids_sha256": manifest["selection"]["selected_agent_ids_sha256"],
                "runtime_sha256": manifest["runtime_fixture"]["fixture_sha256"],
            }

        rows: list[dict[str, object]] = []
        for candidate in candidates:
            row = candidate.as_dict()
            world_dates = calendar_dates(t_init, candidate.end_date)
            row["N20"] = evaluate_activation_design(
                runtime_db=runtime_dbs[20],
                population_size=20,
                world_dates=world_dates,
                decision_dates=candidate.decision_dates,
                seeds=seeds,
                max_zero_trajectories=max_zero,
                minimum_mean_active=minimum_mean,
            ).as_dict()
            row["N30"] = evaluate_activation_design(
                runtime_db=runtime_dbs[30],
                population_size=30,
                world_dates=world_dates,
                decision_dates=candidate.decision_dates,
                seeds=seeds,
                max_zero_trajectories=max_zero,
                minimum_mean_active=minimum_mean,
            ).as_dict()
            rows.append(row)

    source_after = sha256_file(source_db)
    if source_before != source_after:
        raise RuntimeError("source Agent database changed during long-horizon comparison")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}_{str(git['commit'])[:8]}_phase10_long_horizon_interval"
    artifact_dir = (REPO_ROOT / args.artifact_root / run_id).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=False)

    summary: dict[str, object] = {
        "banner": BANNER,
        "status": "PASS",
        "formal_experiment_evidence": False,
        "llm_api_calls": 0,
        "participant_outcomes_used": False,
        "protocol_mutated": False,
        "auto_selected_candidate": None,
        "git": git,
        "candidate_decision_days": list(LONG_HORIZON_DECISION_DAY_CANDIDATES),
        "formal_judgement_events": 5,
        "formal_judgement_dates": 3,
        "T_init": t_init,
        "T_visible": t_visible,
        "population_gate_reference": {
            "max_critical_any_zero_trajectories": max_zero,
            "minimum_critical_date_mean_active": minimum_mean,
            "activation_seed_count": len(seeds),
            "activation_seed_first": seeds[0],
            "activation_seed_last": seeds[-1],
        },
        "candidates": rows,
        "fixtures": fixture_info,
        "source_integrity": {
            "source_db": str(source_db),
            "sha256_before": source_before,
            "sha256_after": source_after,
            "unchanged": True,
        },
        "duration_seconds": round(time.monotonic() - started, 3),
        "run_id": run_id,
    }

    (artifact_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (artifact_dir / "report.md").write_text(markdown_report(summary), encoding="utf-8")

    baseline_workload = rows[0]["N20"]["expected_active_agent_calls_per_episode"]
    csv_rows: list[dict[str, object]] = []
    for row in rows:
        n20 = row["N20"]
        n30 = row["N30"]
        csv_rows.append({
            "decision_days": row["decision_days"],
            "open_transitions_per_phase": row["open_transitions_per_phase"],
            "intermediate_points_per_phase": row["intermediate_points_per_phase"],
            "decision_dates": ";".join(row["decision_dates"]),
            "correction_date": row["correction_date"],
            "later_measurement_date": row["later_measurement_date"],
            "misinformation_to_correction_calendar_days": row["misinformation_to_correction_calendar_days"],
            "correction_to_later_calendar_days": row["correction_to_later_calendar_days"],
            "visible_calendar_days_inclusive": row["visible_calendar_days_inclusive"],
            "phase1_closed_ticks": row["phase1_closed_ticks"],
            "phase2_closed_ticks": row["phase2_closed_ticks"],
            "visible_closed_ticks": row["visible_closed_ticks"],
            "world_ticks": row["world_ticks"],
            "participant_response_events": row["participant_response_events"],
            "news_coverage_complete": row["news_coverage_complete"],
            "N20_any_zero_trajectories": n20["any_zero_on_decision_dates_trajectories"],
            "N20_min_mean_active": n20["minimum_decision_date_mean_active"],
            "N20_overall_mean_active": n20["overall_mean_active"],
            "N20_expected_active_agent_calls": n20["expected_active_agent_calls_per_episode"],
            "N20_workload_delta_vs_11": n20["expected_active_agent_calls_per_episode"] / baseline_workload - 1,
            "N20_sufficient": n20["sufficient_under_phase10_gate"],
            "N30_any_zero_trajectories": n30["any_zero_on_decision_dates_trajectories"],
            "N30_min_mean_active": n30["minimum_decision_date_mean_active"],
            "N30_sufficient": n30["sufficient_under_phase10_gate"],
        })
    write_csv(artifact_dir / "long_horizon_comparison.csv", csv_rows)

    compact = {
        "status": "PASS",
        "llm_api_calls": 0,
        "candidate_decision_days": list(LONG_HORIZON_DECISION_DAY_CANDIDATES),
        "auto_selected_candidate": None,
        "candidates": [
            {
                "decision_days": row["decision_days"],
                "open_transitions_per_phase": row["open_transitions_per_phase"],
                "intermediate_points_per_phase": row["intermediate_points_per_phase"],
                "correction_date": row["correction_date"],
                "later_measurement_date": row["later_measurement_date"],
                "misinformation_to_correction_calendar_days": row["misinformation_to_correction_calendar_days"],
                "correction_to_later_calendar_days": row["correction_to_later_calendar_days"],
                "visible_calendar_days_inclusive": row["visible_calendar_days_inclusive"],
                "world_ticks": row["world_ticks"],
                "participant_response_events": row["participant_response_events"],
                "N20": row["N20"],
                "N30": row["N30"],
            }
            for row in rows
        ],
        "artifact_dir": str(artifact_dir),
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
