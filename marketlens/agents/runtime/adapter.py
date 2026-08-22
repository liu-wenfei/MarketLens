"""Phase 5A: gate inherited TwinMarket reasoning with Phase 4 activation.

This module intentionally does *not* reimplement TwinMarket prompts, strategy
logic, forum reasoning, trading logic or LLM access.  For each activated Agent
it delegates to the inherited ``simulation.process_user_input`` entry point.

Scope boundary
--------------
* only Phase 4 ``active_agent_ids`` enter the inherited pipeline;
* inactive Agents are never delegated;
* ``day_1st=True`` is forced;
* ``prob_of_technical=0.0`` is forced, disabling TwinMarket's random Technical
  trader shortcut so every activated Agent remains an independent reasoning
  unit;
* ``top_user=[]`` and ``import_news=[]`` are forced.  Dynamic social prominence
  and controlled news belong to later phases;
* participant state is not an input to this adapter;
* this module performs no API call on import and no real-backend call unless the
  caller explicitly invokes ``execute_activation_batch`` with the inherited
  callable (or allows the lazy default resolver).

Phase 5B will own temporary runtime/forum copies and the paid one-day preflight.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from marketlens.agents.activation.sampler import ActivationBatch

from .models import (
    AgentReasoningExecution,
    ReasoningBatchExecution,
    RUNTIME_ADAPTER_VERSION,
)


class ReasoningAdapterError(RuntimeError):
    """Raised when Phase 5A cannot safely delegate an activation batch."""


class ProcessUserInput(Protocol):
    def __call__(self, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class Day1ReasoningContext:
    """Minimum inherited inputs allowed through the Phase 5A boundary.

    ``working_user_db`` and ``working_forum_db`` are intentionally named
    *working* paths.  Real-backend execution must provide isolated temporary
    copies rather than repository source artifacts; Phase 5B owns that copying
    and verification.

    No participant object, participant portfolio, user_type, is_top_user, live
    news, market-event activation feature or social-prominence input exists in
    this contract.
    """

    working_user_db: str | Path
    working_forum_db: str | Path
    df_stock: Any
    current_date: Any
    graph_scaffold: Any
    df_strategy: Any
    belief_args: Any
    log_dir: str | Path
    config_path: str | Path
    debug: bool = False
    is_trading_day: bool = True


def load_inherited_process_user_input() -> ProcessUserInput:
    """Lazily resolve the official TwinMarket single-Agent entry point.

    Import is deferred so Phase 5A unit tests can run with zero backend/API
    dependency and without importing the heavy inherited execution stack.
    """

    try:
        simulation = importlib.import_module("simulation")
    except Exception as exc:  # pragma: no cover - environment-specific branch
        raise ReasoningAdapterError(
            "could not import inherited TwinMarket simulation module"
        ) from exc

    process = getattr(simulation, "process_user_input", None)
    if not callable(process):
        raise ReasoningAdapterError(
            "inherited simulation module has no callable process_user_input"
        )
    return process


def _normalise_strategy_frame(df_strategy: Any, population_ids: tuple[str, ...]) -> Any:
    """Copy and string-normalise the inherited Strategy frame.

    TwinMarket's own ``init_simulation`` converts Strategy.user_id to ``str``
    before calling ``process_user_input``.  Phase 3 preserves inherited table
    types (Profiles TEXT, Strategy INTEGER in the audited source), so the thin
    adapter reproduces that exact normalisation rather than changing either DB.
    """

    if not hasattr(df_strategy, "copy") or not hasattr(df_strategy, "columns"):
        raise ReasoningAdapterError("df_strategy must be a pandas-like DataFrame")
    if "user_id" not in df_strategy.columns or "strategy" not in df_strategy.columns:
        raise ReasoningAdapterError("df_strategy must contain user_id and strategy columns")

    normalised = df_strategy.copy()
    normalised["user_id"] = normalised["user_id"].astype(str)

    population = set(population_ids)
    rows = normalised[normalised["user_id"].isin(population)]
    counts = rows.groupby("user_id").size().to_dict()
    missing = sorted(population - set(counts))
    duplicates = sorted(user_id for user_id, count in counts.items() if int(count) != 1)
    if missing:
        raise ReasoningAdapterError(
            f"df_strategy is missing bounded Agent(s): {missing}"
        )
    if duplicates:
        raise ReasoningAdapterError(
            f"df_strategy must contain exactly one strategy row per bounded Agent: {duplicates}"
        )
    return normalised


def _activation_mapping(batch: ActivationBatch) -> tuple[tuple[str, ...], dict[str, bool]]:
    population_ids = tuple(sorted(result.user_id for result in batch.results))
    if not population_ids:
        raise ReasoningAdapterError("activation batch contains no bounded Agents")
    if len(set(population_ids)) != len(population_ids):
        raise ReasoningAdapterError("activation batch contains duplicate Agent IDs")

    active_ids = tuple(sorted(str(user_id) for user_id in batch.active_agent_ids))
    unknown = sorted(set(active_ids) - set(population_ids))
    if unknown:
        raise ReasoningAdapterError(
            f"activation batch contains active Agent(s) outside bounded population: {unknown}"
        )

    result_active_ids = tuple(
        sorted(result.user_id for result in batch.results if result.is_active)
    )
    if active_ids != result_active_ids:
        raise ReasoningAdapterError(
            "activation batch active_agent_ids disagrees with per-Agent activation results"
        )

    mapping = {user_id: user_id in set(active_ids) for user_id in population_ids}
    return population_ids, mapping


def _parse_execution(expected_user_id: str, returned: Any) -> AgentReasoningExecution:
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

    returned_user_id_str = (
        str(returned_user_id) if returned_user_id is not None else None
    )
    completed = bool(
        tuple_shape_ok
        and returned_user_id_str == expected_user_id
        and inherited_error is None
    )

    return AgentReasoningExecution(
        user_id=expected_user_id,
        completed_successfully=completed,
        returned_tuple_shape_ok=tuple_shape_ok,
        returned_user_id=returned_user_id_str,
        inherited_error=inherited_error,
        decision_result_present=decision_result is not None,
        post_response_args_present=post_response_args is not None,
        forum_args=forum_args,
        decision_result=decision_result,
        post_response_args=post_response_args,
    )


def execute_activation_batch(
    batch: ActivationBatch,
    *,
    context: Day1ReasoningContext,
    process_user_input_fn: ProcessUserInput | None = None,
) -> ReasoningBatchExecution:
    """Delegate exactly the activated Agents to TwinMarket reasoning.

    Calls are sequential in Phase 5A on purpose.  Concurrency, throughput and
    cost optimisation are not required to prove the activation gate and can be
    introduced only after the inherited path has been validated safely.
    """

    population_ids, activate_mapping = _activation_mapping(batch)
    active_ids = tuple(sorted(batch.active_agent_ids))
    df_strategy = _normalise_strategy_frame(context.df_strategy, population_ids)

    process = process_user_input_fn or load_inherited_process_user_input()
    config_path = str(context.config_path)
    user_config_mapping = {user_id: config_path for user_id in population_ids}

    executions: list[AgentReasoningExecution] = []
    for user_id in active_ids:
        returned = process(
            user_id=user_id,
            user_db=str(context.working_user_db),
            forum_db=str(context.working_forum_db),
            df_stock=context.df_stock,
            current_date=context.current_date,
            debug=bool(context.debug),
            day_1st=True,
            current_user_graph=context.graph_scaffold,
            import_news=[],
            df_strategy=df_strategy,
            is_trading_day=bool(context.is_trading_day),
            top_user=[],
            log_dir=str(context.log_dir),
            prob_of_technical=0.0,
            user_config_mapping=user_config_mapping,
            activate_maapping=activate_mapping,
            belief_args=context.belief_args,
            config_path=config_path,
        )
        executions.append(_parse_execution(user_id, returned))

    return ReasoningBatchExecution(
        adapter_version=RUNTIME_ADAPTER_VERSION,
        step=int(batch.step),
        population_agent_ids=population_ids,
        active_agent_ids=active_ids,
        executions=tuple(executions),
    )
