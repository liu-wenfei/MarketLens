from __future__ import annotations

from dataclasses import replace
import sys
from types import ModuleType

import pandas as pd
import pytest

from marketlens.agents.activation.policy import ActivationPolicy, ActivationConfig
from marketlens.agents.activation.profiles import AgentActivationProfile
from marketlens.agents.activation.sampler import ActivationBatch, sample_activation
from marketlens.agents.activation.state import ActivationState
from marketlens.agents.runtime import (
    Day1ReasoningContext,
    ReasoningAdapterError,
    execute_activation_batch,
    load_inherited_process_user_input,
)


def _batch(*, seed: str = "phase5a", step: int = 0) -> ActivationBatch:
    profiles = (
        AgentActivationProfile("101", "低"),
        AgentActivationProfile("202", "中"),
        AgentActivationProfile("303", "高"),
    )
    # Force all probabilities to the same deterministic engineering value so the
    # test chooses a reproducible subset from the real Phase 4 sampler.
    policy = ActivationPolicy(
        ActivationConfig(
            activity_baselines={"低": 0.5, "中": 0.5, "高": 0.5},
            p_min=0.01,
            p_max=0.99,
            recency_weight=0.0,
        )
    )
    return sample_activation(
        profiles,
        policy=policy,
        state=ActivationState(),
        seed=seed,
        step=step,
    )


def _context() -> Day1ReasoningContext:
    return Day1ReasoningContext(
        working_user_db="/tmp/runtime.db",
        working_forum_db="/tmp/forum.db",
        df_stock=pd.DataFrame({"date": []}),
        current_date=pd.Timestamp("2023-06-15"),
        graph_scaffold=object(),
        # Int user IDs deliberately reproduce inherited Strategy typing.  The
        # adapter must copy + string-normalise as TwinMarket init_simulation does.
        df_strategy=pd.DataFrame(
            {
                "user_id": [101, 202, 303],
                "strategy": ["基本面", "技术面", "技术面"],
            }
        ),
        belief_args=pd.DataFrame(
            {"user_id": ["101", "202", "303"], "belief": [0.0, 0.0, 0.0]}
        ),
        log_dir="/tmp/marketlens-phase5a",
        config_path="config/api.yaml",
    )


def test_only_active_agents_are_delegated_and_inactive_agents_never_enter_pipeline():
    batch = _batch(seed="active-gate")
    assert 0 < len(batch.active_agent_ids) < len(batch.results)
    calls = []

    def fake_process(**kwargs):
        calls.append(kwargs)
        uid = kwargs["user_id"]
        return uid, {}, {"decision": "placeholder"}, None

    result = execute_activation_batch(
        batch, context=_context(), process_user_input_fn=fake_process
    )

    assert [call["user_id"] for call in calls] == list(batch.active_agent_ids)
    assert result.active_agent_ids == batch.active_agent_ids
    assert result.attempted == len(batch.active_agent_ids)
    inactive = {r.user_id for r in batch.results if not r.is_active}
    assert inactive.isdisjoint({call["user_id"] for call in calls})


def test_adapter_forces_phase5a_scope_controls_on_every_inherited_call():
    batch = _batch(seed="scope-controls")
    calls = []

    def fake_process(**kwargs):
        calls.append(kwargs)
        return kwargs["user_id"], {}, {}, None

    execute_activation_batch(batch, context=_context(), process_user_input_fn=fake_process)
    assert calls
    for call in calls:
        assert call["day_1st"] is True
        assert call["prob_of_technical"] == 0.0
        assert call["top_user"] == []
        assert call["import_news"] == []
        assert call["current_user_graph"] is _context().graph_scaffold or call["current_user_graph"] is not None


def test_adapter_passes_complete_activation_mapping_but_executes_only_active_ids():
    batch = _batch(seed="mapping")
    calls = []

    def fake_process(**kwargs):
        calls.append(kwargs)
        return kwargs["user_id"], {}, {}, None

    execute_activation_batch(batch, context=_context(), process_user_input_fn=fake_process)
    expected = {r.user_id: r.is_active for r in batch.results}
    for call in calls:
        assert call["activate_maapping"] == expected
        assert call["activate_maapping"][call["user_id"]] is True


def test_strategy_ids_are_normalised_without_mutating_caller_frame():
    batch = _batch(seed="strategy-normalisation")
    context = _context()
    original_dtypes = context.df_strategy.dtypes.copy()
    seen = []

    def fake_process(**kwargs):
        seen.append(kwargs["df_strategy"].copy())
        return kwargs["user_id"], {}, {}, None

    execute_activation_batch(batch, context=context, process_user_input_fn=fake_process)
    assert seen
    assert all(frame["user_id"].map(type).eq(str).all() for frame in seen)
    assert context.df_strategy.dtypes.equals(original_dtypes)
    assert context.df_strategy["user_id"].map(type).eq(int).all()


def test_missing_strategy_for_bounded_agent_fails_before_any_delegation():
    batch = _batch(seed="missing-strategy")
    context = _context()
    bad = context.df_strategy[context.df_strategy["user_id"] != 303]
    calls = []

    with pytest.raises(ReasoningAdapterError, match="missing bounded Agent"):
        execute_activation_batch(
            batch,
            context=replace(context, df_strategy=bad),
            process_user_input_fn=lambda **kwargs: calls.append(kwargs),
        )
    assert calls == []


def test_inherited_error_tuple_is_recorded_as_failed_without_repair_call():
    batch = _batch(seed="error-record")
    calls = []

    def fake_process(**kwargs):
        calls.append(kwargs)
        return kwargs["user_id"], {"error": "inherited failure"}, None, None

    result = execute_activation_batch(
        batch, context=_context(), process_user_input_fn=fake_process
    )
    assert result.attempted == len(batch.active_agent_ids)
    assert result.failed == result.attempted
    assert all(execution.inherited_error == "inherited failure" for execution in result.executions)
    assert len(calls) == result.attempted  # no repair/retry call in Phase 5A


def test_empty_active_subset_makes_zero_inherited_calls():
    batch = _batch(seed="empty-active")
    empty_results = tuple(replace(result, is_active=False) for result in batch.results)
    empty = replace(batch, results=empty_results, active_agent_ids=())
    calls = []

    result = execute_activation_batch(
        empty,
        context=_context(),
        process_user_input_fn=lambda **kwargs: calls.append(kwargs),
    )
    assert calls == []
    assert result.attempted == 0
    assert result.active_agent_ids == ()


def test_inconsistent_activation_batch_is_rejected_before_delegation():
    batch = _batch(seed="inconsistent")
    first = batch.results[0]
    inconsistent = replace(
        batch,
        results=(replace(first, is_active=not first.is_active),) + batch.results[1:],
    )
    with pytest.raises(ReasoningAdapterError, match="disagrees"):
        execute_activation_batch(
            inconsistent,
            context=_context(),
            process_user_input_fn=lambda **kwargs: None,
        )


def test_lazy_inherited_resolver_loads_process_user_input_without_executing_it(monkeypatch):
    module = ModuleType("simulation")
    calls = []

    def process_user_input(**kwargs):
        calls.append(kwargs)

    module.process_user_input = process_user_input
    monkeypatch.setitem(sys.modules, "simulation", module)
    resolved = load_inherited_process_user_input()
    assert resolved is process_user_input
    assert calls == []
