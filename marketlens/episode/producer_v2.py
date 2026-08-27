"""MarketLens v2 formal canonical-episode producer orchestration.

The producer owns *orchestration only*. It does not reimplement TwinMarket Agent
reasoning, matching, price formation, portfolio mutation, forum or belief logic.
Default mode is zero-LLM dry-run. A formal execution is limited to one explicit
predeclared episode slot and can never overwrite a technically valid frozen slot.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from marketlens.episode.contract_v2 import (
    EPISODE_IDS,
    EPISODE_POOL_ID,
    EXPECTED_AGENT_PIPELINE_EXECUTIONS,
    EXPECTED_EXECUTION_PLAN_SHA256,
    EXPECTED_WORLD_TICKS,
    POPULATION_SEED,
    SELECTED_AGENT_IDS_SHA256,
    execution_plan_sha256,
    file_sha256,
    formal_episode_paths,
    load_execution_plan,
    validate_formal_episode_manifest,
    validate_formal_episode_pool_manifest,
)
from marketlens.stimulus.manifest import sha256_json


class CanonicalEpisodeProducerError(RuntimeError):
    """Raised when a formal episode producer safety/technical gate fails."""


PRODUCER_CONTRACT_SHA256 = "2ed65346f28e0b065e819c2d2457eb1bf5bfd666e5a69b93d8280f8b88fe2f6d"
PRODUCER_CONTRACT_STATUS = "formal_v2_producer_contract_frozen"
PRODUCER_CONTRACT_VERSION = "2.0"
FORMAL_EXECUTION_BANNER = (
    "FORMAL / MARKETLENS V2 CANONICAL EPISODE SLOT EXECUTION / "
    "PAID REAL BACKEND / PREDECLARED TECHNICAL GATES"
)
DRY_RUN_BANNER = (
    "NON-FORMAL / MARKETLENS V2 CANONICAL EPISODE PRODUCER DRY RUN / "
    "ZERO-LLM / NOT FORMAL EXPERIMENT EVIDENCE"
)
POOL_FINALIZE_BANNER = (
    "FORMAL ASSET FREEZE / MARKETLENS V2 CANONICAL EPISODE POOL FINALIZATION / ZERO-LLM"
)


def default_producer_contract_path() -> Path:
    return Path(__file__).with_name("producer_contract_v2.json")


def _canonical_json_sha256(value: Mapping[str, Any]) -> str:
    return sha256_json(dict(value))


def load_producer_contract(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path is not None else default_producer_contract_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalEpisodeProducerError(f"cannot load MarketLens v2 producer contract: {source}") from exc
    if not isinstance(payload, dict):
        raise CanonicalEpisodeProducerError("MarketLens v2 producer contract root must be an object")
    validate_producer_contract(payload)
    return payload


def validate_producer_contract(contract: Mapping[str, Any]) -> None:
    if _canonical_json_sha256(contract) != PRODUCER_CONTRACT_SHA256:
        raise CanonicalEpisodeProducerError("MarketLens v2 producer-contract SHA-256 drifted")
    if contract.get("contract_schema_version") != "marketlens-canonical-episode-producer-contract/2.0":
        raise CanonicalEpisodeProducerError("MarketLens v2 producer schema drifted")
    if contract.get("contract_version") != PRODUCER_CONTRACT_VERSION:
        raise CanonicalEpisodeProducerError("MarketLens v2 producer version drifted")
    if contract.get("status") != PRODUCER_CONTRACT_STATUS:
        raise CanonicalEpisodeProducerError("MarketLens v2 producer status drifted")
    if contract.get("base_v1_execution_plan_sha256") != "a907079281f7deca590bd7ec741b56fab614f05b0cdd869c5f2c345fb048a8bc":
        raise CanonicalEpisodeProducerError("MarketLens v2 no longer binds the frozen v1 plan identity")
    if contract.get("execution_plan_v2_sha256") != EXPECTED_EXECUTION_PLAN_SHA256:
        raise CanonicalEpisodeProducerError("MarketLens v2 no longer binds the exact v2 execution plan")
    if contract.get("episode_pool_id") != EPISODE_POOL_ID:
        raise CanonicalEpisodeProducerError("MarketLens v2 episode-pool identity drifted")
    if tuple(contract.get("episode_ids", ())) != EPISODE_IDS:
        raise CanonicalEpisodeProducerError("MarketLens v2 episode slot list drifted")

    controls = contract.get("execution_controls", {})
    expected_controls = {
        "default_mode": "dry_run_zero_llm",
        "full_pool_execute_command_allowed": False,
        "one_explicit_episode_slot_per_execute_command": True,
        "formal_execute_requires_clean_git": True,
        "formal_execute_requires_explicit_acknowledgement": True,
        "overwrite_formal_slot_allowed": False,
        "partial_resume_allowed": False,
        "seed_substitution_allowed": False,
        "outcome_based_rerun_allowed": False,
        "episode_similarity_based_rerun_allowed": False,
        "failed_attempt_evidence_retained": True,
        "technically_valid_completed_slot_immutable": True,
        "pool_finalization_is_zero_llm": True,
        "pool_finalization_requires_all_three_valid_slots": True,
    }
    if controls != expected_controls:
        raise CanonicalEpisodeProducerError("MarketLens v2 execution-control policy drifted")

    backend = contract.get("backend_identity", {})
    if backend.get("model_name") != "gpt-5.4-mini":
        raise CanonicalEpisodeProducerError("formal backend model identity drifted")
    if backend.get("base_url") != "https://zhi-api.com/v1":
        raise CanonicalEpisodeProducerError("formal backend base URL drifted")
    if backend.get("api_key_recorded_in_manifest") is not False:
        raise CanonicalEpisodeProducerError("API key must never enter formal evidence")

    plan_output = load_execution_plan().get("v2_forum_output", {})
    if contract.get("forum_output_contract") != plan_output:
        raise CanonicalEpisodeProducerError("MarketLens v2 forum-output contract drifted")

    acceptance = contract.get("technical_acceptance", {})
    if acceptance.get("formal_world_ticks") != EXPECTED_WORLD_TICKS:
        raise CanonicalEpisodeProducerError("formal producer tick count drifted")
    if acceptance.get("active_agent_pipeline_executions") != EXPECTED_AGENT_PIPELINE_EXECUTIONS:
        raise CanonicalEpisodeProducerError("formal producer Agent-pipeline count drifted")
    if acceptance.get("forum_post_language_complete") is not True:
        raise CanonicalEpisodeProducerError("formal v2 English-forum technical gate drifted")
    for key in (
        "minimum_post_count",
        "minimum_trade_count",
        "price_direction",
        "sentiment",
        "misinformation_effect",
        "cross_episode_divergence",
    ):
        if acceptance.get(key) is not None:
            raise CanonicalEpisodeProducerError(f"outcome-conditioned producer gate present: {key}")


def _git(repo_root: Path, *args: str) -> str:
    import subprocess

    result = subprocess.run(
        ["git", *args], cwd=repo_root, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def git_state(repo_root: str | Path) -> dict[str, str]:
    root = Path(repo_root).resolve()
    return {
        "commit": _git(root, "rev-parse", "HEAD"),
        "branch": _git(root, "branch", "--show-current"),
        "status_porcelain": _git(root, "status", "--porcelain"),
    }


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _public_api_config(path: Path) -> dict[str, Any]:
    import yaml

    if not path.is_file():
        raise CanonicalEpisodeProducerError(f"API config not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise CanonicalEpisodeProducerError("API config must be a mapping")
    return {
        "model_name": payload.get("model_name"),
        "base_url": payload.get("base_url"),
        "api_key_configured": bool(payload.get("api_key")),
    }


def validate_runtime_dependencies(
    *,
    repo_root: str | Path,
    config_path: str | Path = "config/api.yaml",
    require_api_key: bool = False,
) -> dict[str, Any]:
    """Validate immutable formal-run dependencies against predeclared identities."""
    root = Path(repo_root).resolve()
    contract = load_producer_contract()
    plan = load_execution_plan()
    if execution_plan_sha256(plan) != contract["execution_plan_v2_sha256"]:
        raise CanonicalEpisodeProducerError("active frozen v2 plan does not match MarketLens v2 producer contract")

    observed_hashes: dict[str, str] = {}
    for relative, expected in contract["protected_inputs"].items():
        path = root / relative
        if not path.is_file():
            raise CanonicalEpisodeProducerError(f"protected formal input missing: {relative}")
        actual = file_sha256(path)
        observed_hashes[relative] = actual
        if actual != expected:
            raise CanonicalEpisodeProducerError(
                f"protected formal input drifted: {relative}; expected {expected}, got {actual}"
            )

    api = _public_api_config(_resolve(root, config_path))
    expected_backend = contract["backend_identity"]
    if api["model_name"] != expected_backend["model_name"]:
        raise CanonicalEpisodeProducerError(
            f"formal model mismatch: expected {expected_backend['model_name']!r}, got {api['model_name']!r}"
        )
    if api["base_url"] != expected_backend["base_url"]:
        raise CanonicalEpisodeProducerError(
            f"formal backend URL mismatch: expected {expected_backend['base_url']!r}, got {api['base_url']!r}"
        )
    if require_api_key and not api["api_key_configured"]:
        raise CanonicalEpisodeProducerError("formal episode execution requires configured API key")

    return {
        "execution_plan_sha256": execution_plan_sha256(plan),
        "producer_contract_sha256": PRODUCER_CONTRACT_SHA256,
        "protected_input_sha256": observed_hashes,
        "backend": api,
    }


def verify_candidate_fixture(
    *,
    repo_root: str | Path,
    runtime_db: str | Path | None = None,
    population_manifest: str | Path | None = None,
) -> dict[str, Any]:
    """Reuse Phase 10's already-audited N30 fixture verifier."""
    from marketlens.market.phase10_n30_real_validation import _verify_candidate_fixture

    root = Path(repo_root).resolve()
    contract = load_producer_contract()
    fixture = contract["candidate_fixture"]
    runtime = _resolve(root, runtime_db or fixture["runtime_db"])
    manifest = _resolve(root, population_manifest or fixture["population_manifest"])
    runtime_sha, manifest_sha, ids = _verify_candidate_fixture(
        runtime_db=runtime, population_manifest=manifest
    )
    if len(ids) != fixture["population_size"]:
        raise CanonicalEpisodeProducerError("formal candidate fixture is not N30")
    if fixture["selection_seed"] != POPULATION_SEED:
        raise CanonicalEpisodeProducerError("formal candidate fixture seed contract drifted")
    if fixture["selected_agent_ids_sha256"] != SELECTED_AGENT_IDS_SHA256:
        raise CanonicalEpisodeProducerError("formal candidate fixture membership contract drifted")
    return {
        "runtime_db": str(runtime),
        "population_manifest": str(manifest),
        "runtime_sha256": runtime_sha,
        "population_manifest_sha256": manifest_sha,
        "population_ids": list(ids),
    }


