# Phase 15C3 Formal Feedback Freeze Audit

## Status

**FORMAL RUNTIME FROZEN WITH VALIDATED FALLBACK**

Phase 15C3 freezes the MarketLens live adaptive feedback
runtime at Git commit:

`c4f8f38a56141bb65ff7e061469d0b5dfd1a1647`

This freeze is a runtime-contract freeze. It is **not** a
claim that every provider request will return a compliant
reflection.

## Final frozen identities

- Prompt: `marketlens-feedback-reflection-prompt-v4`
- Output validator: `marketlens-feedback-reflection-output-v3`
- Generator: `marketlens-formal-feedback-generator-v7`
- Corrective retry: `marketlens-formal-feedback-corrective-retry-v2`
- Preflight: `marketlens-formal-feedback-provider-preflight-v11`
- Live feedback policy: `marketlens-formal-live-adaptive-feedback-v1`
- Fallback policy: `marketlens-formal-feedback-fallback-v1`

## Participant feedback basis

At the frozen F1, F2, and Final checkpoints, MarketLens
constructs participant-specific feedback context from recorded
participant behaviour, participant-reported rationale/evidence,
participant-visible information, and deterministic backend
statistics.

The LLM does not independently recalculate authoritative
metrics and does not receive permission to expose experimental
truth, correctness labels, future information, hidden Agent
state, other-participant comparisons, or unsupported inferred
psychological/strategic states.

## Runtime acceptance rule

The frozen runtime permits exactly two participant-safe
generation outcomes:

1. `formal_live_provider_validated`
2. `formal_live_fallback_validated`

Provider output is not participant-facing until it passes the
deterministic MarketLens output validator.

If compliant provider output is not obtained within the bounded
provider-attempt policy, MarketLens delivers the already
validated deterministic fallback instead of exposing rejected
provider text.

Rejected provider text is not reused as corrective-retry input.

## Provider runtime

- Provider: `openai_compatible`
- Requested model: `gpt-5-nano`
- Maximum provider attempts: `2`
- Request timeout: `30.0` seconds
- Total wait budget: `45.0` seconds
- SDK retries: `0`
- Maximum output tokens: `1024`
- Reasoning effort: `minimal`

The API credential is not part of the frozen tracked record.

## Preflight evidence

### V10

V10 was a non-formal paid provider compatibility preflight.

It demonstrated a successful provider-generated reflection
under output contract v2:

- status: `PREFLIGHT_VALIDATED`
- attempt count: `1`
- fallback used: `false`
- participant DB touched: `false`

V10 is preserved as historical provider-path evidence but does
not establish provider success under the final output-v3
semantic validator.

### V11

V11 was executed once against the final output-v3 runtime and
is permanently consumed.

The provider produced two responses:

- attempt 1: rejected for final-reflection word-count violation
- attempt 2: rejected for unsupported psychological,
  attentional, intentional, or strategic attribution

The bounded provider attempts were therefore exhausted.

The runtime then:

- failed closed;
- did not expose rejected provider output;
- resolved to `formal_live_fallback_validated`;
- used fallback trigger `output_validation_exhausted`;
- did not touch the participant DB.

V11 therefore validates the final runtime's fail-closed safety
path and fallback path. It does **not** constitute successful
provider-output validation under output-v3.

V11 must not be rerun. No V12 is created for Phase 15C3.

## Zero-API regression baseline

Final 15C3Q validation before this freeze record:

- targeted human tests: **80 passed**
- full human regression: **374 passed**
- frozen fallback remained valid under output-v3
- V10 legacy semantic leakage was rejected under output-v3
- explicitly participant-reported state language remained allowed

## Methodological interpretation

MarketLens feedback is a constrained adaptive intervention, not
free-form chat.

The generation rules, checkpoints, context boundaries,
validator, retry budget, and fallback policy are fixed. The
participant context varies according to each participant's
recorded behaviour.

The system therefore attempts participant-specific real-time
reflection while maintaining a deterministic safety boundary.

A fallback event remains part of runtime provenance and must
not be represented as successful live provider generation.

## Freeze decision

Phase 15C3 is accepted and frozen on the basis of the complete
runtime contract:

**bounded live generation → deterministic validation →
validated provider output OR validated fallback**

No further prompt, validator, generator, retry-policy, or
provider-preflight version is introduced as part of Phase 15C3.
