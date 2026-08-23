#!/usr/bin/env python3
"""Zero-cost Phase 10 decision-day design impact comparison.

Compares 0/2/4/7/9/11 behavioural decision-day designs without changing the
frozen protocol or inspecting behavioural outcomes. Two views are produced:

1. Cadence-only: all six counts sampled across one common 11-OPEN-day horizon.
2. Symmetric dynamic family: 7/9/11 decisions with 3/4/5 OPEN transitions per phase.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
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
    DECISION_DAY_CANDIDATES,
    build_cadence_candidates,
    build_dynamic_horizon_candidates,
    calendar_dates,
    evaluate_activation_design,
    first_open_dates,
)
from marketlens.experiment.formal_horizon import formal_horizon_seeds  # noqa: E402
from marketlens.experiment.protocol import load_protocol  # noqa: E402


BANNER = (
    "NON-FORMAL / PHASE 10 DECISION-DAY DESIGN IMPACT / ZERO-LLM / "
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
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True).strip()
    return {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip(),
        "branch": subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT, text=True).strip(),
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
        raise RuntimeError(f"background-news daily rows are not unique: {duplicate_dates[:10]}")
    return open_dates, set(dates.dt.date.astype(str).tolist())


def _fmt(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fields})


def markdown_report(summary: dict) -> str:
    lines = [
        "# Phase 10 — Decision-Day Design Impact Comparison",
        "",
        f"**Evidence class:** {BANNER}",
        "",
        "**Purpose:** Compare behavioural decision-day density and dynamic-window cost without using participant outcomes or LLM-generated content.",
        "",
        "## Interpretation rule",
        "",
        "- `0/2/4` are sparse behavioural-sampling baselines, not candidate replacements for the five formal judgement events.",
        "- `7/9/11` are symmetric dynamic-trajectory candidates: 2/3/4 intermediate behavioural points per phase respectively.",
        "- Formal judgement events remain 5 across 3 formal judgement dates in all comparisons.",
        "- The fixed-horizon table isolates decision cadence. The dynamic-family table allows horizon length to grow with decision density.",
        "- No design is selected because it produces a larger behavioural effect; no behavioural outcome is generated here.",
        "",
        "## A. Fixed-horizon cadence-only comparison",
        "",
        f"Common OPEN dates: `{', '.join(summary['common_horizon']['open_dates'])}`",
        "",
        f"Common world horizon: `{summary['common_horizon']['T_init']}` → `{summary['common_horizon']['T_end']}` (`{summary['common_horizon']['world_ticks']}` calendar ticks).",
        "",
        "Formal anchors on this common horizon: first OPEN date = J0/J1, middle OPEN anchor = J2/J3, final OPEN date = J4.",
        "",
        "| Decision days | Decision density | Formal anchors covered | Correction anchor | Intermediate points phase 1 / phase 2 | Max OPEN gap | Unobserved OPEN states | Participant response events | Structural interpretation |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["cadence_only"]:
        lines.append(
            f"| {row['decision_days']} | {row['decision_fraction']:.1%} | {row['formal_anchor_coverage']}/3 | "
            f"{row['correction_anchor_included']} | {row['phase1_intermediate_points']} / {row['phase2_intermediate_points']} | "
            f"{_fmt(row['max_gap_open_transitions'])} | {row['unobserved_open_states']} | "
            f"{row['participant_response_events']} | `{row['resolution_class']}` |"
        )
    lines.extend([
        "",
        "### Exact sampled dates",
        "",
    ])
    for row in summary["cadence_only"]:
        dates = ", ".join(row["selected_dates"]) if row["selected_dates"] else "none"
        lines.append(f"- **{row['decision_days']} decisions:** {dates}")

    lines.extend([
        "",
        "### What the sparse baselines mean",
        "",
        "- **0:** judgement-only benchmark; no BUY/SELL/HOLD trajectory is observed.",
        "- **2:** endpoint-only behavioural snapshots; no within-window trajectory and no correction-day behavioural anchor under the outcome-agnostic even-spacing rule.",
        "- **4:** one intermediate behavioural sample per phase, but still no correction-day behavioural anchor under even spacing.",
        "- **7:** first design in this requested set that covers all three formal anchors and provides two intermediate behavioural observations per phase.",
        "- **9:** covers all anchors and provides three intermediate behavioural observations per phase.",
        "- **11:** records every OPEN state in the common comparison horizon; no OPEN behavioural state is unobserved.",
        "",
        "## B. Symmetric dynamic-window family",
        "",
        "Here the participant makes a behavioural decision on every participant-visible OPEN date, so adding decision days also lengthens the canonical world horizon.",
        "",
        "| Decision days | OPEN transitions / phase | Intermediate points / phase | Correction date | Later J4 | World ticks | Visible CLOSED ticks | N20 critical-zero trajectories | N20 min mean active | N20 expected active-Agent calls | N20 PASS | Workload vs 7-day |",
        "|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    base_workload = summary["dynamic_family"][0]["N20"]["expected_active_agent_calls_per_episode"]
    for row in summary["dynamic_family"]:
        n20 = row["N20"]
        workload_delta = n20["expected_active_agent_calls_per_episode"] / base_workload - 1
        lines.append(
            f"| {row['decision_days']} | {row['open_transitions_per_phase']} | {row['intermediate_points_per_phase']} | "
            f"{row['correction_date']} | {row['later_measurement_date']} | {row['world_ticks']} | {row['visible_closed_ticks']} | "
            f"{n20['any_zero_on_decision_dates_trajectories']}/{n20['n_seeds']} | "
            f"{n20['minimum_decision_date_mean_active']:.3f} | {n20['expected_active_agent_calls_per_episode']:.1f} | "
            f"{n20['sufficient_under_phase10_gate']} | {workload_delta:+.1%} |"
        )

    lines.extend([
        "",
        "## C. Data fields for dissertation explanation",
        "",
        "Use these as engineering/design evidence, not as participant-behaviour results:",
        "",
        "- `decision_days`: number of OPEN simulated dates requiring BUY/SELL/HOLD.",
        "- `decision_fraction`: fraction of the common 11 OPEN states with a behavioural observation.",
        "- `formal_anchor_coverage`: whether behaviour is recorded at J0/J1, J2/J3, and J4 dates.",
        "- `phase*_intermediate_points`: behavioural-only samples available to describe trajectory shape between formal measurements.",
        "- `max_gap_open_transitions`: largest unobserved gap between behavioural samples, measured in OPEN-state transitions.",
        "- `unobserved_open_states`: OPEN states with no behavioural decision in the fixed-horizon comparison.",
        "- `participant_response_events`: 5 formal judgement events plus behavioural decision submissions; this is a burden proxy, not measured wall-clock time.",
        "- `world_ticks`: calendar-day Agent-world generation required by the dynamic design.",
        "- `expected_active_agent_calls_per_episode`: zero-LLM activation expectation (`mean active Agents × world ticks`), used only as a canonical-generation workload proxy.",
        "- `critical-zero trajectories` and `minimum mean active`: the existing Phase 10 activation-adequacy diagnostics, evaluated with the same 100 predeclared seeds.",
        "",
        "## D. What this experiment does NOT establish",
        "",
        "It does not show that 9 decisions produce a larger misinformation effect than 7 or 11, does not estimate human fatigue, and does not call an LLM. Those questions require methodological judgement and later participant-flow pilot evidence, not outcome-driven protocol selection.",
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
    common_open = first_open_dates(open_dates, start=t_visible, count=11)
    common_end = common_open[-1]
    common_world_dates = calendar_dates(t_init, common_end)
    if not all(value in news_dates for value in common_world_dates):
        raise RuntimeError("background-news coverage is incomplete on common 11-OPEN-day comparison horizon")

    cadence = build_cadence_candidates(common_open)
    dynamic = build_dynamic_horizon_candidates(
        initialization_date=t_init,
        visible_start_date=t_visible,
        open_dates=open_dates,
        news_dates=news_dates,
    )

    seeds = formal_horizon_seeds(protocol)
    rule = protocol["population"]["selection_rule"]
    max_zero = int(rule["critical_date_any_zero_max_trajectories"])
    min_mean = float(rule["critical_date_min_mean_active_agents"])

    with tempfile.TemporaryDirectory(prefix="marketlens_phase10_decision_design_") as temp:
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

        cadence_rows: list[dict[str, object]] = []
        for candidate in cadence:
            row = candidate.as_dict()
            row["N20"] = evaluate_activation_design(
                runtime_db=runtime_dbs[20], population_size=20, world_dates=common_world_dates,
                decision_dates=candidate.selected_dates, seeds=seeds,
                max_zero_trajectories=max_zero, minimum_mean_active=min_mean,
            ).as_dict()
            row["N30"] = evaluate_activation_design(
                runtime_db=runtime_dbs[30], population_size=30, world_dates=common_world_dates,
                decision_dates=candidate.selected_dates, seeds=seeds,
                max_zero_trajectories=max_zero, minimum_mean_active=min_mean,
            ).as_dict()
            cadence_rows.append(row)

        dynamic_rows: list[dict[str, object]] = []
        for candidate in dynamic:
            row = candidate.as_dict()
            world_dates = calendar_dates(t_init, candidate.end_date)
            row["N20"] = evaluate_activation_design(
                runtime_db=runtime_dbs[20], population_size=20, world_dates=world_dates,
                decision_dates=candidate.decision_dates, seeds=seeds,
                max_zero_trajectories=max_zero, minimum_mean_active=min_mean,
            ).as_dict()
            row["N30"] = evaluate_activation_design(
                runtime_db=runtime_dbs[30], population_size=30, world_dates=world_dates,
                decision_dates=candidate.decision_dates, seeds=seeds,
                max_zero_trajectories=max_zero, minimum_mean_active=min_mean,
            ).as_dict()
            dynamic_rows.append(row)

    source_after = sha256_file(source_db)
    if source_before != source_after:
        raise RuntimeError("source Agent database changed during decision-day design comparison")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}_{str(git['commit'])[:8]}_phase10_decision_day_design"
    artifact_dir = (REPO_ROOT / args.artifact_root / run_id).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=False)

    summary = {
        "banner": BANNER,
        "status": "PASS",
        "formal_experiment_evidence": False,
        "llm_api_calls": 0,
        "participant_outcomes_used": False,
        "protocol_mutated": False,
        "git": git,
        "comparison_counts": list(DECISION_DAY_CANDIDATES),
        "formal_judgement_events": 5,
        "formal_judgement_dates": 3,
        "common_horizon": {
            "T_init": t_init,
            "T_visible": t_visible,
            "T_end": common_end,
            "world_ticks": len(common_world_dates),
            "open_dates": list(common_open),
            "formal_anchor_dates": [common_open[0], common_open[5], common_open[10]],
            "background_news_complete": True,
        },
        "sampling_rule": "endpoint-preserving approximately-even OPEN-date spacing; outcome-agnostic",
        "cadence_only": cadence_rows,
        "dynamic_family": dynamic_rows,
        "population_gate_reference": {
            "max_critical_any_zero_trajectories": max_zero,
            "minimum_critical_date_mean_active": min_mean,
            "activation_seed_count": len(seeds),
            "activation_seed_first": seeds[0],
            "activation_seed_last": seeds[-1],
        },
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

    (artifact_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (artifact_dir / "report.md").write_text(markdown_report(summary), encoding="utf-8")

    cadence_csv_rows = []
    for row in cadence_rows:
        cadence_csv_rows.append({
            "decision_days": row["decision_days"],
            "selected_dates": ";".join(row["selected_dates"]),
            "decision_fraction": row["decision_fraction"],
            "formal_anchor_coverage": row["formal_anchor_coverage"],
            "correction_anchor_included": row["correction_anchor_included"],
            "phase1_intermediate_points": row["phase1_intermediate_points"],
            "phase2_intermediate_points": row["phase2_intermediate_points"],
            "max_gap_open_transitions": row["max_gap_open_transitions"],
            "unobserved_open_states": row["unobserved_open_states"],
            "participant_response_events": row["participant_response_events"],
            "resolution_class": row["resolution_class"],
            "N20_any_zero_trajectories": row["N20"]["any_zero_on_decision_dates_trajectories"],
            "N20_min_mean_active": row["N20"]["minimum_decision_date_mean_active"],
            "N30_any_zero_trajectories": row["N30"]["any_zero_on_decision_dates_trajectories"],
            "N30_min_mean_active": row["N30"]["minimum_decision_date_mean_active"],
        })
    write_csv(
        artifact_dir / "cadence_only_comparison.csv",
        cadence_csv_rows,
        list(cadence_csv_rows[0].keys()),
    )

    dynamic_csv_rows = []
    base_workload = dynamic_rows[0]["N20"]["expected_active_agent_calls_per_episode"]
    for row in dynamic_rows:
        dynamic_csv_rows.append({
            "decision_days": row["decision_days"],
            "open_transitions_per_phase": row["open_transitions_per_phase"],
            "intermediate_points_per_phase": row["intermediate_points_per_phase"],
            "decision_dates": ";".join(row["decision_dates"]),
            "correction_date": row["correction_date"],
            "later_measurement_date": row["later_measurement_date"],
            "end_date": row["end_date"],
            "world_ticks": row["world_ticks"],
            "visible_closed_ticks": row["visible_closed_ticks"],
            "N20_any_zero_trajectories": row["N20"]["any_zero_on_decision_dates_trajectories"],
            "N20_min_mean_active": row["N20"]["minimum_decision_date_mean_active"],
            "N20_overall_mean_active": row["N20"]["overall_mean_active"],
            "N20_expected_active_agent_calls": row["N20"]["expected_active_agent_calls_per_episode"],
            "N20_workload_delta_vs_7": row["N20"]["expected_active_agent_calls_per_episode"] / base_workload - 1,
            "N20_sufficient": row["N20"]["sufficient_under_phase10_gate"],
            "N30_sufficient": row["N30"]["sufficient_under_phase10_gate"],
        })
    write_csv(
        artifact_dir / "symmetric_dynamic_family.csv",
        dynamic_csv_rows,
        list(dynamic_csv_rows[0].keys()),
    )

    compact = {
        "status": "PASS",
        "llm_api_calls": 0,
        "comparison_counts": list(DECISION_DAY_CANDIDATES),
        "common_horizon": summary["common_horizon"],
        "cadence_only": [
            {
                "decision_days": row["decision_days"],
                "selected_dates": row["selected_dates"],
                "formal_anchor_coverage": row["formal_anchor_coverage"],
                "correction_anchor_included": row["correction_anchor_included"],
                "phase1_intermediate_points": row["phase1_intermediate_points"],
                "phase2_intermediate_points": row["phase2_intermediate_points"],
                "max_gap_open_transitions": row["max_gap_open_transitions"],
                "unobserved_open_states": row["unobserved_open_states"],
                "participant_response_events": row["participant_response_events"],
                "resolution_class": row["resolution_class"],
            }
            for row in cadence_rows
        ],
        "dynamic_family": [
            {
                "decision_days": row["decision_days"],
                "world_ticks": row["world_ticks"],
                "correction_date": row["correction_date"],
                "later_measurement_date": row["later_measurement_date"],
                "N20": row["N20"],
                "N30": row["N30"],
            }
            for row in dynamic_rows
        ],
        "artifact_dir": str(artifact_dir),
    }
    print(json.dumps(compact, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
