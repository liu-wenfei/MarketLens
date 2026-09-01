"""Deterministic participant-feedback domain primitives."""

from .generation import (
    BoundedValidatedFeedbackGenerator,
    FeedbackGenerationContractError,
    FeedbackGenerationResult,
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
