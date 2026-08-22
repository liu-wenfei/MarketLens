"""Phase 5B isolated one-day real-backend preflight support.

This module is deliberately narrow.  It does not change TwinMarket reasoning,
activation, market dynamics, social dynamics, participant state or formal
measurement.  It prepares an isolated Day-1 working environment, delegates the
already-frozen Phase 5A adapter, and writes a minimal non-formal engineering
record.

The paid backend is reached only when ``run_phase05b_preflight`` is called with
``process_user_input_fn=None``.  Tests inject a fake callable and therefore make
zero real model calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
from typing import Any, Callable, Mapping

import networkx as nx
import pandas as pd

from marketlens.agents.activation.policy import ActivationPolicy
from marketlens.agents.activation.profiles import (
    AgentActivationProfile,
    load_activation_profiles,
)
from marketlens.agents.activation.sampler import (
    ActivationBatch,
    AgentActivationResult,
    sample_activation,
)
from marketlens.agents.activation.state import ActivationState

from .adapter import Day1ReasoningContext, ProcessUserInput, execute_activation_batch


PHASE05B_VERSION = "marketlens_phase05b_real_backend_preflight/1.0"
BANNER = "NON-FORMAL / REAL-BACKEND PREFLIGHT / NOT FORMAL EXPERIMENT EVIDENCE"
PREFLIGHT_DATE = pd.Timestamp("2023-06-15")
HISTORY_CUTOFF = pd.Timestamp("2023-06-14")
FORCED_SINGLE_AGENT_DRAW_ALGORITHM = "forced_single_agent_preflight_gate/1.0"
FORCED_SINGLE_AGENT_SEED = "FORCED_PHASE05B_SINGLE_AGENT_GATE"


class Phase05BPreflightError(RuntimeError):
    """Raised when the preflight cannot be prepared or executed safely."""


@dataclass(frozen=True)
class BoundedAgentMetadata:
    user_id: str
    strategy: str
    user_type: str
    activity_category: str


@dataclass(frozen=True)
class VerifiedPopulationFixture:
    runtime_db: Path
    manifest_path: Path
    runtime_sha256: str
    manifest_sha256: str
    population_ids: tuple[str, ...]
    manifest_status: str | None


@dataclass(frozen=True)
class PreflightOutcome:
    run_dir: Path
    summary: Mapping[str, Any]


def sha256_file(path: str | Path) -> str:
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise Phase05BPreflightError(f"SQLite database does not exist: {path}")
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _infer_manifest_path(runtime_db: Path, manifest_path: str | Path | None) -> Path:
    if manifest_path is not None:
        candidate = Path(manifest_path).resolve()
    else:
        candidate = runtime_db.parent / "population_manifest.json"
    if not candidate.is_file():
        raise Phase05BPreflightError(
            "Phase 5B requires the Phase 3B population_manifest.json paired with "
            f"the bounded runtime DB; not found: {candidate}"
        )
    return candidate


def _read_population_ids(runtime_db: Path) -> tuple[str, ...]:
    connection = _connect_ro(runtime_db)
    try:
        rows = connection.execute(
            "SELECT CAST(user_id AS TEXT) AS user_id FROM Profiles "
            "ORDER BY CAST(user_id AS TEXT)"
        ).fetchall()
    except sqlite3.Error as exc:
        raise Phase05BPreflightError("runtime DB must contain Profiles.user_id") from exc
    finally:
        connection.close()

    ids = tuple(str(row["user_id"]) for row in rows)
    if not ids:
        raise Phase05BPreflightError("bounded runtime DB contains no Agents")
    if len(set(ids)) != len(ids):
        raise Phase05BPreflightError("bounded runtime DB contains duplicate Profiles.user_id")
    return ids


def verify_population_fixture(
    runtime_db: str | Path,
    manifest_path: str | Path | None = None,
) -> VerifiedPopulationFixture:
    """Verify that a runtime DB is the exact Phase 3B fixture named by its manifest."""

    runtime_path = Path(runtime_db).resolve()
    if not runtime_path.is_file():
        raise Phase05BPreflightError(f"bounded runtime DB does not exist: {runtime_path}")
    manifest = _infer_manifest_path(runtime_path, manifest_path)
    try:
        doc = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        raise Phase05BPreflightError(f"could not parse population manifest: {manifest}") from exc

    runtime_hash = sha256_file(runtime_path)
    expected_hash = (
        doc.get("runtime_fixture", {}).get("fixture_sha256")
        if isinstance(doc, Mapping)
        else None
    )
    if not expected_hash:
        raise Phase05BPreflightError(
            "population manifest is missing runtime_fixture.fixture_sha256"
        )
    if str(expected_hash) != runtime_hash:
        raise Phase05BPreflightError(
            "bounded runtime DB hash does not match the Phase 3B population manifest"
        )

    manifest_ids_raw = doc.get("selection", {}).get("selected_agent_ids", [])
    manifest_ids = tuple(sorted(str(user_id) for user_id in manifest_ids_raw))
    runtime_ids = _read_population_ids(runtime_path)
    if manifest_ids != runtime_ids:
        raise Phase05BPreflightError(
            "bounded runtime DB Agent membership differs from the Phase 3B manifest"
        )

    return VerifiedPopulationFixture(
        runtime_db=runtime_path,
        manifest_path=manifest,
        runtime_sha256=runtime_hash,
        manifest_sha256=sha256_file(manifest),
        population_ids=runtime_ids,
        manifest_status=(str(doc.get("status")) if doc.get("status") is not None else None),
    )


def load_bounded_agent_metadata(runtime_db: str | Path) -> dict[str, BoundedAgentMetadata]:
    path = Path(runtime_db).resolve()
    connection = _connect_ro(path)
    try:
        rows = connection.execute(
            """
            SELECT CAST(user_id AS TEXT) AS user_id,
                   CAST(strategy AS TEXT) AS strategy,
                   CAST(user_type AS TEXT) AS user_type,
                   CAST(trade_count_category AS TEXT) AS activity_category
            FROM Profiles
            ORDER BY CAST(user_id AS TEXT)
            """
        ).fetchall()
    except sqlite3.Error as exc:
        raise Phase05BPreflightError(
            "runtime Profiles must contain user_id, strategy, user_type and trade_count_category"
        ) from exc
    finally:
        connection.close()

    metadata: dict[str, BoundedAgentMetadata] = {}
    for row in rows:
        user_id = str(row["user_id"])
        if user_id in metadata:
            raise Phase05BPreflightError(f"duplicate Agent metadata for {user_id}")
        metadata[user_id] = BoundedAgentMetadata(
            user_id=user_id,
            strategy=str(row["strategy"]),
            user_type=str(row["user_type"]),
            activity_category=str(row["activity_category"]),
        )
    if not metadata:
        raise Phase05BPreflightError("runtime Profiles contains no Agent metadata")
    return metadata


def _validate_previous_day_profiles(runtime_db: Path, population_ids: tuple[str, ...]) -> None:
    connection = _connect_ro(runtime_db)
    try:
        rows = connection.execute(
            """
            SELECT CAST(user_id AS TEXT) AS user_id, COUNT(*) AS n
            FROM Profiles
            WHERE date(created_at) = ?
            GROUP BY CAST(user_id AS TEXT)
            """,
            (HISTORY_CUTOFF.strftime("%Y-%m-%d"),),
        ).fetchall()
    except sqlite3.Error as exc:
        raise Phase05BPreflightError(
            "runtime Profiles must contain created_at for the Day-1 previous-date lookup"
        ) from exc
    finally:
        connection.close()

    counts = {str(row["user_id"]): int(row["n"]) for row in rows}
    missing = sorted(set(population_ids) - set(counts))
    ambiguous = sorted(user_id for user_id, count in counts.items() if count != 1)
    extra = sorted(set(counts) - set(population_ids))
    if missing or ambiguous or extra:
        raise Phase05BPreflightError(
            "Day-1 preflight requires exactly one 2023-06-14 Profiles row per bounded Agent; "
            f"missing={missing}, ambiguous={ambiguous}, extra={extra}"
        )


def load_day1_frames(runtime_db: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load Strategy and stock history, cutting StockData off at 2023-06-14."""

    path = Path(runtime_db).resolve()
    connection = _connect_ro(path)
    try:
        df_strategy = pd.read_sql_query("SELECT * FROM Strategy", connection)
        df_stock = pd.read_sql_query("SELECT * FROM StockData", connection)
    except Exception as exc:
        raise Phase05BPreflightError("could not load Strategy/StockData from runtime DB") from exc
    finally:
        connection.close()

    if "user_id" not in df_strategy.columns or "strategy" not in df_strategy.columns:
        raise Phase05BPreflightError("Strategy must contain user_id and strategy")
    if "date" not in df_stock.columns:
        raise Phase05BPreflightError("StockData must contain date")

    df_stock = df_stock.copy()
    df_stock["date"] = pd.to_datetime(df_stock["date"], errors="raise")
    df_stock = df_stock[df_stock["date"] <= HISTORY_CUTOFF].copy()
    if df_stock.empty:
        raise Phase05BPreflightError("no StockData rows remain at or before 2023-06-14")
    if df_stock["date"].max() > HISTORY_CUTOFF:
        raise Phase05BPreflightError("future StockData leaked past the Phase 5B cutoff")
    return df_strategy, df_stock


