# MarketLens Phase 14B3B0 — Participant Experiment Orchestration Audit

**Status:** BOUNDED IMPLEMENTATION PATCH
**Evidence class:** NON-FORMAL / ZERO-LLM

## Why this phase exists

The Phase 14B exposure audit found that the minimal human backend did not yet
execute three parts of the already-frozen Phase 10 protocol:

1. `decisions` allows only one record per `(session_id, step)`, while the formal
   protocol requires J0/J1 at the same step/date and J2/J3 at the same step/date;
2. the session had no server-owned within-step stage, so a client could otherwise
   be forced to choose pre/post stimulus timing;
3. session dates were not advanced from the frozen checkpoint timeline by an
   explicit participant-orchestration contract.

The formal Phase 11 material already exists at
`data/marketlens/stimuli/stimulus_v1.formal.json` and matches the frozen Phase 12
controlled-stimulus cue IDs. This patch does not modify that material, source-cue
mapping, or stimulus timing.

## Domain correction

`decisions` remains the one-per-step shadow/ordinary financial decision domain.
Its existing `(session_id, step)` uniqueness is preserved.

A new `participant_judgements` table is the authoritative source of truth for
formal J0..J4 measurements. J0/J1 and J2/J3 may therefore share one
`experiment_step` and `agent_world_date` without weakening decision semantics.

The client submits only response content. `judgement_event`, `experiment_step`,
`agent_world_date`, participant identity, and stage transition are server-derived.

## Server-owned stages

A nullable `sessions.current_stage` is added for formal orchestration. Existing
minimal-backend sessions are not silently converted; formal orchestration must be
initialized explicitly and fails closed if a conflicting date/stage already
exists.

Every initialized checkpoint begins at `BACKGROUND_REQUIRED`. The frozen
judgement/stimulus sequence is represented as:

- step 0: `BACKGROUND_REQUIRED -> J0_REQUIRED -> MISINFORMATION_DELIVERY_REQUIRED -> J1_REQUIRED -> ROUND_ACTIVE`
- step 7: `BACKGROUND_REQUIRED -> J2_REQUIRED -> CORRECTION_DELIVERY_REQUIRED -> J3_REQUIRED -> ROUND_ACTIVE`
- step 14: `BACKGROUND_REQUIRED -> J4_REQUIRED -> ROUND_ACTIVE -> COMPLETED`
- other participant checkpoints: `BACKGROUND_REQUIRED -> ROUND_ACTIVE`

The future exposure layer will call the background/stimulus transitions after
successful server-confirmed participant delivery. The frontend never supplies a
stage or `VisibilityMoment`.

## B3A correction

`JUDGEMENT_SUBMITTED` and `CONFIDENCE_RECORDED` now reference the authoritative
`participant_judgements.judgement_id`, not the ordinary `decisions.decision_id`.
Portfolio event semantics remain unchanged.

## Explicit non-goals

This patch adds no public judgement/stimulus/background router, no automatic
episode allocator, no participant event writes, no formal participant
assignment, no Agent-world/forum mutation, no LLM/network call, and no change to
Phase 10/11/12 frozen content or timing.

Existing round HTTP wiring is intentionally not switched to the new checkpoint
advance in this bounded phase. Phase 14B3C must wire round completion and
orchestration advancement into one authoritative runtime path with recovery
semantics; until then this orchestration contract is exercised only by internal
services/tests/preflight.
