"""Order-independent seeded Bernoulli sampling for Phase 4 activation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable

from .policy import ActivationPolicy, ActivationPropensity
from .profiles import AgentActivationProfile
from .state import ActivationState


ACTIVATION_DRAW_ALGORITHM = "sha256_agent_step_uniform_bernoulli/1.0"


class ActivationSamplingError(ValueError):
    """Raised for an invalid activation sampling request."""


@dataclass(frozen=True)
class AgentActivationResult:
    user_id: str
    activity_category: str
    propensity: ActivationPropensity
    random_draw: float
    is_active: bool


@dataclass(frozen=True)
class ActivationBatch:
    step: int
    seed: str
    draw_algorithm: str
    policy_version: str
    results: tuple[AgentActivationResult, ...]
    active_agent_ids: tuple[str, ...]
    next_state: ActivationState


def _uniform_draw(*, seed: str, step: int, user_id: str) -> float:
    """Return a stable U[0,1) variate keyed by seed, step and Agent identity.

    Hash-keyed draws make results reproducible and independent of iteration order.
    Changing population size therefore does not silently reassign random draws to
    existing Agents at the same seed/step.
    """

    payload = f"{seed}|{step}|{user_id}".encode("utf-8")
    raw = hashlib.sha256(payload).digest()[:8]
    integer = int.from_bytes(raw, byteorder="big", signed=False)
    return integer / float(1 << 64)


def sample_activation(
    profiles: Iterable[AgentActivationProfile],
    *,
    policy: ActivationPolicy,
    state: ActivationState | None,
    seed: str,
    step: int,
) -> ActivationBatch:
    """Sample the sparse active subset for one simulation step.

    This function performs no LLM inference and imports no inherited TwinMarket
    execution module.  The returned ``active_agent_ids`` are the gate that Phase 5
    will connect to the inherited reasoning pipeline.
    """

    if not str(seed):
        raise ActivationSamplingError("seed must be a non-empty string")
    if step < 0:
        raise ActivationSamplingError("step must be non-negative")

    ordered = tuple(sorted(profiles, key=lambda profile: profile.user_id))
    if not ordered:
        raise ActivationSamplingError("profiles must not be empty")
    ids = tuple(profile.user_id for profile in ordered)
    if len(set(ids)) != len(ids):
        raise ActivationSamplingError("profiles contains duplicate Agent user_id values")

    current_state = state or ActivationState()
    results: list[AgentActivationResult] = []
    active: set[str] = set()

    for profile in ordered:
        propensity = policy.propensity(
            activity_category=profile.activity_category,
            steps_since_last_activation=current_state.steps_for(profile.user_id),
        )
        draw = _uniform_draw(seed=str(seed), step=step, user_id=profile.user_id)
        is_active = bool(draw < propensity.p_active)
        if is_active:
            active.add(profile.user_id)
        results.append(
            AgentActivationResult(
                user_id=profile.user_id,
                activity_category=profile.activity_category,
                propensity=propensity,
                random_draw=draw,
                is_active=is_active,
            )
        )

    active_ids = tuple(sorted(active))
    next_state = current_state.advance(active, ids)
    return ActivationBatch(
        step=step,
        seed=str(seed),
        draw_algorithm=ACTIVATION_DRAW_ALGORITHM,
        policy_version=policy.config.policy_version,
        results=tuple(results),
        active_agent_ids=active_ids,
        next_state=next_state,
    )
