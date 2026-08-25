# MarketLens Phase 14B3C1 — Safe participant runtime wiring

**Status:** BOUNDED IMPLEMENTATION PATCH
**Evidence class:** NON-FORMAL / ZERO-LLM
**Base:** `e4ee3bd`

## Purpose

Phase 14B3C1 wires the already-tested Phase 14 services into FastAPI without
reopening the frozen Agent world or replacing the legacy round-completion path
yet.

This patch intentionally does **not** complete Phase 14B3C. Protocol-driven
round completion and final end-to-end recovery remain Phase 14B3C2.

## Runtime boundary

Participant runtime is opt-in at `create_app(...)`.

Runtime mode requires explicit injection of:

- a separate `ParticipantEventStore`;
- an episode-keyed mapping of participant background projections;
- a `formal_frozen` `StimulusEngine`.

The default application path remains legacy/non-formal and does not create or
write `data/marketlens/human/participant_events.db` implicitly.

## Episode-aware background invariant

A participant session is first resolved to its authoritative B1 episode
assignment. Background projection is then selected only from the projection
whose key and embedded canonical binding both match that exact `episode_id`.

Therefore:

```text
session assignment episode_id
=
participant background projection episode_id
```

A missing or mismatched projection fails closed.

## Public exposure endpoints

Runtime mode adds:

```text
POST /session/{session_id}/exposure/background
POST /session/{session_id}/exposure/stimulus
```

Both accept only an idempotency `request_id`.

Client-supplied episode/date/step/stage/moment/stimulus provenance is rejected by
Pydantic `extra="forbid"` request models.

The old GET background route is blocked while participant runtime is enabled so
formal exposure cannot bypass the append-only provenance ledger.

## Formal judgement endpoint

Runtime mode adds:

```text
POST /session/{session_id}/judgement
```

The authoritative `JudgementService` writes J0..J4 first. The runtime recorder
then appends:

- `JUDGEMENT_SUBMITTED`;
- `CONFIDENCE_RECORDED`.

If the event write fails after the domain row commits, an idempotent retry
replays the existing judgement and can repair the missing ledger event.

The legacy `/decision` write path is blocked while participant runtime is
enabled so it cannot become an unlogged substitute for formal J0..J4.

## Portfolio runtime wiring

Participant portfolio GET remains available.

Preview/order are permitted in participant runtime only after the
server-owned orchestration state reaches `ROUND_ACTIVE`.

A successful authoritative participant transaction is followed by:

- `ORDER_SUBMITTED`;
- `TRADE_SETTLED`;
- `PORTFOLIO_STATE_RECORDED`.

The participant transaction remains the domain source of truth. The event ledger
contains provenance references only.

## Session initialization

In participant runtime mode, `POST /session` initializes the server-owned Phase
14B3B0 orchestration state idempotently:

```text
experiment_step = 0
agent_world_date = 2023-06-19
current_stage = BACKGROUND_REQUIRED
```

No episode is randomly allocated here.

## Explicitly out of scope

B3C1 does not:

- modify `RoundStore` or `RoundService`;
- replace `/round/complete` with the final protocol-driven implementation;
- allocate canonical episodes;
- modify Phase 10 protocol;
- modify Phase 11 formal stimulus;
- modify Phase 12 source cues;
- write Agent/forum state;
- invoke an LLM.

While participant runtime is enabled, the legacy `/round/complete` path is
blocked so it cannot execute the old `current_step + 1` mutation. Its
protocol-driven replacement is the bounded B3C2 task.

## Validation target

The B3C1 targeted test/preflight must prove:

- default app remains runtime-disabled;
- runtime session initialization is protocol-derived;
- background delivery is episode-aware;
- legacy background and decision bypasses are blocked in runtime mode;
- forged provenance fields are rejected;
- J0 retry remains idempotent after stage advancement;
- controlled misinformation release is server-owned;
- trading is rejected before `ROUND_ACTIVE`;
- successful portfolio retry does not duplicate the domain mutation or ledger;
- no random allocation, LLM call, Agent write, or forum write occurs.
