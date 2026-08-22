#!/usr/bin/env python3
"""Phase 7D-2: forced dynamic-top-user news-routing coverage gate.

NON-FORMAL branch coverage only. The gate does not provide natural Phase 4
activation evidence and does not advance the Agent market.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from marketlens.agents.runtime.preflight import (
    collect_git_state,
    create_empty_forum_db,
    load_day1_frames,
    load_initial_beliefs,
    sha256_file,
    verify_population_fixture,
)
from marketlens.agents.social.graph import build_bounded_social_graph
from marketlens.agents.social.prominence import make_prominence_snapshot
from marketlens.market.runtime.full_chain import execute_active_agents
from marketlens.market.runtime.inherited_market import reset_agent_world
from marketlens.market.runtime.news import load_daily_news, load_trading_day_set
from trader.prompts import TradingPrompt


BANNER = (
    "NON-FORMAL / FORCED DYNAMIC TOP-USER NEWS-ROUTING COVERAGE GATE / "
    "NOT NATURAL ACTIVATION OR FORMAL EXPERIMENT EVIDENCE"
)
GATE_VERSION = "marketlens_phase07d2_top_user_news_routing/1.0"
CURRENT_DATE = "2023-06-15"
HISTORY_CUTOFF = "2023-06-14"
EXPECTED_NEWS_COUNT = 19


class Phase07D2Error(RuntimeError):
    pass


def _existing_file(value: str | Path, *, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise Phase07D2Error(f"{label} not found: {path}")
    return path


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalise_news_for_inherited_prompt(news_items: list[Any]) -> list[str]:
    """Mirror inherited _read_news cleaning for audit comparison only."""
    cleaned = [str(news) for news in news_items if news and not pd.isna(news)]
    return list(dict.fromkeys(cleaned))


def _find_news_prompt_exchange(
    conversation: list[Any], *, expected_prompt: str
) -> tuple[int, str]:
    matches: list[int] = []
    for idx, item in enumerate(conversation):
        if not isinstance(item, dict):
            continue
        if item.get("role") == "user" and item.get("content") == expected_prompt:
            matches.append(idx)

    if len(matches) != 1:
        raise Phase07D2Error(
            "expected exactly one inherited news-analysis prompt in conversation "
            f"history, found {len(matches)}"
        )

    idx = matches[0]
    if idx + 1 >= len(conversation):
        raise Phase07D2Error("news-analysis prompt has no following assistant response")

    response = conversation[idx + 1]
    if not isinstance(response, dict) or response.get("role") != "assistant":
        raise Phase07D2Error(
            "entry immediately after inherited news prompt is not an assistant response"
        )
    content = response.get("content")
    if not isinstance(content, str) or not content.strip():
        raise Phase07D2Error("inherited news-analysis assistant response is empty")
    return idx, content


def _run_id(commit: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short = commit[:8] if commit else "nogit"
    return f"{stamp}_{short}_phase07_top_user_news"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-db",
        default="artifacts/preflight/phase05b/dev_population_n20/population_runtime.db",
    )
    parser.add_argument(
        "--population-manifest",
        default="artifacts/preflight/phase05b/dev_population_n20/population_manifest.json",
    )
    parser.add_argument("--belief-csv", default="util/belief/belief_1000_0129.csv")
    parser.add_argument("--config-path", default="config/api.yaml")
    parser.add_argument("--news-pickle", default="data/sorted_impact_news.pkl")
    parser.add_argument("--trading-calendar", default="data/trading_days.csv")
    parser.add_argument("--artifact-root", default="artifacts/preflight/phase07")
    parser.add_argument("--current-date", default=CURRENT_DATE)
    parser.add_argument("--history-cutoff", default=HISTORY_CUTOFF)
    parser.add_argument("--expected-news-count", type=int, default=EXPECTED_NEWS_COUNT)
    parser.add_argument("--graph-start-date", default="2023-01-01")
    parser.add_argument("--similarity-threshold", type=float, default=0.1)
    parser.add_argument("--time-decay-factor", type=float, default=0.05)
    parser.add_argument("--top-fraction", type=float, default=0.10)
    parser.add_argument("--execute-real-backend", action="store_true")
    parser.add_argument("--acknowledge-forced-routing", action="store_true")
    parser.add_argument("--acknowledge-non-formal", action="store_true")
    args = parser.parse_args()

    if args.current_date != CURRENT_DATE or args.history_cutoff != HISTORY_CUTOFF:
        raise SystemExit(
            "Phase 7D-2 is hard-limited to 2023-06-15 with history cutoff 2023-06-14."
        )
    if not args.execute_real_backend:
        raise SystemExit("refusing to run without --execute-real-backend")
    if not args.acknowledge_forced_routing:
        raise SystemExit("refusing to run without --acknowledge-forced-routing")
    if not args.acknowledge_non_formal:
        raise SystemExit("refusing to run without --acknowledge-non-formal")

    git_state = collect_git_state(REPO_ROOT)
    if not git_state.get("clean"):
        raise SystemExit(
            "Phase 7D-2 requires a clean git tree so the artifact maps to one commit:\n"
            + str(git_state.get("status") or "")
        )
    commit = str(git_state.get("commit") or "")

    runtime_db = _existing_file(args.runtime_db, label="bounded runtime DB")
    manifest_path = _existing_file(args.population_manifest, label="population manifest")
    belief_csv = _existing_file(args.belief_csv, label="belief CSV")
    config_path = _existing_file(args.config_path, label="backend config")
    news_pickle = _existing_file(args.news_pickle, label="TwinMarket news pickle")
    trading_calendar = _existing_file(args.trading_calendar, label="TwinMarket trading calendar")

    fixture = verify_population_fixture(runtime_db, manifest_path)
    if args.current_date not in load_trading_day_set(trading_calendar):
        raise Phase07D2Error(f"{args.current_date} is not a TwinMarket trading day")

    news_items = load_daily_news(news_pickle, current_date=args.current_date)
    if len(news_items) != int(args.expected_news_count):
        raise Phase07D2Error(
            f"daily news count drift: expected {args.expected_news_count}, found {len(news_items)}"
        )

    protected = {
        "source_runtime_db": fixture.runtime_db,
        "population_manifest": fixture.manifest_path,
        "belief_csv": belief_csv,
        "news_pickle": news_pickle,
        "trading_calendar": trading_calendar,
    }
    hashes_before = {name: sha256_file(path) for name, path in protected.items()}

    started = datetime.now(timezone.utc)
    run_dir = Path(args.artifact_root).expanduser().resolve() / _run_id(commit)
    run_dir.mkdir(parents=True, exist_ok=False)
    print(BANNER)

    with tempfile.TemporaryDirectory(prefix="marketlens_phase07d2_") as temp_name:
        workspace = Path(temp_name)
        working_db = workspace / "runtime.db"
        working_forum = workspace / "forum.db"
        shutil.copy2(fixture.runtime_db, working_db)
        create_empty_forum_db(working_forum)

        reset_result = reset_agent_world(
            current_date=args.current_date,
            runtime_db=working_db,
            forum_db=working_forum,
            protected_paths=(fixture.runtime_db,),
        )

        built_graph = build_bounded_social_graph(
            runtime_db=working_db,
            history_cutoff=args.history_cutoff,
            graph_start_date=args.graph_start_date,
            similarity_threshold=args.similarity_threshold,
            time_decay_factor=args.time_decay_factor,
        )
        prominence = make_prominence_snapshot(built_graph, top_fraction=args.top_fraction)
        top_user_ids = tuple(str(uid) for uid in prominence["prominence"]["top_user_ids"])
        if not top_user_ids:
            raise Phase07D2Error("Phase 6 prominence produced no dynamic top users")

        # Branch-coverage selection comes only from the Phase 6 dynamic ranking.
        forced_user_id = top_user_ids[0]
        if forced_user_id not in set(fixture.population_ids):
            raise Phase07D2Error("selected dynamic top user is outside bounded population")

        df_strategy, df_stock = load_day1_frames(working_db)
        belief_args = load_initial_beliefs(belief_csv, (forced_user_id,))
        reasoning_log_dir = run_dir / "inherited_reasoning"
        reasoning_log_dir.mkdir(parents=True, exist_ok=True)

        executions = execute_active_agents(
            population_ids=fixture.population_ids,
            active_agent_ids=(forced_user_id,),
            top_user_ids=top_user_ids,
            graph=built_graph.graph,
            news_items=news_items,
            working_user_db=working_db,
            working_forum_db=working_forum,
            df_stock=df_stock,
            df_strategy=df_strategy,
            belief_args=belief_args,
            current_date=args.current_date,
            log_dir=reasoning_log_dir,
            config_path=config_path,
        )

        if len(executions) != 1:
            raise Phase07D2Error(f"expected one forced execution, got {len(executions)}")
        execution = executions[0]
        if not execution.completed_successfully:
            raise Phase07D2Error(
                "forced dynamic top-user reasoning did not complete successfully: "
                f"{execution.to_audit_dict(include_payloads=False)}"
            )
        if not execution.is_top_user:
            raise Phase07D2Error("forced Agent was not classified as dynamic top user")

        conversation_path = (
            reasoning_log_dir
            / "conversation_records"
            / args.current_date
            / f"{forced_user_id}.json"
        )
        if not conversation_path.is_file():
            raise Phase07D2Error(
                f"inherited process_user_input did not save conversation record: {conversation_path}"
            )
        conversation = json.loads(conversation_path.read_text(encoding="utf-8"))
        if not isinstance(conversation, list):
            raise Phase07D2Error("inherited conversation record is not a list")

        cleaned_news = _normalise_news_for_inherited_prompt(news_items)
        expected_prompt = TradingPrompt.get_news_analysis_prompt(cleaned_news)
        prompt_index, news_response = _find_news_prompt_exchange(
            conversation, expected_prompt=expected_prompt
        )

        (run_dir / "agent_execution.json").write_text(
            json.dumps(
                execution.to_audit_dict(include_payloads=True),
                ensure_ascii=False,
                indent=2,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )

    hashes_after = {name: sha256_file(path) for name, path in protected.items()}
    changed = sorted(name for name in protected if hashes_before[name] != hashes_after[name])
    if changed:
        raise Phase07D2Error(f"protected source input(s) changed: {changed}")

    finished = datetime.now(timezone.utc)
    summary = {
        "banner": BANNER,
        "phase": "7D-2",
        "gate_version": GATE_VERSION,
        "status": "PASS",
        "formal_experiment_evidence": False,
        "natural_phase4_activation_evidence": False,
        "forced_branch_coverage": True,
        "run_id": run_dir.name,
        "started_at_utc": started.isoformat(),
        "finished_at_utc": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "git": {"commit": commit, "clean_at_start": True},
        "population": {
            "n_population": len(fixture.population_ids),
            "manifest_status": fixture.manifest_status,
        },
        "day": {
            "current_date": args.current_date,
            "history_cutoff": args.history_cutoff,
            "day_1st": True,
            "market_advance_executed": False,
            "forum_actions_applied": False,
            "belief_propagation_enabled": False,
        },
        "graph": {
            "graph_sha256": built_graph.graph_sha256,
            "n_nodes": built_graph.n_nodes,
            "n_edges": built_graph.n_edges,
            "top_fraction": args.top_fraction,
            "top_user_ids": list(top_user_ids),
            "forced_user_id": forced_user_id,
            "forced_user_selection": "first deterministic Phase 6 dynamic-prominence top_user_id",
        },
        "routing": {
            "forced_agent_count": 1,
            "forced_user_id": forced_user_id,
            "forced_user_is_dynamic_top_user": forced_user_id in set(top_user_ids),
            "complete_daily_news_items_supplied": len(news_items),
            "inherited_process_user_input_completed": execution.completed_successfully,
            "inherited_news_prompt_found_in_saved_conversation": True,
            "inherited_news_prompt_index": prompt_index,
            "inherited_news_prompt_sha256": _sha256_text(expected_prompt),
            "inherited_news_response_present": True,
            "inherited_news_response_sha256": _sha256_text(news_response),
            "top_user_direct_news_branch_exercised": True,
        },
        "delegation": {
            "reasoning_entry_point": "simulation.process_user_input",
            "news_branch_owner": "trader.trading_agent.PersonalizedStockTrader._read_news",
            "marketlens_news_reimplementation_used": False,
            "twinmarket_core_modified": False,
            "participant_data_used": False,
            "reset": reset_result.to_dict(),
        },
        "protected_inputs": {
            name: {
                "path": str(protected[name]),
                "sha256_before": hashes_before[name],
                "sha256_after": hashes_after[name],
                "unchanged": hashes_before[name] == hashes_after[name],
            }
            for name in protected
        },
        "scope": {
            "verified_here": [
                "dynamic top-user identity is derived from the Phase 6 graph",
                "exactly one dynamic top user is forced active for branch coverage",
                "all 19 TwinMarket daily-news items are supplied to inherited reasoning",
                "inherited simulation.process_user_input completes for that top user",
                "the exact inherited news-analysis prompt appears in the saved conversation",
                "a non-empty inherited news-analysis assistant response follows the prompt",
                "protected source runtime/manifest/belief/news/calendar inputs remain unchanged",
                "participant state is excluded",
            ],
            "not_verified_here": [
                "natural Phase 4 activation of a top user",
                "market matching or Agent-world market mutation",
                "multi-day forum propagation",
                "multi-day belief propagation",
                "formal experiment evidence",
            ],
        },
    }

    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"Artifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
