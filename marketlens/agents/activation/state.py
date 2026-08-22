"""Activation-local state for MarketLens Phase 4."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


class ActivationStateError(ValueError):
    """Raised when activation-local state is malformed."""


@dataclass(frozen=True)
class ActivationState:
    """Track only time since each Agent's most recent activation.

    Phase 4 state does not contain beliefs, positions, social-network properties,
    participant responses, market events or news state.
    """

    steps_since_last_activation: Mapping[str, int] = field(default_factory=dict)

    def steps_for(self, user_id: str) -> int:
        value = int(self.steps_since_last_activation.get(str(user_id), 0))
        if value < 0:
            raise ActivationStateError(
                f"negative steps_since_last_activation for Agent {user_id}"
            )
        return value

    def advance(self, active_agent_ids: set[str], all_agent_ids: tuple[str, ...]) -> "ActivationState":
        known = set(all_agent_ids)
        unknown_active = set(active_agent_ids) - known
        if unknown_active:
            raise ActivationStateError(
                f"active_agent_ids contains unknown Agent(s): {sorted(unknown_active)}"
            )

        next_steps = {
            user_id: (0 if user_id in active_agent_ids else self.steps_for(user_id) + 1)
            for user_id in all_agent_ids
        }
        return ActivationState(steps_since_last_activation=next_steps)
