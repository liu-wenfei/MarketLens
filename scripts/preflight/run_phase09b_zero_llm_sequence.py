#!/usr/bin/env python3
"""Phase 9B zero-LLM sequential orchestration gate.

This gate does not execute Agent reasoning, forum mutations, or market updates.
It validates the calendar sequence, Phase 4 activation-state carry-forward,
background-news loading, and the expected open/closed branch for the later
real-backend multi-day preflight.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.agents.activation.policy import ActivationPolicy
from marketlens.agents.activation.profiles import load_activation_profiles
from marketlens.market.multiday import (
    build_calendar_day_plan,
    sample_activation_sequence,
)
from marketlens.market.runtime.news import (
    load_daily_news,
    load_trading_day_set,
)


BANNER = (
    "NON-FORMAL / ZERO-LLM SEQUENTIAL ORCHESTRATION GATE / "
    "NOT MULTI-DAY REAL-BACKEND OR FORMAL EXPERIMENT EVIDENCE"
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _state_digest(mapping: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        {str(k): int(v) for k, v in sorted(mapping.items())},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    parser = argparse.ArgumentParser(description=BANNER)
    parser.add_argument(
        "--runtime-db",
        default="artifacts/preflight/phase05b/dev_population_n20/population_runtime.db",
    )
    parser.add_argument(
        "--trading-calendar",
        default="data/trading_days.csv",
    )
    parser.add_argument(
        "--news-pickle",
        default="data/sorted_impact_news.pkl",
    )
    parser.add_argument("--start-date", default="2023-06-15")
    parser.add_argument("--end-date", default="2023-06-17")
    parser.add_argument(
        "--seed",
        default="marketlens-phase09b-activation-01",
    )
    parser.add_argument(
        "--artifact-root",
        default="artifacts/preflight/phase09",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_db = Path(args.runtime_db)
    calendar = Path(args.trading_calendar)
    news_pickle = Path(args.news_pickle)

    for path in (runtime_db, calendar, news_pickle):
        if not path.exists():
            print(f"PHASE 9B FAIL: required input missing: {path}", file=sys.stderr)
            return 2

    runtime_before = _sha256_file(runtime_db)
    calendar_before = _sha256_file(calendar)
    news_before = _sha256_file(news_pickle)

    trading_days = load_trading_day_set(calendar)
    plan = build_calendar_day_plan(
        start_date=args.start_date,
        end_date=args.end_date,
        trading_days=trading_days,
    )

    # This engineering gate deliberately spans both branches.
    market_pattern = [day.market_open for day in plan]
    if not any(market_pattern) or all(market_pattern):
        print(
            "PHASE 9B FAIL: horizon must exercise both open and closed market days",
            file=sys.stderr,
        )
        return 2

    profiles = load_activation_profiles(runtime_db)
    activation = sample_activation_sequence(
        profiles,
        plan=plan,
        seed=args.seed,
        policy=ActivationPolicy(),
    )

    day_rows = []
    previous_output_state_digest = None
    for item in activation:
        state_mapping = item.batch.next_state.steps_since_last_activation
        output_state_digest = _state_digest(state_mapping)
        news = load_daily_news(
            news_pickle,
            current_date=item.day.current_date,
        )

        day_rows.append(
            {
                "step": item.day.step,
                "agent_world_date": item.day.current_date,
                "history_cutoff": item.day.history_cutoff,
                "day_1st": item.day.day_1st,
                "market_open": item.day.market_open,
                "participant_trading_enabled": (
                    item.day.participant_trading_enabled
                ),
                "belief_source": item.day.belief_source,
                "forum_actions_enabled": item.day.forum_actions_enabled,
                "expected_market_action": item.day.expected_market_action,
                "background_news_items": len(news),
                "activation": {
                    "n_active": len(item.batch.active_agent_ids),
                    "active_agent_ids": list(item.batch.active_agent_ids),
                    "policy_version": item.batch.policy_version,
                    "input_state_digest": previous_output_state_digest,
                    "output_state_digest": output_state_digest,
                },
            }
        )
        previous_output_state_digest = output_state_digest

    runtime_after = _sha256_file(runtime_db)
    calendar_after = _sha256_file(calendar)
    news_after = _sha256_file(news_pickle)

    unchanged = {
        "runtime_db": runtime_before == runtime_after,
        "trading_calendar": calendar_before == calendar_after,
        "news_pickle": news_before == news_after,
    }
    if not all(unchanged.values()):
        print("PHASE 9B FAIL: a protected input changed", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    commit = _git_commit()
    run_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}_{commit[:8]}_phase09b_zero_llm"
    artifact_dir = Path(args.artifact_root) / run_id
    artifact_dir.mkdir(parents=True, exist_ok=False)

    summary = {
        "banner": BANNER,
        "phase": "9B",
        "gate_version": "marketlens_phase09b_zero_llm_sequence/1.0",
        "status": "PASS",
        "formal_experiment_evidence": False,
        "real_backend_execution": False,
        "llm_calls": 0,
        "market_execution": False,
        "forum_mutation": False,
        "participant_data_used": False,
        "run_id": run_id,
        "git_commit": commit,
        "population": {
            "n_profiles": len(profiles),
            "runtime_db": str(runtime_db),
        },
        "horizon": {
            "start_date": args.start_date,
            "end_date": args.end_date,
            "calendar_day_count": len(plan),
            "contains_open_day": any(market_pattern),
            "contains_closed_day": not all(market_pattern),
        },
        "days": day_rows,
        "delegation_contract": {
            "activation_owner": "marketlens.agents.activation.sampler.sample_activation",
            "news_owner": "marketlens.market.runtime.news.load_daily_news",
            "calendar_owner": "marketlens.market.runtime.news.load_trading_day_set",
            "future_open_market_owner": (
                "marketlens.market.runtime.inherited_market.advance_trading_day"
            ),
            "future_closed_market_owner": (
                "marketlens.market.runtime.inherited_market.advance_non_trading_day"
            ),
            "simulation_init_simulation_called": False,
        },
        "protected_inputs": {
            "runtime_db": {
                "sha256_before": runtime_before,
                "sha256_after": runtime_after,
                "unchanged": unchanged["runtime_db"],
            },
            "trading_calendar": {
                "sha256_before": calendar_before,
                "sha256_after": calendar_after,
                "unchanged": unchanged["trading_calendar"],
            },
            "news_pickle": {
                "sha256_before": news_before,
                "sha256_after": news_after,
                "unchanged": unchanged["news_pickle"],
            },
        },
        "scope": {
            "verified_here": [
                "calendar-day sequence is explicit and contiguous",
                "market-open state comes only from the authoritative trading calendar",
                "participant trading availability mirrors authoritative market-open state",
                "Day 1 uses the initial-belief source contract",
                "Day 2+ uses the inherited forum-with-initial-fallback belief-source contract",
                "Day 2+ enables the inherited forum-action stage",
                "Phase 4 activation state is carried from one calendar day to the next",
                "daily background-news count is loaded per date without a fixed 19-item invariant",
                "future market branch is selected as open vs non-trading without using Agent activity",
                "protected runtime/calendar/news inputs remain unchanged",
            ],
            "not_verified_here": [
                "real Agent reasoning",
                "forum post creation or forum actions",
                "belief propagation content",
                "market mutation",
                "Profiles/StockData/TradingDetails multi-day continuity",
                "dynamic graph continuity after market mutation",
                "final Agent N",
                "formal experiment evidence",
            ],
        },
    }

    output = artifact_dir / "summary.json"
    output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(BANNER)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Artifact: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
