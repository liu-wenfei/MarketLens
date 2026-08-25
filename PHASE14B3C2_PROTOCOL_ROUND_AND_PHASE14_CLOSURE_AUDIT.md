# MarketLens Phase 14B3C2 — Protocol-driven round completion and Phase 14 closure

**Status:** BOUNDED IMPLEMENTATION PATCH
**Evidence class:** NON-FORMAL / ZERO-LLM
**Base:** `ee60919`

## Purpose

B3C2 replaces the participant-runtime round-completion bypass with one
protocol-driven human-database transaction. It does not alter the inherited
TwinMarket Agent world, the frozen Phase 10 timeline, formal Phase 11 stimulus,
or Phase 12 source cues.

## Runtime round contract

The participant still submits only the existing round request identity and the
current step assertion. Date, next checkpoint and stage are server-derived.
`RoundComplete` forbids extra client fields.

For participant runtime:

```text
ROUND_ACTIVE
    -> validate frozen checkpoint
    -> insert round_completions row
    -> update session step/date/stage
```

The completion row and session transition use the same `Database.connect()`
transaction. A failure rolls both back.

The legacy `RoundService` remains unchanged for runtime-disabled development
apps.

## Terminal checkpoint

The frozen participant protocol ends at experiment step 14. There is no formal
step 15. `round_completions.next_step` is therefore nullable in B3C2:

- non-terminal completion: `next_step > step`;
- terminal completion: `next_step = NULL`;
- the authoritative session remains at step 14/date 2023-07-11 and transitions
  to `COMPLETED`.

Migration `0004_protocol_round_completion` updates the existing table without
inventing a terminal checkpoint.

## Replay semantics

The same `(session_id, request_id)` is resolved before reading the current
session state. Therefore a lost HTTP response can be retried after the first
request has already advanced to the next checkpoint. It returns the original
completion row and does not advance twice.

A different request for an already-completed step is rejected.

## Phase 14 closure target

The final non-formal preflight traverses all 15 participant checkpoints and
verifies:

- 15 protocol-derived round completions;
- 15 background exposures;
- exactly two controlled-stimulus releases;
- exactly J0..J4 formal judgements;
- J0/J1 share step/date and J2/J3 share step/date;
- J4 is later;
- terminal `next_step` is null;
- final session is completed at step 14;
- replay does not duplicate checkpoint advancement;
- no client-supplied date/stage/moment is accepted;
- no random allocator, LLM call, Agent-world write or forum write occurs.

Passing this gate closes Phase 14 engineering. It is not formal participant
evidence.