def load_initial_beliefs(
    belief_csv: str | Path,
    required_agent_ids: tuple[str, ...],
) -> pd.DataFrame:
    """Load inherited initial beliefs and fail closed for any Agent that will execute."""

    path = Path(belief_csv).resolve()
    if not path.is_file():
        raise Phase05BPreflightError(f"initial belief CSV does not exist: {path}")
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        raise Phase05BPreflightError(f"could not read initial belief CSV: {path}") from exc
    if "user_id" not in frame.columns or "belief" not in frame.columns:
        raise Phase05BPreflightError("initial belief CSV must contain user_id and belief")

    frame = frame.copy()
    frame["user_id"] = frame["user_id"].astype(str)
    if frame["user_id"].duplicated().any():
        duplicates = sorted(frame.loc[frame["user_id"].duplicated(), "user_id"].unique())
        raise Phase05BPreflightError(f"initial belief CSV has duplicate user_id values: {duplicates}")

    required = set(str(user_id) for user_id in required_agent_ids)
    if not required:
        return frame.iloc[0:0].copy()
    subset = frame[frame["user_id"].isin(required)].copy()
    missing = sorted(required - set(subset["user_id"]))
    empty = sorted(
        str(row.user_id)
        for row in subset.itertuples()
        if pd.isna(row.belief) or not str(row.belief).strip()
    )
    if missing or empty:
        raise Phase05BPreflightError(
            f"initial belief coverage failed for executing Agent(s); missing={missing}, empty={empty}"
        )
    return subset