def dry_run_summary(
    *,
    repo_root: str | Path,
    config_path: str | Path = "config/api.yaml",
    runtime_db: str | Path | None = None,
    population_manifest: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    contract = load_producer_contract()
    plan = load_execution_plan()
    deps = validate_runtime_dependencies(
        repo_root=root, config_path=config_path, require_api_key=False
    )
    fixture = verify_candidate_fixture(
        repo_root=root,
        runtime_db=runtime_db,
        population_manifest=population_manifest,
    )
    slot_state: dict[str, Any] = {}
    for episode_id in EPISODE_IDS:
        paths = formal_episode_paths(episode_id)
        slot_state[episode_id] = {
            "formal_root": paths["root"],
            "formal_root_exists": (root / paths["root"]).exists(),
            "raw_evidence_root": paths["raw_execution_evidence_root"],
        }
    return {
        "status": "READY / ZERO-LLM / NO FORMAL EPISODE MUTATION",
        "banner": DRY_RUN_BANNER,
        "llm_api_calls": 0,
        "formal_execution_performed": False,
        "episode_pool_id": EPISODE_POOL_ID,
        "episode_ids": list(EPISODE_IDS),
        "one_slot_per_execute_command": True,
        "full_pool_execute_command_allowed": False,
        "execution_plan_v2_sha256": deps["execution_plan_sha256"],
        "producer_contract_sha256": deps["producer_contract_sha256"],
        "world_ticks_per_episode": len(plan["days"]),
        "agent_pipeline_executions_per_episode": sum(row["n_active"] for row in plan["days"]),
        "expected_pool_agent_pipeline_executions": sum(row["n_active"] for row in plan["days"]) * len(EPISODE_IDS),
        "backend": {
            "model_name": deps["backend"]["model_name"],
            "base_url": deps["backend"]["base_url"],
            "api_key_configured": deps["backend"]["api_key_configured"],
            "api_key_recorded": False,
            "exact_backend_call_count_claimed": False,
        },
        "protected_input_sha256": deps["protected_input_sha256"],
        "candidate_fixture": {
            "runtime_db": fixture["runtime_db"],
            "population_manifest": fixture["population_manifest"],
            "population_size": len(fixture["population_ids"]),
            "selected_agent_ids_sha256": SELECTED_AGENT_IDS_SHA256,
        },
        "slot_state": slot_state,
        "participant_data_used": False,
        "controlled_stimulus_injected_into_agent_world": False,
        "forum_output_contract": contract["forum_output_contract"],
        "formal_assets_written": False,
    }


def _next_attempt_dir(raw_root: Path) -> tuple[int, Path]:
    raw_root.mkdir(parents=True, exist_ok=True)
    used: list[int] = []
    for item in raw_root.iterdir():
        if item.is_dir() and item.name.startswith("attempt_"):
            try:
                used.append(int(item.name.split("_", 1)[1]))
            except (IndexError, ValueError):
                continue
    number = max(used, default=0) + 1
    return number, raw_root / f"attempt_{number:03d}"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def _readonly(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _participant_decision_dates(repo_root: Path) -> tuple[str, ...]:
    from marketlens.experiment.protocol import load_protocol

    protocol = load_protocol(repo_root / "marketlens/experiment/protocol_v1.json")
    dates = tuple(
        str(row["agent_world_date"])
        for row in protocol["timeline"]
        if bool(row.get("shadow_trade_enabled"))
    )
    if len(dates) != 15:
        raise CanonicalEpisodeProducerError(
            f"formal participant decision-date count drifted: expected 15, got {len(dates)}"
        )
    return dates


def validate_participant_price_coverage(
    *, repo_root: str | Path, agent_world_db: str | Path
) -> dict[str, Any]:
    """Require exact canonical DB close prices for every investable asset/decision date."""
    from marketlens.market.asset_catalog import AssetCatalog

    root = Path(repo_root).resolve()
    db = Path(agent_world_db).resolve()
    stock_ids = AssetCatalog(root / "data/stock_profile.csv").ids()
    dates = _participant_decision_dates(root)
    missing: list[str] = []
    invalid: list[str] = []
    with sqlite3.connect(str(db)) as conn:
        for current_date in dates:
            for stock_id in stock_ids:
                rows = conn.execute(
                    "SELECT close_price FROM StockData WHERE stock_id = ? AND DATE(date) = ?",
                    (stock_id, current_date),
                ).fetchall()
                key = f"{stock_id}@{current_date}"
                if len(rows) != 1:
                    missing.append(key)
                    continue
                try:
                    price = float(rows[0][0])
                except (TypeError, ValueError):
                    invalid.append(key)
                    continue
                if price <= 0:
                    invalid.append(key)
    return {
        "complete": not missing and not invalid,
        "asset_count": len(stock_ids),
        "decision_date_count": len(dates),
        "expected_exact_price_cells": len(stock_ids) * len(dates),
        "missing": missing,
        "invalid": invalid,
    }


def validate_forum_profile_source_cue_join(
    *, agent_world_db: str | Path, forum_db: str | Path
) -> dict[str, Any]:
    """Prove every participant-visible natural post has a same-day Profiles snapshot."""
    world = Path(agent_world_db).resolve()
    forum = Path(forum_db).resolve()
    missing: list[dict[str, str]] = []
    checked = 0
    with sqlite3.connect(str(forum)) as forum_conn, sqlite3.connect(str(world)) as world_conn:
        posts = forum_conn.execute(
            "SELECT id, user_id, created_at FROM posts WHERE COALESCE(type, '') != 'repost' ORDER BY id"
        ).fetchall()
        for post_id, user_id, created_at in posts:
            post_date = str(created_at)[:10]
            checked += 1
            row = world_conn.execute(
                "SELECT user_type FROM Profiles WHERE CAST(user_id AS TEXT) = ? AND DATE(created_at) = ? LIMIT 1",
                (str(user_id), post_date),
            ).fetchone()
            if row is None or row[0] is None or not str(row[0]).strip():
                missing.append(
                    {"post_id": str(post_id), "user_id": str(user_id), "post_date": post_date}
                )
    return {
        "complete": not missing,
        "participant_visible_nonrepost_posts_checked": checked,
        "missing_same_day_profile_snapshots": missing,
    }


def _formal_slot_already_exists(root: Path, episode_id: str) -> bool:
    paths = formal_episode_paths(episode_id)
    return any((root / paths[key]).exists() for key in ("root", "agent_world_db", "forum_db", "episode_manifest"))


def _planned_calendar(repo_root: Path, frozen_days: Sequence[Mapping[str, Any]]) -> tuple[Any, ...]:
    from marketlens.experiment.protocol import load_protocol
    from marketlens.market.multiday import build_calendar_day_plan
    from marketlens.market.runtime.news import load_trading_day_set

    protocol = load_protocol(repo_root / "marketlens/experiment/protocol_v1.json")
    calendar = build_calendar_day_plan(
        start_date=protocol["world"]["initialization_date"],
        end_date=protocol["world"]["end_date"],
        trading_days=load_trading_day_set(repo_root / "data/trading_days.csv"),
    )
    if len(calendar) != len(frozen_days):
        raise CanonicalEpisodeProducerError("runtime calendar length drifted from frozen frozen v2 plan")
    for live, frozen in zip(calendar, frozen_days, strict=True):
        if (
            live.step != frozen["step"]
            or live.current_date != frozen["agent_world_date"]
            or bool(live.market_open) != bool(frozen["market_open"])
            or live.expected_market_action != frozen["expected_market_action"]
        ):
            raise CanonicalEpisodeProducerError(
                f"runtime calendar drift on frozen step {frozen['step']}"
            )
    return tuple(calendar)


def execute_formal_episode_slot(
    *,
    repo_root: str | Path,
    episode_id: str,
    acknowledge_formal_execution: bool,
    runtime_db: str | Path | None = None,
    population_manifest: str | Path | None = None,
    config_path: str | Path = "config/api.yaml",
) -> dict[str, Any]:
    """Execute exactly one predeclared formal slot. This can invoke paid LLM calls."""
    root = Path(repo_root).resolve()
    if episode_id not in EPISODE_IDS:
        raise CanonicalEpisodeProducerError(f"unknown formal episode slot: {episode_id}")
    if not acknowledge_formal_execution:
        raise CanonicalEpisodeProducerError(
            "formal slot execution requires explicit acknowledgement"
        )
    git = git_state(root)
    if git["status_porcelain"]:
        raise CanonicalEpisodeProducerError("formal slot execution requires a clean Git working tree")
    if _formal_slot_already_exists(root, episode_id):
        raise CanonicalEpisodeProducerError(
            f"formal slot {episode_id} already has output; overwrite/replacement is forbidden"
        )
    if (root / "data/marketlens/canonical_episode/v2/pool_manifest.json").exists():
        raise CanonicalEpisodeProducerError("formal pool is already frozen; further slot execution is forbidden")

    contract = load_producer_contract()
    plan = load_execution_plan()
    deps_before = validate_runtime_dependencies(
        repo_root=root, config_path=config_path, require_api_key=True
    )
    fixture = verify_candidate_fixture(
        repo_root=root, runtime_db=runtime_db, population_manifest=population_manifest
    )
    candidate_runtime = Path(fixture["runtime_db"])
    candidate_manifest = Path(fixture["population_manifest"])
    population_ids = tuple(map(str, fixture["population_ids"]))
    calendar = _planned_calendar(root, plan["days"])

    paths = formal_episode_paths(episode_id)
    raw_root = root / paths["raw_execution_evidence_root"]
    attempt_number, attempt_dir = _next_attempt_dir(raw_root)
    attempt_dir.mkdir(parents=False, exist_ok=False)
    workspace = attempt_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=False)
    working_db = workspace / "agent_world.db"
    forum_db = workspace / "forum.db"
    shutil.copy2(candidate_runtime, working_db)

    from marketlens.agents.runtime.preflight import create_empty_forum_db, load_initial_beliefs
    from marketlens.agents.social.graph import build_bounded_social_graph
    from marketlens.agents.social.prominence import make_prominence_snapshot
    from marketlens.market.phase10_n30_real_validation import extract_phase6_top_user_ids
    from marketlens.market.multiday_real import (
        GRAPH_START_DATE,
        SIMILARITY_THRESHOLD,
        TIME_DECAY_FACTOR,
        TOP_FRACTION,
        _apply_forum_actions,
        _create_posts,
        _execute_active_agents,
        _load_runtime_frames,
        _serialize_result,
        _validate_runtime_day,
        build_forum_belief_args,
        capture_forum_metrics,
        capture_runtime_metrics,
        write_daily_records,
    )
    from marketlens.market.runtime.inherited_market import (
        advance_non_trading_day,
        advance_trading_day,
        reset_agent_world,
    )
    from marketlens.market.runtime.news import load_daily_news
    import simulation
    from marketlens.episode.language import (
        validate_english_forum_post,
        validate_forum_db_english_posts,
    )
    from trader.prompts import forum_post_language
    from util.ForumDB import (
        create_post_db,
        execute_forum_actions,
        get_all_users_posts_db,
        update_posts_score_by_date_range,
    )

    create_empty_forum_db(forum_db)
    protected_paths = tuple(root / rel for rel in contract["protected_inputs"])
    started = time.perf_counter()
    daily_state_chain: list[dict[str, Any]] = []
    day_evidence: list[dict[str, Any]] = []
    pipeline_completed = 0
    technical_failures: list[str] = []
    sealed_success = False
    final_root_for_recovery: Path | None = None
    attempt_manifest_path = attempt_dir / "attempt_manifest.json"
    attempt_base: dict[str, Any] = {
        "manifest_schema_version": "marketlens-canonical-episode-attempt/2.0",
        "episode_pool_id": EPISODE_POOL_ID,
        "episode_id": episode_id,
        "attempt_number": attempt_number,
        "git": git,
        "execution_plan_v2_sha256": execution_plan_sha256(plan),
        "producer_v2_contract_sha256": PRODUCER_CONTRACT_SHA256,
        "backend": {
            "model_name": deps_before["backend"]["model_name"],
            "base_url": deps_before["backend"]["base_url"],
            "api_key_configured": True,
            "api_key_recorded": False,
        },
        "candidate_fixture": {
            "runtime_sha256_before": fixture["runtime_sha256"],
            "population_manifest_sha256_before": fixture["population_manifest_sha256"],
            "selected_agent_ids_sha256": SELECTED_AGENT_IDS_SHA256,
        },
        "protected_input_sha256_before": deps_before["protected_input_sha256"],
        "partial_resume_used": False,
        "seed_substitution_used": False,
        "outcome_review_used_for_acceptance": False,
        "episode_similarity_review_used_for_acceptance": False,
    }
    _write_json(attempt_manifest_path, {**attempt_base, "status": "running"})

    try:
        reset_result = reset_agent_world(
            current_date=plan["world"]["initialization_date"],
            runtime_db=working_db,
            forum_db=forum_db,
            protected_paths=protected_paths,
        )
        initial_beliefs = load_initial_beliefs(
            root / "util/belief/belief_1000_0129.csv", population_ids
        )
        previous_world_sha = file_sha256(working_db)
        previous_forum_sha = file_sha256(forum_db)

        for live_day, frozen_day in zip(calendar, plan["days"], strict=True):
            date_str = frozen_day["agent_world_date"]
            current_ts = pd.Timestamp(date_str)
            active_ids = tuple(map(str, frozen_day["active_agent_ids"]))
            if len(active_ids) != int(frozen_day["n_active"]):
                raise CanonicalEpisodeProducerError(f"frozen n_active mismatch on {date_str}")
            if not set(active_ids).issubset(set(population_ids)):
                raise CanonicalEpisodeProducerError(f"frozen active Agent outside N30 on {date_str}")

            graph_built = build_bounded_social_graph(
                runtime_db=working_db,
                history_cutoff=live_day.history_cutoff,
                graph_start_date=GRAPH_START_DATE,
                similarity_threshold=SIMILARITY_THRESHOLD,
                time_decay_factor=TIME_DECAY_FACTOR,
            )
            if graph_built.n_nodes != 30:
                raise CanonicalEpisodeProducerError(
                    f"formal graph escaped bounded N30 on {date_str}: {graph_built.n_nodes}"
                )
            prominence = make_prominence_snapshot(graph_built, top_fraction=TOP_FRACTION)
            top_ids = extract_phase6_top_user_ids(
                prominence, expected_top_n=int(30 * TOP_FRACTION)
            )
            news_items = load_daily_news(
                root / "data/sorted_impact_news.pkl", current_date=date_str
            )
            df_stock, df_strategy = _load_runtime_frames(
                working_db, market_open=bool(frozen_day["market_open"])
            )
            if live_day.day_1st:
                belief_args: Any = initial_beliefs
                belief_source = "initial_belief_csv"
            else:
                belief_args, stats = build_forum_belief_args(
                    forum_db=forum_db,
                    current_date=current_ts,
                    initial_beliefs=initial_beliefs,
                    population_ids=population_ids,
                    forum_reader=get_all_users_posts_db,
                )
                belief_source = {"source": "forum_with_initial_fallback", **stats}

            with forum_post_language("en"):
                agent_results = _execute_active_agents(
                    process_user_input_fn=simulation.process_user_input,
                    population_ids=population_ids,
                    active_ids=active_ids,
                    runtime_db=working_db,
                    forum_db=forum_db,
                    current_date=current_ts,
                    day_1st=live_day.day_1st,
                    graph=graph_built.graph,
                    news_items=news_items,
                    df_stock=df_stock,
                    df_strategy=df_strategy,
                    top_user_ids=top_ids,
                    belief_args=belief_args,
                    log_dir=attempt_dir,
                    config_path=_resolve(root, config_path),
                    market_open=bool(frozen_day["market_open"]),
                )
            pipeline_completed += len(agent_results)
            day_language_invalid: list[dict[str, Any]] = []
            for item in agent_results:
                post_args = item.get("post_response_args")
                if not isinstance(post_args, Mapping) or post_args.get("post") is None:
                    continue
                check = validate_english_forum_post(str(post_args["post"]))
                if not check["complete"]:
                    day_language_invalid.append(
                        {
                            "user_id": str(item["user_id"]),
                            "violations": check["violations"],
                        }
                    )
            if day_language_invalid:
                raise CanonicalEpisodeProducerError(
                    f"v2 English forum-post gate failed on {date_str}: {day_language_invalid}"
                )
            records = write_daily_records(
                log_dir=attempt_dir, current_date=date_str, agent_results=agent_results
            )
            post_stats = _create_posts(
                agent_results=agent_results,
                current_date=current_ts,
                forum_db=forum_db,
                create_post_fn=create_post_db,
            )

            if frozen_day["market_open"]:
                market_result = advance_trading_day(
                    current_date=date_str,
                    runtime_db=working_db,
                    decision_json=records["trading_records"],
                    log_dir=attempt_dir,
                    protected_paths=protected_paths,
                )
                market_action = "advance_trading_day"
            else:
                market_result = advance_non_trading_day(
                    current_date=date_str,
                    runtime_db=working_db,
                    protected_paths=protected_paths,
                )
                market_action = "advance_non_trading_day"
            if market_action != frozen_day["expected_market_action"]:
                raise CanonicalEpisodeProducerError(
                    f"market action drift on {date_str}: {market_action}"
                )

            if live_day.day_1st:
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

            runtime_metrics = capture_runtime_metrics(working_db, date_str)
            forum_metrics = capture_forum_metrics(forum_db)
            failures = _validate_runtime_day(
                metrics=runtime_metrics,
                market_open=bool(frozen_day["market_open"]),
                population_size=30,
            )
            if failures:
                raise CanonicalEpisodeProducerError(
                    f"post-day technical validation failed on {date_str}: {failures}"
                )

            world_sha = file_sha256(working_db)
            forum_sha = file_sha256(forum_db)
            daily_state_chain.append(
                {
                    "step": frozen_day["step"],
                    "agent_world_date": date_str,
                    "agent_world_db_sha256_before": previous_world_sha,
                    "forum_db_sha256_before": previous_forum_sha,
                    "agent_world_db_sha256": world_sha,
                    "forum_db_sha256": forum_sha,
                }
            )
            previous_world_sha = world_sha
            previous_forum_sha = forum_sha
            day_evidence.append(
                {
                    "step": frozen_day["step"],
                    "agent_world_date": date_str,
                    "market_open": bool(frozen_day["market_open"]),
                    "expected_market_action": frozen_day["expected_market_action"],
                    "active_agent_ids": list(active_ids),
                    "n_active": len(active_ids),
                    "belief": belief_source,
                    "graph": {
                        "n_nodes": graph_built.n_nodes,
                        "n_edges": graph_built.n_edges,
                        "graph_sha256": graph_built.graph_sha256,
                        "top_user_ids": list(top_ids),
                    },
                    "posts": post_stats,
                    "forum_post_language": {
                        "complete": True,
                        "invalid_post_count": 0,
                        "validation_mode": "deterministic_zero_llm_no_translation",
                    },
                    "forum_actions": forum_action_stats,
                    "market": {
                        "action": market_action,
                        "delegation_result": _serialize_result(market_result),
                    },
                    "runtime_metrics": runtime_metrics,
                    "forum_metrics": forum_metrics,
                }
            )
            _write_json(attempt_manifest_path, {
                **attempt_base,
                "status": "running",
                "days_completed": len(day_evidence),
                "active_agent_pipeline_executions_completed": pipeline_completed,
                "latest_agent_world_db_sha256": world_sha,
                "latest_forum_db_sha256": forum_sha,
            })

        price_coverage = validate_participant_price_coverage(
            repo_root=root, agent_world_db=working_db
        )
        source_join = validate_forum_profile_source_cue_join(
            agent_world_db=working_db, forum_db=forum_db
        )
        forum_language = validate_forum_db_english_posts(forum_db)
        if not price_coverage["complete"]:
            technical_failures.append("participant exact-price coverage incomplete")
        if not source_join["complete"]:
            technical_failures.append("forum/profile source-cue join incomplete")
        if not forum_language["complete"]:
            technical_failures.append("v2 forum post language validation incomplete")
        if len(day_evidence) != EXPECTED_WORLD_TICKS:
            technical_failures.append("not all 27 calendar ticks completed")
        if pipeline_completed != EXPECTED_AGENT_PIPELINE_EXECUTIONS:
            technical_failures.append(
                f"Agent pipeline total {pipeline_completed} != {EXPECTED_AGENT_PIPELINE_EXECUTIONS}"
            )

        deps_after = validate_runtime_dependencies(
            repo_root=root, config_path=config_path, require_api_key=True
        )
        fixture_after = verify_candidate_fixture(
            repo_root=root, runtime_db=runtime_db, population_manifest=population_manifest
        )
        if deps_after["protected_input_sha256"] != deps_before["protected_input_sha256"]:
            technical_failures.append("protected formal inputs changed during execution")
        if fixture_after["runtime_sha256"] != fixture["runtime_sha256"]:
            technical_failures.append("candidate N30 runtime fixture changed during execution")
        if fixture_after["population_manifest_sha256"] != fixture["population_manifest_sha256"]:
            technical_failures.append("candidate N30 population manifest changed during execution")
        if technical_failures:
            raise CanonicalEpisodeProducerError("; ".join(technical_failures))

        formal_root = root / paths["root"]
        if formal_root.exists():
            raise CanonicalEpisodeProducerError(f"formal slot root unexpectedly exists: {formal_root}")
        staging_root = attempt_dir / "seal_staging"
        staging_root.mkdir(parents=True, exist_ok=False)
        staging_world = staging_root / "agent_world.db"
        staging_forum = staging_root / "forum.db"
        shutil.move(str(working_db), str(staging_world))
        shutil.move(str(forum_db), str(staging_forum))
        final_world_sha = file_sha256(staging_world)
        final_forum_sha = file_sha256(staging_forum)

        episode_manifest = {
            "manifest_schema_version": "marketlens-canonical-episode-manifest/2.0",
            "status": "formal_frozen",
            "episode_pool_id": EPISODE_POOL_ID,
            "episode_id": episode_id,
            "episode_slot": EPISODE_IDS.index(episode_id) + 1,
            "protocol_version": plan["protocol_version"],
            "execution_plan_sha256": execution_plan_sha256(plan),
            "producer_contract_sha256": PRODUCER_CONTRACT_SHA256,
            "git": git,
            "backend": {
                "model_name": deps_before["backend"]["model_name"],
                "base_url": deps_before["backend"]["base_url"],
                "api_key_recorded": False,
                "exact_backend_call_count_claimed": False,
            },
            "population": {
                "size": 30,
                "selection_seed": POPULATION_SEED,
                "selected_agent_ids_sha256": SELECTED_AGENT_IDS_SHA256,
            },
            "activation": {
                "seed": plan["activation"]["seed"],
                "same_frozen_plan_as_other_episode_slots": True,
            },
            "world": {
                "initialization_date": plan["world"]["initialization_date"],
                "end_date": plan["world"]["end_date"],
                "formal_world_ticks": len(day_evidence),
            },
            "attempt": {
                "attempt_number": attempt_number,
                "attempt_evidence_root": str(attempt_dir.relative_to(root)),
                "seed_substitution_used": False,
                "partial_resume_used": False,
                "outcome_review_used_for_acceptance": False,
                "episode_similarity_review_used_for_acceptance": False,
            },
            "forum_output": contract["forum_output_contract"],
            "execution": {
                "active_agent_pipeline_executions_expected": EXPECTED_AGENT_PIPELINE_EXECUTIONS,
                "active_agent_pipeline_executions_completed": pipeline_completed,
                "failed_agent_pipeline_count": 0,
                "participant_data_used": False,
                "controlled_stimulus_injected_into_agent_world": False,
                "custom_matching_price_forum_belief_logic_used": False,
                "inherited_entrypoints": contract["inherited_execution_boundary"],
            },
            "validation": {
                "all_days_complete": len(day_evidence) == EXPECTED_WORLD_TICKS,
                "activation_plan_exact": True,
                "calendar_actions_exact": True,
                "state_chain_complete": len(daily_state_chain) == EXPECTED_WORLD_TICKS,
                "protected_sources_unchanged": deps_after["protected_input_sha256"] == deps_before["protected_input_sha256"],
                "participant_price_coverage_complete": price_coverage["complete"],
                "forum_profile_source_cue_join_complete": source_join["complete"],
                "forum_post_language_complete": forum_language["complete"],
                "price_coverage_evidence": price_coverage,
                "forum_profile_join_evidence": source_join,
                "forum_post_language_evidence": forum_language,
            },
            "daily_state_chain": daily_state_chain,
            "outputs": {
                "agent_world_db": {
                    "path": paths["agent_world_db"],
                    "sha256": final_world_sha,
                },
                "forum_db": {
                    "path": paths["forum_db"],
                    "sha256": final_forum_sha,
                },
            },
            "protected_input_sha256": deps_after["protected_input_sha256"],
        }
        # Validate manifest semantics before publishing any formal asset.
        validate_formal_episode_manifest(episode_manifest, repo_root=root, verify_files=False)
        staging_manifest = staging_root / "episode_manifest.json"
        _write_json(staging_manifest, episode_manifest)

        formal_root.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging_root, formal_root)
        final_root_for_recovery = formal_root
        final_world = root / paths["agent_world_db"]
        final_forum = root / paths["forum_db"]
        manifest_path = root / paths["episode_manifest"]
        validate_formal_episode_manifest(episode_manifest, repo_root=root, verify_files=True)
        sealed_success = True

        _readonly(final_world)
        _readonly(final_forum)
        _readonly(manifest_path)
        finished = round(time.perf_counter() - started, 3)
        attempt_final = {
            **attempt_base,
            "status": "FORMAL_FROZEN",
            "days_completed": len(day_evidence),
            "active_agent_pipeline_executions_completed": pipeline_completed,
            "reset": _serialize_result(reset_result),
            "formal_outputs": episode_manifest["outputs"],
            "episode_manifest_path": paths["episode_manifest"],
            "duration_seconds": finished,
        }
        _write_json(attempt_manifest_path, attempt_final)
        return {
            "status": "FORMAL_FROZEN",
            "banner": FORMAL_EXECUTION_BANNER,
            "episode_id": episode_id,
            "attempt_number": attempt_number,
            "episode_manifest": paths["episode_manifest"],
            "agent_world_db_sha256": final_world_sha,
            "forum_db_sha256": final_forum_sha,
            "days_completed": len(day_evidence),
            "active_agent_pipeline_executions_completed": pipeline_completed,
            "duration_seconds": finished,
        }
    except Exception as exc:
        # A failed attempt must never leave a path that looks formally frozen.
        if not sealed_success and final_root_for_recovery is not None and final_root_for_recovery.exists():
            recovery = attempt_dir / "failed_seal_staging"
            try:
                os.replace(final_root_for_recovery, recovery)
            except OSError:
                pass
        try:
            deps_now = validate_runtime_dependencies(
                repo_root=root, config_path=config_path, require_api_key=False
            )
            protected_unchanged = deps_now["protected_input_sha256"] == deps_before["protected_input_sha256"]
        except Exception:
            protected_unchanged = False
        failure = {
            **attempt_base,
            "status": "TECHNICAL_INVALID",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "days_completed": len(day_evidence),
            "active_agent_pipeline_executions_completed": pipeline_completed,
            "protected_sources_unchanged_at_failure_capture": protected_unchanged,
            "workspace_preserved": True,
            "partial_resume_allowed": False,
            "restart_policy": "new attempt from frozen initial N30 state only",
            "duration_seconds": round(time.perf_counter() - started, 3),
        }
        if working_db.exists():
            failure["latest_agent_world_db_sha256"] = file_sha256(working_db)
        if forum_db.exists():
            failure["latest_forum_db_sha256"] = file_sha256(forum_db)
        _write_json(attempt_manifest_path, failure)
        raise


