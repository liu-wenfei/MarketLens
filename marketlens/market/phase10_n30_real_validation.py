"""Phase 10 N30 three-calendar-day real-backend feasibility validation.

This module is a thin validation runner built on already-frozen MarketLens
boundaries. It reuses a separately prepared deterministic N30 candidate fixture and the
same Phase 9B activation reference seed. The runner never regenerates a
population, searches for a more convenient seed, or executes the 27-tick
formal horizon.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from marketlens.market.multiday_real import (
    GRAPH_START_DATE,
    PROB_OF_TECHNICAL,
    SIMILARITY_THRESHOLD,
    TIME_DECAY_FACTOR,
    TOP_FRACTION,
    _apply_forum_actions,
    _create_posts,
    _ensure_real_run_clean,
    _execute_active_agents,
    _load_config_public,
    _load_runtime_frames,
    _protected_hashes,
    _serialize_result,
    _validate_runtime_day,
    activation_state_digest,
    build_forum_belief_args,
    capture_forum_metrics,
    capture_runtime_metrics,
    git_state,
    sha256_file,
    write_daily_records,
)

PHASE10_N30_VERSION = "marketlens_phase10_n30_real_backend_validation/1.0"
BANNER = (
    "NON-FORMAL / PHASE 10 N30 THREE-DAY REAL-BACKEND FEASIBILITY VALIDATION / "
    "NOT FORMAL EXPERIMENT EVIDENCE"
)
DRY_BANNER = (
    "NON-FORMAL / PHASE 10 N30 THREE-DAY DRY RUN / 0 LLM / "
    "NOT FORMAL EXPERIMENT EVIDENCE"
)

class Phase10N30Error(RuntimeError):
    """Raised when the bounded Phase 10 N30 validation contract is unsafe."""


POPULATION_SIZE = 30
POPULATION_SEED = "marketlens-dev-population-01"
ACTIVATION_SEED = "marketlens-phase09b-activation-01"
START_DATE = "2023-06-15"
END_DATE = "2023-06-17"
EXPECTED_DATES = ("2023-06-15", "2023-06-16", "2023-06-17")
EXPECTED_MARKET_OPEN = (True, True, False)

DEFAULT_RUNTIME_DB = (
    "artifacts/preflight/phase10/n30_candidate_fixture/population_runtime.db"
)
DEFAULT_POPULATION_MANIFEST = (
    "artifacts/preflight/phase10/n30_candidate_fixture/population_manifest.json"
)

# Frozen from the outcome-blind Phase 9E same-seed N30 population family.
EXPECTED_SELECTED_IDS_SHA256 = (
    "60d846b21c15e2213f6f897a17a7ea98039fbf461abe54ee89e1b6779d24b2d4"
)
EXPECTED_ROW_COUNTS = {
    "Profiles": 30,
    "Strategy": 30,
    "TradingDetails": 1304,
    "StockProfile": 10,
    "StockData": 1080,
}
EXPECTED_TABLE_DIGESTS_SHA256 = {
    "Profiles": "a9c59d685756ef8370d9bf7a9460bdbd593c4ffd96ac3061c59e83cb5385ff27",
    "Strategy": "387ee4de16e9535160da835bb505947860e2589d7c551c31d3ae2173d467ed8c",
    "TradingDetails": "35bd353c9de6e5c9aa7603e3c3608f7aed0e634eeecccff03d1139c588169ba5",
    "StockProfile": "3991b7e2ce084c5a5df5a402f2eefe6e33cf58825e5674becbf210e8514683ac",
    "StockData": "80d31d17c0e8fade532194e6e9afb465615b885495f31b398a69b8b9649bb542",
}

# Same activation reference seed already used for the Phase 9B/9C N20 path.
# These N30 IDs are a drift guard computed before any paid N30 validation.
EXPECTED_ACTIVE_IDS = (
    (
        "19674822257",
        "25823641850",
        "35530389569",
        "42710178889",
        "46549065517",
        "70690674622",
        "75680675866",
        "88166001054",
        "88792353988",
        "94588474629",
    ),
    (
        "15476317174",
        "24570243197",
        "25823641850",
        "72429318063",
        "75680675866",
        "92879748105",
        "93531157884",
    ),
    (
        "34238881864",
        "48968490169",
        "96496600304",
    ),
)


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _verify_candidate_fixture(
    *, runtime_db: Path, population_manifest: Path
) -> tuple[str, str, tuple[str, ...]]:
    if not runtime_db.is_file():
        raise Phase10N30Error(
            f"prepared N30 runtime fixture not found: {runtime_db}; "
            "run prepare_phase10_n30_candidate_fixture.py first"
        )
    if not population_manifest.is_file():
        raise Phase10N30Error(
            f"prepared N30 population manifest not found: {population_manifest}; "
            "run prepare_phase10_n30_candidate_fixture.py first"
        )

    runtime_sha = sha256_file(runtime_db)
    manifest_sha = sha256_file(population_manifest)

    manifest = json.loads(population_manifest.read_text(encoding="utf-8"))
    selection = manifest.get("selection", {})
    fixture = manifest.get("runtime_fixture", {})
    ids = tuple(map(str, selection.get("selected_agent_ids", ())))
    if selection.get("seed") != POPULATION_SEED:
        raise Phase10N30Error("N30 population selection seed drifted")
    if selection.get("population_size") != POPULATION_SIZE:
        raise Phase10N30Error("N30 population manifest size drifted")
    if selection.get("selected_agent_ids_sha256") != EXPECTED_SELECTED_IDS_SHA256:
        raise Phase10N30Error("N30 selected membership drifted from Phase 9E")
    if fixture.get("fixture_sha256") != runtime_sha:
        raise Phase10N30Error("N30 runtime hash does not match its manifest")
    if dict(fixture.get("row_counts", {})) != EXPECTED_ROW_COUNTS:
        raise Phase10N30Error("N30 runtime row counts drifted from the frozen semantic reference")
    if dict(fixture.get("table_digests_sha256", {})) != EXPECTED_TABLE_DIGESTS_SHA256:
        raise Phase10N30Error("N30 runtime table digests drifted from the frozen semantic reference")
    if len(ids) != POPULATION_SIZE or len(set(ids)) != POPULATION_SIZE:
        raise Phase10N30Error("N30 manifest membership is incomplete or duplicated")

    return runtime_sha, manifest_sha, ids


def _build_plan(*, trading_days: frozenset[str]) -> tuple[Any, ...]:
    from marketlens.market.multiday import build_calendar_day_plan

    plan = build_calendar_day_plan(
        start_date=START_DATE,
        end_date=END_DATE,
        trading_days=trading_days,
    )
    if tuple(day.current_date for day in plan) != EXPECTED_DATES:
        raise Phase10N30Error("N30 validation calendar horizon drifted")
    if tuple(day.market_open for day in plan) != EXPECTED_MARKET_OPEN:
        raise Phase10N30Error(
            "authoritative calendar no longer resolves to OPEN, OPEN, CLOSED"
        )
    return plan


def _activation_sequence(
    *, runtime_db: Path, plan: Sequence[Any]
) -> tuple[tuple[Any, ...], tuple[dict[str, Any], ...]]:
    from marketlens.agents.activation.policy import ActivationPolicy
    from marketlens.agents.activation.profiles import load_activation_profiles
    from marketlens.market.multiday import sample_activation_sequence

    profiles = load_activation_profiles(runtime_db)
    if len(profiles) != POPULATION_SIZE:
        raise Phase10N30Error(
            f"prepared N30 candidate fixture produced {len(profiles)} activation profiles"
        )

    sequence = sample_activation_sequence(
        profiles,
        plan=plan,
        seed=ACTIVATION_SEED,
        policy=ActivationPolicy(),
    )

    evidence: list[dict[str, Any]] = []
    previous_output_digest: str | None = None
    for index, item in enumerate(sequence):
        actual_ids = tuple(map(str, item.batch.active_agent_ids))
        expected_ids = EXPECTED_ACTIVE_IDS[index]
        if actual_ids != expected_ids:
            raise Phase10N30Error(
                "Phase 9B deterministic N30 activation reference drifted on "
                f"{item.day.current_date}: expected {expected_ids}, got {actual_ids}"
            )
        output_digest = activation_state_digest(item.batch.next_state)
        if output_digest is None:
            raise Phase10N30Error("unexpected null activation-state digest")
        evidence.append(
            {
                "step": item.day.step,
                "agent_world_date": item.day.current_date,
                "active_agent_ids": list(actual_ids),
                "n_active": len(actual_ids),
                "input_state_digest": previous_output_digest,
                "output_state_digest": output_digest,
                "policy_version": item.batch.policy_version,
                "matches_phase9b_reference": True,
            }
        )
        previous_output_digest = output_digest

    return tuple(item.batch for item in sequence), tuple(evidence)


def extract_phase6_top_user_ids(
    prominence_snapshot: Mapping[str, Any],
    *,
    expected_top_n: int,
) -> tuple[str, ...]:
    """Read top-user IDs from the frozen Phase 6 nested snapshot shape."""
    prominence = prominence_snapshot.get("prominence")
    if not isinstance(prominence, Mapping):
        raise Phase10N30Error(
            "Phase 6 prominence snapshot is missing its nested 'prominence' record"
        )

    reported_top_n = prominence.get("top_n")
    if reported_top_n != expected_top_n:
        raise Phase10N30Error(
            "Phase 6 prominence snapshot reported top_n="
            f"{reported_top_n!r}; expected {expected_top_n}"
        )

    top_user_ids = tuple(map(str, prominence.get("top_user_ids", ())))
    if len(top_user_ids) != expected_top_n:
        raise Phase10N30Error(
            f"dynamic prominence returned {len(top_user_ids)} top users; "
            f"expected {expected_top_n}"
        )
    return top_user_ids


def validate_n30_real_summary(
    summary: Mapping[str, Any],
) -> tuple[str, list[str]]:
    failures: list[str] = []
    inconclusive: list[str] = []

    if summary.get("population", {}).get("size") != POPULATION_SIZE:
        failures.append("population size is not fixed N30")
    if tuple(summary.get("horizon", {}).get("dates", ())) != EXPECTED_DATES:
        failures.append("calendar horizon drifted")
    if tuple(summary.get("horizon", {}).get("market_open", ())) != EXPECTED_MARKET_OPEN:
        failures.append("authoritative OPEN/OPEN/CLOSED pattern failed")

    integrity = summary.get("integrity", {})
    if not integrity.get("protected_sources_unchanged"):
        failures.append("protected source hash changed")
    if not integrity.get("candidate_n30_fixture_unchanged"):
        failures.append("prepared N30 candidate fixture changed")
    if integrity.get("participant_data_used") is not False:
        failures.append("participant data entered the Agent world")
    if integrity.get("custom_market_logic_used") is not False:
        failures.append("custom market logic was used")
    if integrity.get("custom_forum_logic_used") is not False:
        failures.append("custom forum logic was used")
    if integrity.get("custom_belief_logic_used") is not False:
        failures.append("custom belief logic was used")

    continuity = summary.get("continuity", {})
    if not continuity.get("activation_state_chain_valid"):
        failures.append("Phase 4 activation state chain is broken")
    if not continuity.get("all_graphs_bounded_n30"):
        failures.append("one or more daily graphs were not bounded N30")
    if not continuity.get("same_working_runtime_across_all_days"):
        failures.append("working runtime was not continuous across all days")
    if not continuity.get("same_working_forum_across_all_days"):
        failures.append("working forum DB was not continuous across all days")

    days = summary.get("days", [])
    for day in days:
        failures.extend(day.get("post_day_validation_failures", []))
        if day.get("reasoning", {}).get("failed_agents", 0) != 0:
            failures.append(
                f"Agent reasoning failure on {day.get('agent_world_date')}"
            )

    if days:
        if days[0].get("reasoning", {}).get("active_agents", 0) <= 0:
            inconclusive.append("Day 1 had no active Agent")
        closed_days = [day for day in days if not day.get("market_open")]
        if not closed_days or closed_days[0].get("reasoning", {}).get(
            "active_agents", 0
        ) <= 0:
            inconclusive.append("closed day had no active Agent")

    natural = summary.get("natural_multiday_coverage", {})
    if natural.get("posts_created_total", 0) <= 0:
        inconclusive.append("no natural Agent post was created")
    if natural.get("forum_belief_agents_observed", 0) <= 0:
        inconclusive.append(
            "no later-day Agent belief was naturally sourced from ForumDB"
        )
    if natural.get("later_day_forum_action_calls", 0) <= 0:
        inconclusive.append("no later-day inherited forum-action call occurred")

    if failures:
        return "FAIL", failures + inconclusive
    if inconclusive:
        return "INCONCLUSIVE_NATURAL_MULTIDAY_COVERAGE", inconclusive
    return "PASS", []


def run_phase10_n30(
    *,
    repo_root: str | Path,
    runtime_db: str | Path = DEFAULT_RUNTIME_DB,
    population_manifest: str | Path = DEFAULT_POPULATION_MANIFEST,
    source_db: str | Path = "data/sys_1000.db",
    belief_csv: str | Path = "util/belief/belief_1000_0129.csv",
    config_path: str | Path = "config/api.yaml",
    news_pickle: str | Path = "data/sorted_impact_news.pkl",
    trading_calendar: str | Path = "data/trading_days.csv",
    artifact_root: str | Path = "artifacts/preflight/phase10",
    execute_real_backend: bool = False,
    acknowledge_non_formal: bool = False,
    preserve_workspace: bool = False,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    runtime_db_p = _resolve(root, runtime_db)
    manifest_p = _resolve(root, population_manifest)
    source_db_p = _resolve(root, source_db)
    belief_csv_p = _resolve(root, belief_csv)
    config_path_p = _resolve(root, config_path)
    news_pickle_p = _resolve(root, news_pickle)
    trading_calendar_p = _resolve(root, trading_calendar)
    artifact_root_p = _resolve(root, artifact_root)

    if execute_real_backend and not acknowledge_non_formal:
        raise Phase10N30Error(
            "--execute-real-backend requires --acknowledge-non-formal"
        )

    started = time.perf_counter()
    git = _ensure_real_run_clean(root) if execute_real_backend else git_state(root)
    mode = "real" if execute_real_backend else "dry"
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + f"_{git['commit'][:8]}_phase10_n30_{mode}"
    )
    run_dir = artifact_root_p / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    fixture_runtime_sha, fixture_manifest_sha, manifest_population_ids = _verify_candidate_fixture(
        runtime_db=runtime_db_p,
        population_manifest=manifest_p,
    )

    from marketlens.agents.runtime.preflight import (
        create_empty_forum_db,
        load_initial_beliefs,
        verify_population_fixture,
    )
    from marketlens.market.runtime.news import (
        load_daily_news,
        load_trading_day_set,
    )

    verified = verify_population_fixture(runtime_db_p, manifest_p)
    population_ids = tuple(map(str, verified.population_ids))
    if population_ids != manifest_population_ids:
        raise Phase10N30Error("verified N30 runtime membership differs from manifest order")
    if len(population_ids) != POPULATION_SIZE:
        raise Phase10N30Error(
            f"prepared fixture has {len(population_ids)} Agents, expected N30"
        )

    trading_days = load_trading_day_set(trading_calendar_p)
    plan = _build_plan(trading_days=trading_days)
    batches, activation_plan = _activation_sequence(
        runtime_db=runtime_db_p,
        plan=plan,
    )

    planned_days = [
        {
            "step": day.step,
            "agent_world_date": day.current_date,
            "history_cutoff": day.history_cutoff,
            "day_1st": day.day_1st,
            "market_open": day.market_open,
            "participant_trading_enabled": day.participant_trading_enabled,
            "belief_source": day.belief_source,
            "forum_actions_enabled": day.forum_actions_enabled,
            "expected_market_action": day.expected_market_action,
            "background_news_items": len(
                load_daily_news(news_pickle_p, current_date=day.current_date)
            ),
        }
        for day in plan
    ]

    public_config = _load_config_public(config_path_p)
    protected_paths = {
        "source_population_db": source_db_p,
        "candidate_n30_runtime_db": runtime_db_p,
        "candidate_n30_population_manifest": manifest_p,
        "trading_calendar": trading_calendar_p,
        "background_news": news_pickle_p,
        "initial_beliefs": belief_csv_p,
    }
    protected_before = _protected_hashes(protected_paths)

    summary: dict[str, Any] = {
        "banner": BANNER if execute_real_backend else DRY_BANNER,
        "phase": "10-N30",
        "gate_version": PHASE10_N30_VERSION,
        "formal_experiment_evidence": False,
        "mode": mode,
        "git": git,
        "population": {
            "size": POPULATION_SIZE,
            "status": "CANDIDATE N30 / REAL-BACKEND FEASIBILITY / NOT YET FORMAL POPULATION FREEZE",
            "fixture_origin": (
                "deterministically prepared N30 candidate using frozen Phase 3 selector; "
                "membership/runtime guards frozen from Phase 9E"
            ),
            "runtime_db": str(runtime_db_p),
            "population_manifest": str(manifest_p),
            "runtime_sha256": fixture_runtime_sha,
            "manifest_sha256": fixture_manifest_sha,
            "population_ids": list(population_ids),
            "prepared_by_separate_zero_llm_step": True,
            "regenerated_inside_real_runner": False,
            "selection_seed": POPULATION_SEED,
            "selected_agent_ids_sha256": EXPECTED_SELECTED_IDS_SHA256,
        },
        "activation": {
            "seed": ACTIVATION_SEED,
            "policy": "frozen Phase 4",
            "reference_origin": (
                "same pre-existing Phase 9B reference seed; N30 sequence frozen "
                "before paid N30 validation"
            ),
            "days": list(activation_plan),
            "expected_agent_pipeline_executions": sum(
                row["n_active"] for row in activation_plan
            ),
            "exact_backend_call_count": None,
            "exact_backend_call_count_note": (
                "one inherited Agent pipeline may make multiple backend calls; "
                "inference is not monkeypatched for counting"
            ),
        },
        "horizon": {
            "dates": list(EXPECTED_DATES),
            "market_open": list(EXPECTED_MARKET_OPEN),
            "fixed_three_calendar_days": True,
            "purpose": "bounded N30 backend feasibility only; not the 27-tick formal horizon",
            "authoritative_calendar": str(trading_calendar_p),
        },
        "planned_days": planned_days,
        "api_config": public_config,
        "integrity": {
            "participant_data_used": False,
            "custom_market_logic_used": False,
            "custom_matching_used": False,
            "custom_price_formation_used": False,
            "custom_agent_portfolio_update_used": False,
            "custom_tradingdetails_writer_used": False,
            "custom_forum_logic_used": False,
            "custom_belief_logic_used": False,
            "structured_inference_instrumentation_used": False,
            "protected_sha256_before": protected_before,
        },
        "run_id": run_id,
    }

    if not execute_real_backend:
        protected_after = _protected_hashes(protected_paths)
        summary["integrity"].update(
            {
                "protected_sha256_after": protected_after,
                "protected_sources_unchanged": protected_before == protected_after,
                "candidate_n30_fixture_unchanged": (
                    sha256_file(runtime_db_p) == fixture_runtime_sha
                    and sha256_file(manifest_p) == fixture_manifest_sha
                ),
            }
        )
        summary["status"] = "READY / 0 LLM / NO MARKET OR FORUM MUTATION"
        summary["duration_seconds"] = round(time.perf_counter() - started, 3)
        summary_path = run_dir / "summary.json"
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        summary["artifact"] = str(summary_path)
        return summary

    if not public_config["api_key_configured"]:
        raise Phase10N30Error("real-backend run requires api_key in config/api.yaml")

    from marketlens.agents.social.graph import build_bounded_social_graph
    from marketlens.agents.social.prominence import make_prominence_snapshot
    from marketlens.market.runtime.inherited_market import (
        advance_non_trading_day,
        advance_trading_day,
        reset_agent_world,
    )
    import simulation
    from util.ForumDB import (
        create_post_db,
        execute_forum_actions,
        get_all_users_posts_db,
        update_posts_score_by_date_range,
    )

    workspace_ctx = tempfile.TemporaryDirectory(prefix="marketlens_phase10_n30_")
    workspace = Path(workspace_ctx.name)
    working_db = workspace / "runtime.db"
    forum_db = workspace / "forum.db"
    shutil.copy2(runtime_db_p, working_db)
    create_empty_forum_db(forum_db)

    reset_result = reset_agent_world(
        current_date=START_DATE,
        runtime_db=working_db,
        forum_db=forum_db,
        protected_paths=tuple(protected_paths.values()),
    )
    working_after_reset_sha = sha256_file(working_db)
    initial_beliefs = load_initial_beliefs(belief_csv_p, population_ids)

    real_days: list[dict[str, Any]] = []
    posts_created_total = 0
    forum_belief_agents_observed = 0
    later_day_forum_action_calls = 0
    activation_chain_valid = True
    all_graphs_bounded_n30 = True
    previous_output_digest: str | None = None

    try:
        for step, day in enumerate(plan):
            date_str = day.current_date
            current_ts = pd.Timestamp(date_str)
            market_open = day.market_open
            batch = batches[step]
            active_ids = tuple(map(str, batch.active_agent_ids))
            activation_row = activation_plan[step]

            if step > 0 and activation_row["input_state_digest"] != previous_output_digest:
                activation_chain_valid = False
            previous_output_digest = activation_row["output_state_digest"]

            graph_built = build_bounded_social_graph(
                runtime_db=working_db,
                history_cutoff=day.history_cutoff,
                graph_start_date=GRAPH_START_DATE,
                similarity_threshold=SIMILARITY_THRESHOLD,
                time_decay_factor=TIME_DECAY_FACTOR,
            )
            prominence_snapshot = make_prominence_snapshot(
                graph_built, top_fraction=TOP_FRACTION
            )
            if graph_built.n_nodes != POPULATION_SIZE:
                all_graphs_bounded_n30 = False
            expected_top_n = int(POPULATION_SIZE * TOP_FRACTION)
            top_user_ids = extract_phase6_top_user_ids(
                prominence_snapshot,
                expected_top_n=expected_top_n,
            )

            news_items = load_daily_news(news_pickle_p, current_date=date_str)
            df_stock, df_strategy = _load_runtime_frames(
                working_db, market_open=market_open
            )

            if step == 0:
                belief_args: Any = initial_beliefs
                belief_stats = {
                    "source": "initial_belief_csv",
                    "population": POPULATION_SIZE,
                    "forum_with_belief": 0,
                    "fallback_no_post": 0,
                    "fallback_missing_belief": 0,
                }
            else:
                belief_args, stats = build_forum_belief_args(
                    forum_db=forum_db,
                    current_date=current_ts,
                    initial_beliefs=initial_beliefs,
                    population_ids=population_ids,
                    forum_reader=get_all_users_posts_db,
                )
                forum_belief_agents_observed += stats["forum_with_belief"]
                belief_stats = {"source": "forum_with_initial_fallback", **stats}

            reasoning_started = time.perf_counter()
            agent_results = _execute_active_agents(
                process_user_input_fn=simulation.process_user_input,
                population_ids=population_ids,
                active_ids=active_ids,
                runtime_db=working_db,
                forum_db=forum_db,
                current_date=current_ts,
                day_1st=day.day_1st,
                graph=graph_built.graph,
                news_items=news_items,
                df_stock=df_stock,
                df_strategy=df_strategy,
                top_user_ids=top_user_ids,
                belief_args=belief_args,
                log_dir=run_dir,
                config_path=config_path_p,
                market_open=market_open,
            )
            reasoning_seconds = round(time.perf_counter() - reasoning_started, 3)

            records = write_daily_records(
                log_dir=run_dir,
                current_date=date_str,
                agent_results=agent_results,
            )
            post_stats = _create_posts(
                agent_results=agent_results,
                current_date=current_ts,
                forum_db=forum_db,
                create_post_fn=create_post_db,
            )
            posts_created_total += post_stats["created"]

            market_started = time.perf_counter()
            if market_open:
                market_result = advance_trading_day(
                    current_date=date_str,
                    runtime_db=working_db,
                    decision_json=records["trading_records"],
                    log_dir=run_dir,
                    protected_paths=tuple(protected_paths.values()),
                )
                market_action = "advance_trading_day"
            else:
                market_result = advance_non_trading_day(
                    current_date=date_str,
                    runtime_db=working_db,
                    protected_paths=tuple(protected_paths.values()),
                )
                market_action = "advance_non_trading_day"
            market_seconds = round(time.perf_counter() - market_started, 3)

            if day.day_1st:
                forum_action_stats = {
                    "attempted_user_calls": 0,
                    "successful_user_calls": 0,
                    "skipped_string_args": 0,
                    "score_update_invoked": False,
                }
            else:
                forum_action_stats = _apply_forum_actions(
                    agent_results=agent_results,
                    current_date=current_ts,
                    forum_db=forum_db,
                    execute_forum_actions_fn=execute_forum_actions,
                    update_scores_fn=update_posts_score_by_date_range,
                )
                later_day_forum_action_calls += forum_action_stats[
                    "successful_user_calls"
                ]

            runtime_metrics = capture_runtime_metrics(working_db, date_str)
            forum_metrics = capture_forum_metrics(forum_db)
            post_day_failures = _validate_runtime_day(
                metrics=runtime_metrics,
                market_open=market_open,
                population_size=POPULATION_SIZE,
            )
            conversation_dir = run_dir / "conversation_records" / date_str
            conversation_files = (
                len(list(conversation_dir.glob("*.json")))
                if conversation_dir.is_dir()
                else 0
            )

            real_days.append(
                {
                    "step": day.step,
                    "agent_world_date": date_str,
                    "history_cutoff": day.history_cutoff,
                    "day_1st": day.day_1st,
                    "market_open": market_open,
                    "participant_trading_enabled": day.participant_trading_enabled,
                    "belief_source_contract": day.belief_source,
                    "forum_actions_enabled": day.forum_actions_enabled,
                    "background_news_items": len(news_items),
                    "activation": activation_row,
                    "graph": {
                        "n_nodes": graph_built.n_nodes,
                        "n_edges": graph_built.n_edges,
                        "graph_sha256": graph_built.graph_sha256,
                        "history_cutoff": graph_built.history_cutoff,
                        "top_user_ids": list(top_user_ids),
                    },
                    "belief": belief_stats,
                    "reasoning": {
                        "active_agents": len(active_ids),
                        "attempted_agents": len(agent_results),
                        "failed_agents": 0,
                        "conversation_files": conversation_files,
                        "duration_seconds": reasoning_seconds,
                        "per_agent": [
                            {
                                "user_id": item["user_id"],
                                "duration_seconds": item["duration_seconds"],
                                "decision_result_present": item["decision_result"] is not None,
                                "post_response_present": item["post_response_args"] is not None,
                            }
                            for item in agent_results
                        ],
                    },
                    "records": records,
                    "posts": post_stats,
                    "market": {
                        "action": market_action,
                        "delegation_result": _serialize_result(market_result),
                        "duration_seconds": market_seconds,
                    },
                    "forum_actions": forum_action_stats,
                    "runtime_metrics": runtime_metrics,
                    "forum_metrics": forum_metrics,
                    "post_day_validation_failures": post_day_failures,
                }
            )

        protected_after = _protected_hashes(protected_paths)
        summary.update(
            {
                "days": real_days,
                "reset": {
                    "delegation_result": _serialize_result(reset_result),
                    "working_runtime_sha256_after_reset": working_after_reset_sha,
                },
                "continuity": {
                    "activation_state_chain_valid": activation_chain_valid,
                    "all_graphs_bounded_n30": all_graphs_bounded_n30,
                    "same_working_runtime_across_all_days": True,
                    "same_working_forum_across_all_days": True,
                    "daily_graph_recomputed_after_prior_day_state": True,
                    "day2plus_belief_source": (
                        "inherited ForumDB with inherited initial-belief fallback"
                    ),
                },
                "natural_multiday_coverage": {
                    "posts_created_total": posts_created_total,
                    "forum_belief_agents_observed": forum_belief_agents_observed,
                    "later_day_forum_action_calls": later_day_forum_action_calls,
                },
            }
        )
        summary["integrity"].update(
            {
                "protected_sha256_after": protected_after,
                "protected_sources_unchanged": protected_before == protected_after,
                "candidate_n30_fixture_unchanged": (
                    sha256_file(runtime_db_p) == fixture_runtime_sha
                    and sha256_file(manifest_p) == fixture_manifest_sha
                ),
                "isolated_working_runtime_was_mutated": (
                    working_after_reset_sha != sha256_file(working_db)
                ),
                "inherited_reasoning_entrypoint": "simulation.process_user_input",
                "inherited_trading_day_entrypoint": (
                    "marketlens.market.runtime.inherited_market.advance_trading_day"
                ),
                "inherited_non_trading_day_entrypoint": (
                    "marketlens.market.runtime.inherited_market.advance_non_trading_day"
                ),
                "inherited_forum_entrypoints": [
                    "util.ForumDB.get_all_users_posts_db",
                    "util.ForumDB.create_post_db",
                    "util.ForumDB.execute_forum_actions",
                    "util.ForumDB.update_posts_score_by_date_range",
                ],
            }
        )

        status, reasons = validate_n30_real_summary(summary)
        summary["status"] = status
        summary["status_reasons"] = reasons
        summary["duration_seconds"] = round(time.perf_counter() - started, 3)
        summary_path = run_dir / "summary.json"
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        summary["artifact"] = str(summary_path)

        if status != "PASS" and preserve_workspace:
            debug_dir = run_dir / "failed_workspace"
            debug_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(working_db, debug_dir / "runtime.db")
            shutil.copy2(forum_db, debug_dir / "forum.db")
            summary["failed_workspace"] = str(debug_dir)

        return summary
    finally:
        workspace_ctx.cleanup()
