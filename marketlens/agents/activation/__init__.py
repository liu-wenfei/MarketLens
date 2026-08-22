"""MarketLens sparse heterogeneous Agent activation (Phase 4)."""

from .policy import (
    ACTIVATION_POLICY_VERSION,
    DEFAULT_ACTIVITY_BASELINES,
    DEFAULT_BASELINE_PROVENANCE,
    ActivationConfig,
    ActivationPolicy,
    ActivationPolicyError,
    ActivationPropensity,
)
from .profiles import AgentActivationProfile, ActivationProfileError, load_activation_profiles
from .sampler import (
    ACTIVATION_DRAW_ALGORITHM,
    ActivationBatch,
    ActivationSamplingError,
    AgentActivationResult,
    sample_activation,
)
from .state import ActivationState, ActivationStateError

__all__ = [
    "ACTIVATION_POLICY_VERSION",
    "ACTIVATION_DRAW_ALGORITHM",
    "DEFAULT_ACTIVITY_BASELINES",
    "DEFAULT_BASELINE_PROVENANCE",
    "ActivationConfig",
    "ActivationPolicy",
    "ActivationPolicyError",
    "ActivationPropensity",
    "AgentActivationProfile",
    "ActivationProfileError",
    "load_activation_profiles",
    "ActivationBatch",
    "ActivationSamplingError",
    "AgentActivationResult",
    "sample_activation",
    "ActivationState",
    "ActivationStateError",
]