def build_isolated_graph(population_ids: tuple[str, ...]) -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(population_ids)
    if graph.number_of_edges() != 0:
        raise Phase05BPreflightError("Phase 5B graph scaffold must contain zero edges")
    return graph


def _load_inherited_forum_initializer() -> Callable[..., Any]:
    try:
        from util.ForumDB import init_db_forum
    except Exception as exc:  # pragma: no cover - inherited environment branch
        raise Phase05BPreflightError("could not import inherited util.ForumDB.init_db_forum") from exc
    return init_db_forum


def create_empty_forum_db(
    path: str | Path,
    *,
    forum_initializer: Callable[..., Any] | None = None,
) -> Path:
    """Create an empty schema-valid forum using the inherited TwinMarket initializer."""

    forum_path = Path(path).resolve()
    if forum_path.exists():
        raise Phase05BPreflightError(f"refusing to overwrite working forum DB: {forum_path}")
    forum_path.parent.mkdir(parents=True, exist_ok=True)
    initializer = forum_initializer or _load_inherited_forum_initializer()
    initializer(db_path=str(forum_path))
    if not forum_path.is_file():
        raise Phase05BPreflightError("inherited forum initializer did not create a database")

    connection = sqlite3.connect(forum_path)
    try:
        table_names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        required = {"posts", "reactions", "post_references"}
        if not required.issubset(table_names):
            raise Phase05BPreflightError(
                f"working forum DB is missing inherited tables: {sorted(required - table_names)}"
            )
        nonempty = {
            table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in sorted(required)
        }
        if any(nonempty.values()):
            raise Phase05BPreflightError(
                f"Phase 5B requires an empty forum scaffold; row counts={nonempty}"
            )
    finally:
        connection.close()
    return forum_path