def finalize_formal_episode_pool(*, repo_root: str | Path) -> dict[str, Any]:
    """Freeze pool_manifest.json only after all three formal slots validate. Zero LLM."""
    root = Path(repo_root).resolve()
    contract = load_producer_contract()
    plan = load_execution_plan()
    pool_path = root / "data/marketlens/canonical_episode/v2/pool_manifest.json"
    if pool_path.exists():
        raise CanonicalEpisodeProducerError("formal pool manifest already exists; overwrite is forbidden")

    episode_rows: list[dict[str, str]] = []
    for episode_id in EPISODE_IDS:
        path = root / formal_episode_paths(episode_id)["episode_manifest"]
        if not path.is_file():
            raise CanonicalEpisodeProducerError(
                f"cannot finalize pool before formal slot exists: {episode_id}"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_formal_episode_manifest(payload, repo_root=root, verify_files=True)
        episode_rows.append(
            {
                "episode_id": episode_id,
                "episode_manifest_path": formal_episode_paths(episode_id)["episode_manifest"],
            }
        )

    manifest = {
        "manifest_schema_version": "marketlens-canonical-episode-pool-manifest/2.0",
        "status": "formal_frozen",
        "episode_pool_id": EPISODE_POOL_ID,
        "execution_plan_sha256": execution_plan_sha256(plan),
        "producer_contract_sha256": PRODUCER_CONTRACT_SHA256,
        "forum_output": contract["forum_output_contract"],
        "episode_count": len(EPISODE_IDS),
        "episode_ids": list(EPISODE_IDS),
        "participant_assignment": {
            "mode": "balanced_random_across_episode_pool",
            "episode_id_recorded_for_analysis": True,
            "assignment_uses_episode_outcomes": False,
        },
        "episodes": episode_rows,
        "finalization": {
            "llm_api_calls": 0,
            "outcome_review_used": False,
            "episode_similarity_review_used": False,
        },
    }
    validate_formal_episode_pool_manifest(manifest, repo_root=root, verify_files=True)
    _write_json(pool_path, manifest)
    _readonly(pool_path)
    return {
        "status": "FORMAL_POOL_FROZEN",
        "banner": POOL_FINALIZE_BANNER,
        "llm_api_calls": 0,
        "episode_pool_id": EPISODE_POOL_ID,
        "episode_ids": list(EPISODE_IDS),
        "pool_manifest": str(pool_path.relative_to(root)),
    }
