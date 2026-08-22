"""Sparse heterogeneous activation policy for MarketLens Phase 4.

Lineage
-------
TwinMarket already performs an independent stochastic activation draw for each
Agent, but every Agent shares one global ``activate_prob``.  The uploaded newer
TwinMarket work explored a heterogeneous log-odds policy.  MarketLens Phase 4
keeps those two useful ideas while deliberately narrowing the feature set to
stable historical activity plus activation-local recency.

No market/news/social/LLM/participant feature is used here.  Those belong to
later phases and can be added as contextual modifiers without changing the
baseline activation contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping


ACTIVATION_POLICY_VERSION = "marketlens_sparse_heterogeneous_activation/1.0"

# Engineering defaults derived from the inherited 1,000-Agent source database.
# In the audited source, median TradingDetails counts were 16 / 36 / 80 for
# trade_count_category 低 / 中 / 高, with category counts 332 / 371 / 297.
# Scaling those medians to a population-weighted mean baseline of 0.20 gives the
# probabilities below.  These are development parameters, not formal study
# parameters; the dataclass keeps them explicit and overrideable.
DEFAULT_ACTIVITY_BASELINES = {
    "低": 0.07542189120392195,
    "中": 0.16969925520882437,
    "高": 0.37710945601960977,
}

DEFAULT_BASELINE_PROVENANCE = {
    "source_population_agents": 1000,
    "source_category_counts": {"低": 332, "中": 371, "高": 297},
    "median_observed_trades": {"低": 16.0, "中": 36.0, "高": 80.0},
    "target_population_weighted_mean": 0.20,
    "interpretation": (
        "trade_count_category is used only as a historical activity propensity; "
        "it is not a correctness, credibility, strategy or source-status signal"
    ),
}

FORBIDDEN_ACTIVATION_FEATURES = frozenset(
    {
        "user_type",
        "is_top_user",
        "top_user",
        "source_status",
        "strategy",
        "profit",
        "return_rate",
        "participant_action",
        "participant_decision",
        "news_event",
        "price_move",
        "social_signal",
    }
)


class ActivationPolicyError(ValueError):
    """Raised when an activation policy configuration is invalid."""


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _logit(probability: float) -> float:
    p = min(max(float(probability), 1e-12), 1.0 - 1e-12)
    return math.log(p / (1.0 - p))


@dataclass(frozen=True)
class ActivationConfig:
    """Explicit Phase 4 engineering parameters.

    ``recency_weight`` operates in log-odds space.  Recency is the only dynamic
    modifier in Phase 4 and depends solely on prior activation outcomes.
    """

    activity_baselines: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_ACTIVITY_BASELINES)
    )
    p_min: float = 0.02
    p_max: float = 0.60
    recency_weight: float = 0.40
    recency_reference_steps: int = 5
    policy_version: str = ACTIVATION_POLICY_VERSION

    def __post_init__(self) -> None:
        required = {"低", "中", "高"}
        if set(self.activity_baselines) != required:
            raise ActivationPolicyError(
                "activity_baselines must define exactly the inherited categories 低/中/高"
            )
        if not 0.0 < self.p_min < self.p_max < 1.0:
            raise ActivationPolicyError("require 0 < p_min < p_max < 1")
        if self.recency_weight < 0.0:
            raise ActivationPolicyError("recency_weight must be non-negative")
        if self.recency_reference_steps <= 0:
            raise ActivationPolicyError("recency_reference_steps must be positive")
        for category, probability in self.activity_baselines.items():
            p = float(probability)
            if not 0.0 < p < 1.0:
                raise ActivationPolicyError(
                    f"baseline probability for {category!r} must lie in (0, 1)"
                )


@dataclass(frozen=True)
class ActivationPropensity:
    activity_category: str
    p_base: float
    steps_since_last_activation: int
    recency_feature: float
    recency_weight: float
    logit_score: float
    p_active: float


class ActivationPolicy:
    """Compute an Agent-specific activation probability without running an Agent."""

    def __init__(self, config: ActivationConfig | None = None):
        self.config = config or ActivationConfig()

    def base_probability(self, activity_category: str) -> float:
        try:
            return float(self.config.activity_baselines[str(activity_category)])
        except KeyError as exc:
            raise ActivationPolicyError(
                f"unsupported activity category {activity_category!r}"
            ) from exc

    def propensity(
        self,
        *,
        activity_category: str,
        steps_since_last_activation: int,
    ) -> ActivationPropensity:
        if steps_since_last_activation < 0:
            raise ActivationPolicyError("steps_since_last_activation must be non-negative")

        p_base = self.base_probability(activity_category)
        recency_feature = min(
            float(steps_since_last_activation) / self.config.recency_reference_steps,
            1.0,
        )
        score = _logit(p_base) + self.config.recency_weight * recency_feature
        p_active = min(max(_sigmoid(score), self.config.p_min), self.config.p_max)

        return ActivationPropensity(
            activity_category=str(activity_category),
            p_base=p_base,
            steps_since_last_activation=int(steps_since_last_activation),
            recency_feature=recency_feature,
            recency_weight=self.config.recency_weight,
            logit_score=score,
            p_active=p_active,
        )