def build_forced_single_agent_batch(
    runtime_db: str | Path,
    user_id: str,
    *,
    step: int = 0,
) -> ActivationBatch:
    """Build a transparent forced one-Agent gate for the first paid integration check.

    This is intentionally *not* presented as a Phase 4 stochastic sample.  It keeps
    the complete bounded population in the activation mapping but marks exactly the
    requested Agent active so the one-Agent real-backend pipeline can be isolated.
    """

    profiles = load_activation_profiles(runtime_db)
    selected = str(user_id)
    population_ids = tuple(profile.user_id for profile in profiles)
    if selected not in set(population_ids):
        raise Phase05BPreflightError(
            f"requested Agent {selected!r} is outside the bounded Phase 3 population"
        )

    policy = ActivationPolicy()
    state = ActivationState()
    results: list[AgentActivationResult] = []
    for profile in profiles:
        propensity = policy.propensity(
            activity_category=profile.activity_category,
            steps_since_last_activation=state.steps_for(profile.user_id),
        )
        is_active = profile.user_id == selected
        results.append(
            AgentActivationResult(
                user_id=profile.user_id,
                activity_category=profile.activity_category,
                propensity=propensity,
                random_draw=(0.0 if is_active else 0.9999999999999999),
                is_active=is_active,
            )
        )

    next_state = state.advance({selected}, population_ids)
    return ActivationBatch(
        step=int(step),
        seed=FORCED_SINGLE_AGENT_SEED,
        draw_algorithm=FORCED_SINGLE_AGENT_DRAW_ALGORITHM,
        policy_version=policy.config.policy_version,
        results=tuple(results),
        active_agent_ids=(selected,),
        next_state=next_state,
    )


def build_phase4_activation_batch(
    runtime_db: str | Path,
    *,
    seed: str,
    step: int = 0,
) -> ActivationBatch:
    if not str(seed):
        raise Phase05BPreflightError("activation mode requires a non-empty explicit seed")
    profiles = load_activation_profiles(runtime_db)
    return sample_activation(
        profiles,
        policy=ActivationPolicy(),
        state=ActivationState(),
        seed=str(seed),
        step=int(step),
    )


def collect_git_state(repo_root: str | Path) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True, stderr=subprocess.STDOUT
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo, text=True, stderr=subprocess.STDOUT
        )
    except subprocess.CalledProcessError as exc:
        raise Phase05BPreflightError("Phase 5B must run from a valid Git worktree") from exc
    return {"commit": commit, "clean": not bool(status.strip()), "status": status.strip()}


def _safe_backend_metadata(config_path: Path) -> dict[str, Any]:
    """Read only non-secret backend labels. API keys are never returned or stored."""

    metadata: dict[str, Any] = {
        "config_path": str(config_path),
        "model_name": None,
        "base_url": None,
        "api_key_recorded": False,
    }
    try:
        import yaml

        doc = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if isinstance(doc, Mapping):
            if doc.get("model_name") is not None:
                metadata["model_name"] = str(doc.get("model_name"))
            if doc.get("base_url") is not None:
                metadata["base_url"] = str(doc.get("base_url"))
    except Exception:
        # Backend labels are optional audit metadata.  Failure to parse them must
        # never lead us to inspect or serialize secret fields.
        pass
    return metadata


def _copy_conversation_logs(working_log_dir: Path, run_dir: Path) -> bool:
    source = working_log_dir / "conversation_records"
    if not source.is_dir():
        return False
    destination = run_dir / "inherited_logs" / "conversation_records"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return True


def _agent_payload(execution: Any, metadata: BoundedAgentMetadata | None) -> dict[str, Any]:
    return {
        "user_id": execution.user_id,
        "strategy": metadata.strategy if metadata else None,
        "user_type": metadata.user_type if metadata else None,
        "activity_category": metadata.activity_category if metadata else None,
        "pipeline_called": True,
        "completed_successfully": execution.completed_successfully,
        "returned_tuple_shape_ok": execution.returned_tuple_shape_ok,
        "returned_user_id": execution.returned_user_id,
        "returned_user_id_matches": execution.returned_user_id == execution.user_id,
        "inherited_error": execution.inherited_error,
        "decision_result_present": execution.decision_result_present,
        "post_response_args_present": execution.post_response_args_present,
        "forum_args": execution.forum_args,
        "decision_result": execution.decision_result,
        "post_response_args": execution.post_response_args,
        "agent_decision_applied_to_market": False,
        "forum_actions_applied": False,
    }


