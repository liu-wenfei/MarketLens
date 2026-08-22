"""Data contracts for MarketLens Phase 5A inherited reasoning integration.

Phase 5A is deliberately a thin adapter layer.  It records one result per
activated Agent pipeline without interpreting the financial decision itself.
Structured decision measurement belongs to a later phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RUNTIME_ADAPTER_VERSION = "marketlens_twinmarket_reasoning_adapter/1.0"


@dataclass(frozen=True)
class AgentReasoningExecution:
    """Outcome of one inherited TwinMarket Agent-pipeline execution."""

    user_id: str
    completed_successfully: bool
    returned_tuple_shape_ok: bool
    returned_user_id: str | None
    inherited_error: str | None
    decision_result_present: bool
    post_response_args_present: bool
    forum_args: Any = None
    decision_result: Any = None
    post_response_args: Any = None


@dataclass(frozen=True)
class ReasoningBatchExecution:
    """Phase 5A batch result for exactly the Agents activated in one step."""

    adapter_version: str
    step: int
    population_agent_ids: tuple[str, ...]
    active_agent_ids: tuple[str, ...]
    executions: tuple[AgentReasoningExecution, ...]

    @property
    def attempted(self) -> int:
        return len(self.executions)

    @property
    def completed_successfully(self) -> int:
        return sum(1 for execution in self.executions if execution.completed_successfully)

    @property
    def failed(self) -> int:
        return self.attempted - self.completed_successfully
