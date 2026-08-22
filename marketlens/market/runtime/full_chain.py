"""Phase 7C one-day orchestration for the inherited TwinMarket Agent world.

This module wires already-validated MarketLens layers together without
reimplementing TwinMarket market mechanics:

Phase 3 bounded population
    -> Phase 6 inherited social graph / deterministic prominence
    -> Phase 4 sparse activation
    -> inherited ``simulation.process_user_input`` for active Agents only
       with the complete TwinMarket daily-news list and dynamic top-user IDs
    -> inherited ``trader.matching_engine.test_matching_system`` through the
       Phase 7B delegation wrapper.

The source bounded runtime database and source input files are read-only for
this preflight.  All TwinMarket mutation occurs on an isolated temporary copy.
Participant state is not an input to this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any, Callable, Mapping, Protocol

import pandas as pd

from marketlens.agents.runtime.preflight import (
    build_phase4_activation_batch,
    collect_git_state,
    create_empty_forum_db,
    load_day1_frames,
    load_initial_beliefs,
    sha256_file,
    verify_population_fixture,
)
from marketlens.agents.social.graph import build_bounded_social_graph
from marketlens.agents.social.prominence import make_prominence_snapshot
from marketlens.market.runtime.inherited_market import (
    advance_trading_day,
    reset_agent_world,
)
from marketlens.market.runtime.news import load_daily_news, load_trading_day_set


PHASE07C_VERSION = "marketlens_phase07c_full_chain_preflight/1.0"
BANNER = "NON-FORMAL / REAL-BACKEND FULL-CHAIN PREFLIGHT / NOT FORMAL EXPERIMENT EVIDENCE"
SUPPORTED_DATE = "2023-06-15"
SUPPORTED_HISTORY_CUTOFF = "2023-06-14"
DEFAULT_ACTIVATION_SEED = "marketlens-phase05b-activation-01"


class Phase07FullChainError(RuntimeError):
    """Raised when the one-day Phase 7 chain cannot proceed safely."""


class ProcessUserInput(Protocol):
    def __call__(self, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class Phase07AgentExecution:
    user_id: str
    is_top_user: bool
    completed_successfully: bool
    returned_tuple_shape_ok: bool
    returned_user_id: str | None
    inherited_error: str | None
    decision_result_present: bool
    forum_args: Any = None
    decision_result: Any = None
    post_response_args: Any = None
    exception_error: str | None = None

    def to_audit_dict(self, *, include_payloads: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "user_id": self.user_id,
            "is_top_user": self.is_top_user,
            "completed_successfully": self.completed_successfully,
            "returned_tuple_shape_ok": self.returned_tuple_shape_ok,
            "returned_user_id": self.returned_user_id,
            "inherited_error": self.inherited_error,
            "decision_result_present": self.decision_result_present,
            "post_response_args_present": self.post_response_args is not None,
            "exception_error": self.exception_error,
        }
        if include_payloads:
            payload.update(
                {
                    "forum_args": self.forum_args,
                    "decision_result": self.decision_result,
                    "post_response_args": self.post_response_args,
                }
            )
        return payload


@dataclass(frozen=True)
class Phase07FullChainOutcome:
    run_dir: Path
    summary: Mapping[str, Any]


def _json_dump(path: Path, payload: Any, *, default: Callable[[Any], Any] | None = str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "ensure_ascii": False,
        "indent": 2,
    }
    if default is not None:
        kwargs["default"] = default
    path.write_text(json.dumps(payload, **kwargs) + "\n", encoding="utf-8")


def _existing_file(value: str | Path, *, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise Phase07FullChainError(f"{label} not found: {path}")
    return path


def _normalise_strategy_frame(
    df_strategy: pd.DataFrame,
    population_ids: tuple[str, ...],
) -> pd.DataFrame:
    if "user_id" not in df_strategy.columns or "strategy" not in df_strategy.columns:
        raise Phase07FullChainError("Strategy must contain user_id and strategy")

    frame = df_strategy.copy()
    frame["user_id"] = frame["user_id"].astype(str)
    population = set(population_ids)
    rows = frame[frame["user_id"].isin(population)]
    counts = rows.groupby("user_id").size().to_dict()
    missing = sorted(population - set(counts))
    duplicates = sorted(uid for uid, count in counts.items() if int(count) != 1)
    if missing or duplicates:
        raise Phase07FullChainError(
            "Strategy coverage does not match the bounded population; "
            f"missing={missing}, duplicates={duplicates}"
        )
    return frame


def _activation_mapping(
    population_ids: tuple[str, ...],
    active_agent_ids: tuple[str, ...],
) -> dict[str, bool]:
    population = tuple(str(uid) for uid in population_ids)
    active = tuple(str(uid) for uid in active_agent_ids)
    if not population:
        raise Phase07FullChainError("bounded population is empty")
    if len(set(population)) != len(population):
        raise Phase07FullChainError("bounded population contains duplicate Agent IDs")
    if len(set(active)) != len(active):
        raise Phase07FullChainError("activation batch contains duplicate active Agent IDs")
    unknown = sorted(set(active) - set(population))
    if unknown:
        raise Phase07FullChainError(
            f"activation batch contains Agent(s) outside bounded population: {unknown}"
        )
    active_set = set(active)
    return {uid: uid in active_set for uid in population}


def _load_process_user_input() -> ProcessUserInput:
    try:
        simulation = importlib.import_module("simulation")
    except Exception as exc:  # pragma: no cover - inherited environment branch
        raise Phase07FullChainError(
            "could not import inherited TwinMarket simulation module"
        ) from exc
    process = getattr(simulation, "process_user_input", None)
    if not callable(process):
        raise Phase07FullChainError(
            "inherited simulation module has no callable process_user_input"
        )
    return process


def _parse_execution(
    *,
    expected_user_id: str,
    is_top_user: bool,
    returned: Any,
) -> Phase07AgentExecution:
    tuple_shape_ok = isinstance(returned, tuple) and len(returned) == 4
    returned_user_id = None
    forum_args = None
    decision_result = None
    post_response_args = None

    if tuple_shape_ok:
        returned_user_id, forum_args, decision_result, post_response_args = returned

    inherited_error = None
    if isinstance(forum_args, Mapping) and forum_args.get("error"):
        inherited_error = str(forum_args["error"])

    returned_uid = str(returned_user_id) if returned_user_id is not None else None
    completed = bool(
        tuple_shape_ok
        and returned_uid == expected_user_id
        and inherited_error is None
        and decision_result is not None
    )
    return Phase07AgentExecution(
        user_id=expected_user_id,
        is_top_user=is_top_user,
        completed_successfully=completed,
        returned_tuple_shape_ok=tuple_shape_ok,
        returned_user_id=returned_uid,
        inherited_error=inherited_error,
        decision_result_present=decision_result is not None,
        forum_args=forum_args,
        decision_result=decision_result,
        post_response_args=post_response_args,
    )


def execute_active_agents(
    *,
    population_ids: tuple[str, ...],
    active_agent_ids: tuple[str, ...],
    top_user_ids: tuple[str, ...] | list[str],
    graph: Any,
    news_items: list[Any],
    working_user_db: str | Path,
    working_forum_db: str | Path,
    df_stock: pd.DataFrame,
    df_strategy: pd.DataFrame,
    belief_args: pd.DataFrame,
    current_date: str,
    log_dir: str | Path,
    config_path: str | Path,
    process_user_input_fn: ProcessUserInput | None = None,
) -> tuple[Phase07AgentExecution, ...]:
    """Run only naturally activated Agents through inherited TwinMarket reasoning.

    MarketLens supplies the Phase 6 dynamic ``top_user`` IDs and the complete
    daily TwinMarket news list.  TwinMarket itself decides whether a particular
    Agent directly consumes that news (the inherited top-user-only branch).
    """

    population = tuple(sorted(str(uid) for uid in population_ids))
    active = tuple(sorted(str(uid) for uid in active_agent_ids))
    if not active:
        raise Phase07FullChainError(
            "Phase 4 produced zero active Agents; this preflight does not resample or seed-fish"
        )

    activate_mapping = _activation_mapping(population, active)
    strategy = _normalise_strategy_frame(df_strategy, population)

    top_users = tuple(str(uid) for uid in top_user_ids)
    unknown_top = sorted(set(top_users) - set(population))
    if unknown_top:
        raise Phase07FullChainError(
            f"dynamic top-user set contains Agent(s) outside bounded population: {unknown_top}"
        )
    top_set = set(top_users)

    config = _existing_file(config_path, label="backend config")
    user_config_mapping = {uid: str(config) for uid in population}
    process = process_user_input_fn or _load_process_user_input()
    supplied_news = list(news_items)

    executions: list[Phase07AgentExecution] = []
    for user_id in active:
        try:
            returned = process(
                user_id=user_id,
                user_db=str(Path(working_user_db).resolve()),
                forum_db=str(Path(working_forum_db).resolve()),
                df_stock=df_stock,
                current_date=pd.Timestamp(current_date),
                debug=False,
                day_1st=True,
                current_user_graph=graph,
                import_news=supplied_news,
                df_strategy=strategy,
                is_trading_day=True,
                top_user=list(top_users),
                log_dir=str(Path(log_dir).resolve()),
                prob_of_technical=0.0,
                user_config_mapping=user_config_mapping,
                activate_maapping=activate_mapping,
                belief_args=belief_args,
                config_path=str(config),
            )
        except Exception as exc:
            executions.append(
                Phase07AgentExecution(
                    user_id=user_id,
                    is_top_user=user_id in top_set,
                    completed_successfully=False,
                    returned_tuple_shape_ok=False,
                    returned_user_id=None,
                    inherited_error=None,
                    decision_result_present=False,
                    exception_error=f"{type(exc).__name__}: {exc}",
                )
            )
            # Fail closed and avoid paying for further Agent calls after a hard failure.
            break

        execution = _parse_execution(
            expected_user_id=user_id,
            is_top_user=user_id in top_set,
            returned=returned,
        )
        executions.append(execution)
        if not execution.completed_successfully:
            # Do not continue into a partial paid batch or partial market day.
            break

    return tuple(executions)


def write_inherited_decision_json(
    *,
    path: str | Path,
    active_agent_ids: tuple[str, ...],
    executions: tuple[Phase07AgentExecution, ...],
) -> Path:
    """Write the exact user->decision_result shape consumed by TwinMarket matching."""

    active = tuple(sorted(str(uid) for uid in active_agent_ids))
    execution_ids = tuple(item.user_id for item in executions)
    if execution_ids != active:
        raise Phase07FullChainError(
            "reasoning did not complete the full active batch; market advance is blocked"
        )
    failed = [item.user_id for item in executions if not item.completed_successfully]
    if failed:
        raise Phase07FullChainError(
            f"one or more active Agent reasoning calls failed; market advance blocked: {failed}"
        )

    payload = {item.user_id: item.decision_result for item in executions}
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Strict serialization here: matching input must not silently stringify
        # unsupported objects.
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except TypeError as exc:
        raise Phase07FullChainError(
            "inherited Agent decision_result is not JSON-serializable"
        ) from exc
    return output


def inspect_runtime_day_state(
    runtime_db: str | Path,
    *,
    current_date: str,
) -> dict[str, int]:
    """Read audit counts only; this function performs no market-state writes."""

    db = _existing_file(runtime_db, label="working runtime database")
    with sqlite3.connect(str(db)) as conn:
        expected_stocks = int(
            conn.execute("SELECT COUNT(DISTINCT stock_id) FROM StockProfile").fetchone()[0]
        )
        stock_rows = int(
            conn.execute(
                "SELECT COUNT(*) FROM StockData WHERE date(date) = ?",
                (current_date,),
            ).fetchone()[0]
        )
        stock_ids = int(
            conn.execute(
                "SELECT COUNT(DISTINCT stock_id) FROM StockData WHERE date(date) = ?",
                (current_date,),
            ).fetchone()[0]
        )
        profile_rows = int(
            conn.execute(
                "SELECT COUNT(*) FROM Profiles WHERE date(created_at) = ?",
                (current_date,),
            ).fetchone()[0]
        )
        profile_ids = int(
            conn.execute(
                "SELECT COUNT(DISTINCT CAST(user_id AS TEXT)) "
                "FROM Profiles WHERE date(created_at) = ?",
                (current_date,),
            ).fetchone()[0]
        )
        trading_rows = int(
            conn.execute(
                "SELECT COUNT(*) FROM TradingDetails WHERE date(date_time) = ?",
                (current_date,),
            ).fetchone()[0]
        )

    return {
        "expected_stock_count": expected_stocks,
        "stockdata_rows_on_date": stock_rows,
        "stockdata_distinct_stocks_on_date": stock_ids,
        "profiles_rows_on_date": profile_rows,
        "profiles_distinct_agents_on_date": profile_ids,
        "tradingdetails_rows_on_date": trading_rows,
    }


def validate_runtime_day_state(
    state: Mapping[str, int],
    *,
    population_size: int,
) -> None:
    expected_stocks = int(state["expected_stock_count"])
    if expected_stocks <= 0:
        raise Phase07FullChainError("working runtime has no StockProfile universe")
    if int(state["stockdata_rows_on_date"]) != expected_stocks:
        raise Phase07FullChainError(
            "inherited market did not create exactly one StockData row per bounded stock"
        )
    if int(state["stockdata_distinct_stocks_on_date"]) != expected_stocks:
        raise Phase07FullChainError(
            "inherited market StockData date has missing or duplicate stock coverage"
        )
    if int(state["profiles_rows_on_date"]) != int(population_size):
        raise Phase07FullChainError(
            "inherited market did not create exactly one Profiles row per bounded Agent"
        )
    if int(state["profiles_distinct_agents_on_date"]) != int(population_size):
        raise Phase07FullChainError(
            "inherited market Profiles date has missing or duplicate Agent coverage"
        )
    # TradingDetails may legitimately be zero when generated orders do not match.


def _input_hashes(paths: Mapping[str, Path]) -> dict[str, str]:
    return {name: sha256_file(path) for name, path in paths.items()}


def _run_id(commit: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short = commit[:8] if commit else "nogit"
    return f"{stamp}_{short}_phase07_full_chain"


def run_phase07_full_chain(
    *,
    repo_root: str | Path,
    runtime_db: str | Path,
    population_manifest: str | Path,
    belief_csv: str | Path,
    config_path: str | Path,
    news_pickle: str | Path,
    trading_calendar: str | Path,
    market_reference_csv: str | Path,
    artifact_root: str | Path,
    current_date: str = SUPPORTED_DATE,
    history_cutoff: str = SUPPORTED_HISTORY_CUTOFF,
    seed: str = DEFAULT_ACTIVATION_SEED,
    expected_news_count: int | None = 19,
    graph_start_date: str = "2023-01-01",
    similarity_threshold: float = 0.1,
    time_decay_factor: float = 0.05,
    top_fraction: float = 0.10,
    process_user_input_fn: ProcessUserInput | None = None,
) -> Phase07FullChainOutcome:
    """Execute one isolated real/synthetic-backend Phase 7 day.

    ``process_user_input_fn`` exists only for zero-API tests.  Production/preflight
    CLI execution leaves it as ``None`` and therefore resolves the inherited
    TwinMarket function lazily.
    """

    if current_date != SUPPORTED_DATE or history_cutoff != SUPPORTED_HISTORY_CUTOFF:
        raise Phase07FullChainError(
            "Phase 7C is intentionally hard-limited to 2023-06-15 with "
            "history cutoff 2023-06-14 until multi-day forum/belief/state propagation "
            "is separately validated"
        )
    if not str(seed):
        raise Phase07FullChainError("activation seed must be explicit and non-empty")

    repo = Path(repo_root).expanduser().resolve()
    if not repo.is_dir():
        raise Phase07FullChainError(f"repo root not found: {repo}")

    config = _existing_file(config_path, label="backend config")
    beliefs = _existing_file(belief_csv, label="initial belief CSV")
    news = _existing_file(news_pickle, label="TwinMarket news pickle")
    calendar = _existing_file(trading_calendar, label="TwinMarket trading calendar")
    market_reference = _existing_file(
        market_reference_csv,
        label="TwinMarket historical market reference CSV",
    )

    trading_days = load_trading_day_set(calendar)
    if current_date not in trading_days:
        raise Phase07FullChainError(
            f"{current_date} is not present in TwinMarket pretrade_date calendar"
        )
    news_items = load_daily_news(news, current_date=current_date)
    if expected_news_count is not None and len(news_items) != int(expected_news_count):
        raise Phase07FullChainError(
            f"daily news count drift: expected {expected_news_count}, found {len(news_items)}"
        )

    fixture = verify_population_fixture(runtime_db, population_manifest)
    batch = build_phase4_activation_batch(fixture.runtime_db, seed=str(seed), step=0)
    if not batch.active_agent_ids:
        raise Phase07FullChainError(
            "Phase 4 produced zero active Agents; no resampling or seed fishing is allowed"
        )

    git_state = collect_git_state(repo)
    commit = str(git_state.get("commit") or "")
    artifacts = Path(artifact_root).expanduser().resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    run_dir = artifacts / _run_id(commit)
    if run_dir.exists():
        raise Phase07FullChainError(f"refusing to overwrite Phase 7 run: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    protected_inputs = {
        "source_runtime_db": fixture.runtime_db,
        "population_manifest": fixture.manifest_path,
        "belief_csv": beliefs,
        "news_pickle": news,
        "trading_calendar": calendar,
        "market_reference_csv": market_reference,
    }
    hashes_before = _input_hashes(protected_inputs)
    started = datetime.now(timezone.utc)

    summary: dict[str, Any] = {
        "banner": BANNER,
        "phase": "7C",
        "preflight_version": PHASE07C_VERSION,
        "formal_experiment_evidence": False,
        "run_id": run_dir.name,
        "status": "RUNNING",
        "started_at_utc": started.isoformat(),
        "git": {
            "commit": commit,
            "clean_at_start": bool(git_state.get("clean")),
            "status_at_start": str(git_state.get("status") or ""),
        },
        "participant_state_read": False,
        "participant_database_used": False,
    }
    _json_dump(run_dir / "summary.json", summary)

    try:
        with tempfile.TemporaryDirectory(prefix="marketlens_phase07c_") as temp_name:
            workspace = Path(temp_name)
            working_db = workspace / "runtime.db"
            working_forum = workspace / "forum.db"
            shutil.copy2(fixture.runtime_db, working_db)
            create_empty_forum_db(working_forum)

            reset_result = reset_agent_world(
                current_date=current_date,
                runtime_db=working_db,
                forum_db=working_forum,
                protected_paths=(fixture.runtime_db,),
            )

            built_graph = build_bounded_social_graph(
                runtime_db=working_db,
                history_cutoff=history_cutoff,
                graph_start_date=graph_start_date,
                similarity_threshold=similarity_threshold,
                time_decay_factor=time_decay_factor,
            )
            prominence = make_prominence_snapshot(
                built_graph,
                top_fraction=top_fraction,
            )
            top_user_ids = tuple(
                str(uid) for uid in prominence["prominence"]["top_user_ids"]
            )
            active_ids = tuple(sorted(str(uid) for uid in batch.active_agent_ids))
            active_top_user_ids = tuple(uid for uid in active_ids if uid in set(top_user_ids))

            df_strategy, df_stock = load_day1_frames(working_db)
            belief_args = load_initial_beliefs(beliefs, active_ids)

            reasoning_log_dir = run_dir / "inherited_reasoning"
            reasoning_log_dir.mkdir(parents=True, exist_ok=True)
            executions = execute_active_agents(
                population_ids=fixture.population_ids,
                active_agent_ids=active_ids,
                top_user_ids=top_user_ids,
                graph=built_graph.graph,
                news_items=news_items,
                working_user_db=working_db,
                working_forum_db=working_forum,
                df_stock=df_stock,
                df_strategy=df_strategy,
                belief_args=belief_args,
                current_date=current_date,
                log_dir=reasoning_log_dir,
                config_path=config,
                process_user_input_fn=process_user_input_fn,
            )

            for execution in executions:
                _json_dump(
                    run_dir / "agents" / f"{execution.user_id}.json",
                    execution.to_audit_dict(include_payloads=True),
                )

            decision_json = write_inherited_decision_json(
                path=run_dir / "trading_records" / f"{current_date}.json",
                active_agent_ids=active_ids,
                executions=executions,
            )

            market_result = advance_trading_day(
                current_date=current_date,
                runtime_db=working_db,
                decision_json=decision_json,
                log_dir=run_dir / "inherited_market",
                protected_paths=(fixture.runtime_db,),
            )
            day_state = inspect_runtime_day_state(
                working_db,
                current_date=current_date,
            )
            validate_runtime_day_state(
                day_state,
                population_size=len(fixture.population_ids),
            )
            if not market_result.runtime_db_changed:
                raise Phase07FullChainError(
                    "inherited market returned without advancing the isolated runtime database"
                )

        hashes_after = _input_hashes(protected_inputs)
        changed_sources = sorted(
            name for name in hashes_before if hashes_before[name] != hashes_after[name]
        )
        if changed_sources:
            raise Phase07FullChainError(
                f"protected source input(s) changed during Phase 7C: {changed_sources}"
            )

        finished = datetime.now(timezone.utc)
        execution_passed = sum(item.completed_successfully for item in executions)
        summary.update(
            {
                "status": "PASS",
                "finished_at_utc": finished.isoformat(),
                "duration_seconds": round((finished - started).total_seconds(), 3),
                "population": {
                    "n_population": len(fixture.population_ids),
                    "source_runtime_db": str(fixture.runtime_db),
                    "source_runtime_sha256": fixture.runtime_sha256,
                    "population_manifest": str(fixture.manifest_path),
                    "population_manifest_sha256": fixture.manifest_sha256,
                    "manifest_status": fixture.manifest_status,
                },
                "day": {
                    "current_date": current_date,
                    "history_cutoff": history_cutoff,
                    "is_trading_day": True,
                    "day_1st": True,
                    "multi_day_enabled": False,
                },
                "graph": {
                    "graph_sha256": built_graph.graph_sha256,
                    "n_nodes": built_graph.n_nodes,
                    "n_edges": built_graph.n_edges,
                    "top_fraction": top_fraction,
                    "top_user_ids": list(top_user_ids),
                    "top_user_status_definition": "dynamic graph prominence; not credibility/correctness",
                    "passed_into_inherited_reasoning": True,
                },
                "activation": {
                    "seed": batch.seed,
                    "draw_algorithm": batch.draw_algorithm,
                    "policy_version": batch.policy_version,
                    "active_agent_ids": list(active_ids),
                    "n_active": len(active_ids),
                    "resampled_for_coverage": False,
                    "active_top_user_ids": list(active_top_user_ids),
                },
                "news": {
                    "source": str(news),
                    "n_items_supplied_to_each_active_pipeline": len(news_items),
                    "delivery": "complete daily list; no ranking, truncation or summarisation",
                    "top_user_direct_news_branch_exercised": bool(
                        active_top_user_ids and len(news_items) > 0
                    ),
                    "note": (
                        "TwinMarket receives the same complete daily list for each active Agent; "
                        "direct reading remains inherited and role-dependent."
                    ),
                },
                "agent_reasoning": {
                    "attempted": len(executions),
                    "expected": len(active_ids),
                    "passed": execution_passed,
                    "all_active_agents_completed": (
                        len(executions) == len(active_ids)
                        and execution_passed == len(active_ids)
                    ),
                    "random_technical_shortcut_probability": 0.0,
                    "forum_actions_applied": False,
                },
                "market": {
                    **market_result.to_dict(),
                    "agent_decisions_applied_to_agent_market": True,
                    "participant_decisions_applied_to_agent_market": False,
                    "day_state": day_state,
                    "tradingdetails_may_be_zero_if_no_orders_match": True,
                },
                "reset": reset_result.to_dict(),
                "protected_inputs": {
                    name: {
                        "path": str(protected_inputs[name]),
                        "sha256_before": hashes_before[name],
                        "sha256_after": hashes_after[name],
                        "unchanged": hashes_before[name] == hashes_after[name],
                    }
                    for name in protected_inputs
                },
                "scope": {
                    "custom_market_logic_used": False,
                    "participant_data_used": False,
                    "forum_propagation_enabled": False,
                    "belief_propagation_enabled": False,
                    "controlled_experimental_stimulus_injected": False,
                    "verified_here": [
                        "Phase 3 bounded population membership",
                        "Phase 6 inherited social graph and deterministic dynamic prominence",
                        "Phase 4 natural sparse activation with explicit seed and no resampling",
                        "complete TwinMarket daily-news list supplied to active inherited pipelines",
                        "independent inherited TwinMarket reasoning for active Agents only",
                        "Agent decision JSON delegated to inherited TwinMarket market matching",
                        "isolated Agent-world state advanced for one trading day",
                        "protected source runtime/news/calendar/belief/market-reference files unchanged",
                        "participant state excluded from the Agent-world chain",
                    ],
                    "not_verified_here": [
                        "multi-day forum propagation",
                        "multi-day belief propagation",
                        "multi-day Agent state evolution",
                        "Phase 8 misinformation/correction timing",
                        "participant-visible source cues",
                        "structured Agent research measurement",
                        "formal computational-feasibility evidence",
                    ],
                },
            }
        )
        _json_dump(run_dir / "summary.json", summary)
        return Phase07FullChainOutcome(run_dir=run_dir, summary=summary)

    except Exception as exc:
        finished = datetime.now(timezone.utc)
        summary.update(
            {
                "status": "FAIL",
                "finished_at_utc": finished.isoformat(),
                "duration_seconds": round((finished - started).total_seconds(), 3),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        try:
            summary["protected_inputs_after_failure"] = {
                name: {
                    "path": str(path),
                    "sha256_before": hashes_before[name],
                    "sha256_after": sha256_file(path),
                    "unchanged": hashes_before[name] == sha256_file(path),
                }
                for name, path in protected_inputs.items()
            }
        except Exception:
            pass
        _json_dump(run_dir / "summary.json", summary)
        if isinstance(exc, Phase07FullChainError):
            raise Phase07FullChainError(
                f"{exc} | artifacts: {run_dir}"
            ) from exc
        raise Phase07FullChainError(
            f"Phase 7C failed: {type(exc).__name__}: {exc} | artifacts: {run_dir}"
        ) from exc
