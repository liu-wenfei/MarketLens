"""Frozen policy for live adaptive participant feedback.

The model may tailor only the reflection text to the already-recorded,
participant-safe context. Timing, context bounds, validation, provider budget,
fallback content, and persistence semantics are deterministic system policy.
"""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping

from .context import ContextLimits
from .prompt import FrozenFeedbackPrompt


FORMAL_LIVE_FEEDBACK_POLICY_VERSION = (
    "marketlens-formal-live-adaptive-feedback-v2"
)
FORMAL_CONTEXT_LIMITS = ContextLimits(
    policy_version="marketlens-formal-feedback-context-limits-v1",
    max_news_items=70,
    max_community_posts=200,
    max_news_chars=2000,
    max_community_chars=1000,
    max_rationale_chars=2000,
    max_evidence_sources=12,
    max_evidence_source_chars=300,
    max_controlled_headline_chars=500,
    max_controlled_body_chars=5000,
    max_source_label_chars=200,
    max_source_descriptor_chars=500,
)

FORMAL_REQUEST_TIMEOUT_SECONDS = 30.0
FORMAL_TOTAL_WAIT_SECONDS = 45.0
FORMAL_MAX_PROVIDER_ATTEMPTS = 2

FORMAL_PROVIDER_SUCCESS_STATUS = "formal_live_provider_validated"
FORMAL_FALLBACK_STATUS = "formal_live_fallback_validated"
FORMAL_FALLBACK_POLICY_VERSION = "marketlens-formal-feedback-fallback-v2"

_MID_FALLBACK = (
    "Across this feedback window, the recorded assessments, confidence "
    "reports, rationales, evidence selections, and portfolio behaviour form "
    "separate parts of the decision record. The reflection can describe "
    "where the stated market view remained stable or changed, and whether "
    "confidence and portfolio behaviour changed together or separately. "
    "Information shown in the interface is treated as available context "
    "only; the record does not establish that every item was read, relied "
    "upon, or believed. References to evidence therefore remain limited to "
    "sources explicitly selected and reasons recorded at the time. Trading "
    "and choosing not to trade are both retained as behaviour, without "
    "treating either as a better response. This feedback makes patterns in "
    "the recorded process easier to inspect while leaving accuracy "
    "judgements, hidden conditions, later outcomes, and investment "
    "recommendations outside the reflection."
)

_FINAL_FALLBACK = (
    "Across the full session, the recorded assessments form a developing "
    "decision journey rather than a set of isolated answers. The record can "
    "show continuity in the stated market view, revision at particular "
    "points, or a mixture of stability and change as the visible information "
    "environment developed. The rationales and evidence selections captured "
    "at the time provide the only basis for describing information that was "
    "explicitly reported as part of the decision process. Material displayed "
    "in the interface remains available context only and does not establish "
    "that every item was read, relied upon, or believed.\n\n"
    "Confidence reports and portfolio behaviour provide a separate view of "
    "the same journey. A change in assessment may appear with or without a "
    "change in confidence, and it may appear with a trade or with a decision "
    "not to trade. Those relationships are descriptive. They do not establish "
    "the quality of a judgement or make one type of portfolio behaviour "
    "preferable to another. Portfolio values and transaction records are "
    "likewise retained as descriptions of participant behaviour within the "
    "simulated environment, not as measures of decision accuracy.\n\n"
    "Taken together, these records support a process-level review of where "
    "views stayed stable, where they changed, how confidence developed, how "
    "portfolio behaviour related to stated judgement, and which reasons or "
    "sources were explicitly reported. The reflection does not infer hidden "
    "attention, belief, causality, or experimental conditions from those "
    "records. It also leaves scoring, comparison with other people, later "
    "market information, and investment recommendations outside the "
    "feedback. Its role is limited to presenting the recorded decision "
    "process in a coherent form while preserving the distinction between "
    "information availability, participant-reported evidence, judgement, "
    "confidence, and portfolio behaviour."
)

FORMAL_FALLBACK_TRIGGER_CATEGORIES = frozenset(
    {
        "total_wait_budget_exhausted",
        "transient_provider_failure_exhausted",
        "nonretryable_provider_failure",
        "incomplete_provider_response_exhausted",
        "empty_provider_output_exhausted",
        "output_validation_exhausted",
    }
)

FORMAL_LIVE_FEEDBACK_POLICY: Mapping[str, object] = MappingProxyType(
    {
        "policy_version": FORMAL_LIVE_FEEDBACK_POLICY_VERSION,
        "tailoring_variables": (
            "participant-safe recorded assessments",
            "participant-reported confidence",
            "participant-authored rationale",
            "participant-selected evidence",
            "participant trades and no-trade records",
            "participant-visible information available by the checkpoint",
        ),
        "allowed_personalisation": (
            "selection of context-supported process patterns",
            "neutral wording and ordering of those patterns",
            "longitudinal comparison within the frozen feedback window",
        ),
        "locked_across_participants": (
            "feedback checkpoints and windows",
            "participant-safe context schema and limits",
            "system and user prompt contract",
            "provider model and request parameters",
            "reflection-only output schema and word bounds",
            "deterministic validator and prohibited-language rules",
            "provider attempt and total-wait budgets",
            "fallback triggers and fallback text by feedback kind",
            "one-time generation claim and immutable persistence",
        ),
        "intervention_options": (
            FORMAL_PROVIDER_SUCCESS_STATUS,
            FORMAL_FALLBACK_STATUS,
        ),
        "fixed_decision_points": ("F1", "F2", "FINAL"),
        "provider_attempts": FORMAL_MAX_PROVIDER_ATTEMPTS,
        "request_timeout_seconds": FORMAL_REQUEST_TIMEOUT_SECONDS,
        "total_wait_seconds": FORMAL_TOTAL_WAIT_SECONDS,
        "fallback_policy_version": FORMAL_FALLBACK_POLICY_VERSION,
        "fallback_triggers": tuple(sorted(FORMAL_FALLBACK_TRIGGER_CATEGORIES)),
        "fallback_for_context_or_invariant_failure": False,
        "unvalidated_output_exposed": False,
    }
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_json(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def formal_context_limits_payload() -> dict[str, object]:
    return asdict(FORMAL_CONTEXT_LIMITS)


def formal_live_feedback_policy_payload() -> dict[str, object]:
    return dict(FORMAL_LIVE_FEEDBACK_POLICY)


def formal_fallback_output(prompt: FrozenFeedbackPrompt) -> dict[str, str]:
    if prompt.feedback_kind == "multi_period_decision_feedback":
        reflection = _MID_FALLBACK
    elif prompt.feedback_kind == "final_session_summary":
        reflection = _FINAL_FALLBACK
    else:
        raise ValueError("unsupported feedback kind for formal fallback")
    return {
        "feedback_kind": prompt.feedback_kind,
        "reflection": reflection,
    }


def formal_fallback_sha256_by_kind() -> dict[str, str]:
    result: dict[str, str] = {}
    for kind in (
        "multi_period_decision_feedback",
        "final_session_summary",
    ):
        prompt = FrozenFeedbackPrompt(
            prompt_contract_version="hash-only",
            context_pack_version="hash-only",
            context_policy_version="hash-only",
            context_sha256="0" * 64,
            feedback_kind=kind,
            system_prompt="hash-only",
            user_prompt="hash-only",
        )
        result[kind] = sha256_json(formal_fallback_output(prompt))
    return result