def _run_id(mode: str, commit: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short = commit[:8] if commit else "nogit"
    return f"{stamp}_{short}_{mode.replace('-', '_')}"


def run_phase05b_preflight(
    *,
    repo_root: str | Path,
    runtime_db: str | Path,
    belief_csv: str | Path,
    config_path: str | Path,
    artifact_root: str | Path,
    mode: str,
    user_id: str | None = None,
    seed: str | None = None,
    population_manifest: str | Path | None = None,
    process_user_input_fn: ProcessUserInput | None = None,
    forum_initializer: Callable[..., Any] | None = None,
    require_clean_git: bool = True,
    git_state_override: Mapping[str, Any] | None = None,
    preserve_failed_workspace: bool = False,
) -> PreflightOutcome:
    """Run one isolated Day-1 preflight and persist only minimal non-formal artifacts.

    Real backend behaviour is obtained by leaving ``process_user_input_fn=None``.
    Unit tests pass a fake callable, which exercises the exact adapter and storage
    boundary without contacting any backend.
    """

    repo = Path(repo_root).resolve()
    config = Path(config_path).resolve()
    beliefs = Path(belief_csv).resolve()
    artifacts = Path(artifact_root).resolve()
    if mode not in {"one-agent", "activation"}:
        raise Phase05BPreflightError("mode must be 'one-agent' or 'activation'")
    if not config.is_file():
        raise Phase05BPreflightError(f"TwinMarket backend config does not exist: {config}")
    if not beliefs.is_file():
        raise Phase05BPreflightError(f"initial belief CSV does not exist: {beliefs}")

    git_state = dict(git_state_override or collect_git_state(repo))
    if require_clean_git and not bool(git_state.get("clean")):
        raise Phase05BPreflightError(
            "real-backend preflight requires a clean committed Git worktree; "
            f"git status={git_state.get('status')!r}"
        )
    commit = str(git_state.get("commit") or "")

    fixture = verify_population_fixture(runtime_db, population_manifest)
    metadata = load_bounded_agent_metadata(fixture.runtime_db)
    _validate_previous_day_profiles(fixture.runtime_db, fixture.population_ids)

    if mode == "one-agent":
        if user_id is None or not str(user_id):
            raise Phase05BPreflightError("one-agent mode requires --user-id")
        batch = build_forced_single_agent_batch(fixture.runtime_db, str(user_id), step=0)
    else:
        if seed is None or not str(seed):
            raise Phase05BPreflightError("activation mode requires --seed")
        batch = build_phase4_activation_batch(fixture.runtime_db, seed=str(seed), step=0)

    run_id = _run_id(mode, commit)
    run_dir = artifacts / run_id
    if run_dir.exists():
        raise Phase05BPreflightError(f"refusing to overwrite existing preflight run: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)

    source_hash_before = sha256_file(fixture.runtime_db)
    belief_hash_before = sha256_file(beliefs)
    start = datetime.now(timezone.utc)
    temp_preserved = False

    with tempfile.TemporaryDirectory(prefix="marketlens_phase05b_") as temp_name:
        workspace = Path(temp_name)
        working_db = workspace / "runtime.db"
        working_forum = workspace / "forum.db"
        working_logs = workspace / "inherited_logs"
        working_logs.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture.runtime_db, working_db)
        create_empty_forum_db(working_forum, forum_initializer=forum_initializer)

        df_strategy, df_stock = load_day1_frames(working_db)
        executing_ids = tuple(batch.active_agent_ids)
        belief_args = load_initial_beliefs(beliefs, executing_ids)
        graph = build_isolated_graph(fixture.population_ids)
        context = Day1ReasoningContext(
            working_user_db=working_db,
            working_forum_db=working_forum,
            df_stock=df_stock,
            current_date=PREFLIGHT_DATE,
            graph_scaffold=graph,
            df_strategy=df_strategy,
            belief_args=belief_args,
            log_dir=working_logs,
            config_path=config,
            debug=False,
            is_trading_day=True,
        )

        try:
            execution = execute_activation_batch(
                batch,
                context=context,
                process_user_input_fn=process_user_input_fn,
            )
            source_hash_after = sha256_file(fixture.runtime_db)
            belief_hash_after = sha256_file(beliefs)
            if source_hash_after != source_hash_before:
                raise Phase05BPreflightError("frozen Phase 3 runtime DB changed during preflight")
            if belief_hash_after != belief_hash_before:
                raise Phase05BPreflightError("initial belief source changed during preflight")

            for agent_execution in execution.executions:
                _json_dump(
                    run_dir / "agents" / f"{agent_execution.user_id}.json",
                    _agent_payload(agent_execution, metadata.get(agent_execution.user_id)),
                )
            inherited_logs_preserved = _copy_conversation_logs(working_logs, run_dir)

            passed_executions = [
                item
                for item in execution.executions
                if item.completed_successfully
                and item.returned_tuple_shape_ok
                and item.returned_user_id == item.user_id
                and item.inherited_error is None
                and item.decision_result_present
            ]
            if mode == "activation" and execution.attempted == 0:
                status = "NO_ACTIVE_AGENTS"
                reason = (
                    "Phase 4 produced zero stochastic activations for the explicit seed; "
                    "the runner did not resample or fish for another seed."
                )
            elif len(passed_executions) == execution.attempted and execution.attempted > 0:
                status = "PASS"
                reason = None
            else:
                status = "FAIL"
                reason = "one or more inherited Agent pipelines failed the Phase 5B gate"
        except Exception:
            if preserve_failed_workspace:
                debug_copy = run_dir / "debug_workspace"
                shutil.copytree(workspace, debug_copy)
                temp_preserved = True
            raise

    finished = datetime.now(timezone.utc)
    summary = {
        "banner": BANNER,
        "phase": "5B",
        "preflight_version": PHASE05B_VERSION,
        "formal_experiment_evidence": False,
        "run_id": run_id,
        "status": status,
        "reason": reason,
        "mode": mode,
        "generated_at_utc": finished.isoformat(),
        "started_at_utc": start.isoformat(),
        "finished_at_utc": finished.isoformat(),
        "duration_seconds": round((finished - start).total_seconds(), 3),
        "git": {
            "commit": commit,
            "clean_at_start": bool(git_state.get("clean")),
        },
        "population": {
            "runtime_db": str(fixture.runtime_db),
            "runtime_sha256_before": source_hash_before,
            "runtime_sha256_after": source_hash_after,
            "manifest": str(fixture.manifest_path),
            "manifest_sha256": fixture.manifest_sha256,
            "manifest_status": fixture.manifest_status,
            "n_population": len(fixture.population_ids),
        },
        "day1_context": {
            "date": PREFLIGHT_DATE.strftime("%Y-%m-%d"),
            "history_cutoff": HISTORY_CUTOFF.strftime("%Y-%m-%d"),
            "day_1st": True,
            "is_trading_day": True,
            "graph_mode": "isolated_nodes",
            "graph_edges": 0,
            "dynamic_top_users_enabled": False,
            "news_supplied": 0,
            "random_technical_shortcut_probability": 0.0,
            "forum_mode": "empty_inherited_schema_scaffold",
        },
        "activation": {
            "mode": mode,
            "seed": batch.seed,
            "draw_algorithm": batch.draw_algorithm,
            "policy_version": batch.policy_version,
            "active_agent_ids": list(batch.active_agent_ids),
            "n_active": len(batch.active_agent_ids),
            "resampled_for_coverage": False,
        },
        "agent_execution": {
            "attempted": execution.attempted,
            "completed_successfully_by_adapter": execution.completed_successfully,
            "failed_by_adapter": execution.failed,
            "passed_phase05b_gate": len(passed_executions),
            "agent_decisions_applied_to_market": False,
            "forum_actions_applied": False,
        },
        "belief_source": {
            "path": str(beliefs),
            "sha256_before": belief_hash_before,
            "sha256_after": belief_hash_after,
            "updated": False,
        },
        "backend": _safe_backend_metadata(config),
        "participant_state_read": False,
        "participant_database_used": False,
        "inherited_conversation_logs_preserved": inherited_logs_preserved,
        "temporary_runtime_db_preserved": temp_preserved,
        "temporary_forum_db_preserved": temp_preserved,
        "scope": {
            "verified_here": [
                "Phase 5A adapter gates inherited reasoning by active Agent IDs",
                "one-day inherited TwinMarket reasoning execution",
                "isolated writable runtime/forum copies",
                "no Agent decision is applied to the exogenous market",
            ],
            "not_verified_here": [
                "dynamic social graph or top-user behaviour",
                "controlled news behaviour",
                "multi-day forum propagation",
                "multi-day belief propagation",
                "multi-day Agent portfolio/state evolution",
                "structured Agent research measurement",
                "formal computational-feasibility evidence",
                "formal population-size recommendation",
            ],
        },
    }
    _json_dump(run_dir / "summary.json", summary)
    return PreflightOutcome(run_dir=run_dir, summary=summary)
