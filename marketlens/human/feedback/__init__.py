"""Deterministic participant-feedback domain primitives."""

from .generation import (
    BoundedValidatedFeedbackGenerator,
    FeedbackGenerationContractError,
    FeedbackGenerationResult,
)
from .formal_policy import (
    FORMAL_CONTEXT_LIMITS,
    FORMAL_FALLBACK_POLICY_VERSION,
    FORMAL_FALLBACK_STATUS,
    FORMAL_FALLBACK_TRIGGER_CATEGORIES,
    FORMAL_LIVE_FEEDBACK_POLICY,
    FORMAL_LIVE_FEEDBACK_POLICY_VERSION,
    FORMAL_MAX_PROVIDER_ATTEMPTS,
    FORMAL_PROVIDER_SUCCESS_STATUS,
    FORMAL_REQUEST_TIMEOUT_SECONDS,
    FORMAL_TOTAL_WAIT_SECONDS,
    formal_context_limits_payload,
    formal_fallback_output,
    formal_fallback_sha256_by_kind,
    formal_live_feedback_policy_payload,
)

from .portfolio_metrics import (
    EquityPoint,
    ExecutedTurnover,
    MaxDrawdown,
    calculate_executed_turnover,
    max_drawdown,
)

from .context import (
    CONTEXT_PACK_VERSION,
    ContextLimits,
    FeedbackContextBuilder,
    FeedbackContextError,
    FeedbackContextPack,
)

from .prompt import (
    PROMPT_CONTRACT_VERSION,
    SYSTEM_PROMPT_V1,
    FeedbackPromptError,
    FrozenFeedbackPrompt,
    build_feedback_prompt,
)
from .output_validation import (
    OUTPUT_CONTRACT_VERSION,
    FeedbackOutputValidationError,
    ValidatedFeedbackOutput,
    validate_feedback_output,
)

from .source import (
    FeedbackKind,
    FeedbackSourceError,
    FeedbackStatisticsSourceAdapter,
    FeedbackWindow,
)

from .statistics import (
    STATISTICS_VERSION,
    AssessmentActionLink,
    FeedbackStatistics,
    JudgementObservation,
    TradeObservation,
    build_feedback_statistics,
)

__all__ = [
    "CONTEXT_PACK_VERSION",
    "OUTPUT_CONTRACT_VERSION",
    "PROMPT_CONTRACT_VERSION",
    "SYSTEM_PROMPT_V1",
    "STATISTICS_VERSION",
    "ContextLimits",
    "BoundedValidatedFeedbackGenerator",
    "FeedbackGenerationContractError",
    "FeedbackGenerationResult",
    "FORMAL_CONTEXT_LIMITS",
    "FORMAL_FALLBACK_POLICY_VERSION",
    "FORMAL_FALLBACK_STATUS",
    "FORMAL_FALLBACK_TRIGGER_CATEGORIES",
    "FORMAL_LIVE_FEEDBACK_POLICY",
    "FORMAL_LIVE_FEEDBACK_POLICY_VERSION",
    "FORMAL_MAX_PROVIDER_ATTEMPTS",
    "FORMAL_PROVIDER_SUCCESS_STATUS",
    "FORMAL_REQUEST_TIMEOUT_SECONDS",
    "FORMAL_TOTAL_WAIT_SECONDS",
    "formal_context_limits_payload",
    "formal_fallback_output",
    "formal_fallback_sha256_by_kind",
    "formal_live_feedback_policy_payload",
    "FeedbackOutputValidationError",
    "FeedbackPromptError",
    "FeedbackContextBuilder",
    "FeedbackContextError",
    "FeedbackContextPack",
    "AssessmentActionLink",
    "EquityPoint",
    "ExecutedTurnover",
    "FeedbackKind",
    "FeedbackSourceError",
    "FeedbackStatistics",
    "FeedbackStatisticsSourceAdapter",
    "FeedbackWindow",
    "FrozenFeedbackPrompt",
    "ValidatedFeedbackOutput",
    "build_feedback_prompt",
    "validate_feedback_output",
    "JudgementObservation",
    "MaxDrawdown",
    "TradeObservation",
    "build_feedback_statistics",
    "calculate_executed_turnover",
    "max_drawdown",
]
