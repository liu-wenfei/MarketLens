# MarketLens Phase 14B3B — Participant-visible exposure delivery

**Status:** BOUNDED IMPLEMENTATION PATCH  
**Evidence class:** NON-FORMAL / ZERO-LLM  
**Base:** Phase 14B3B0 server-owned participant experiment orchestration

## Purpose

Phase 14B3B defines an internal delivery boundary for the two exposure events
that cannot be inferred from an already-completed decision or portfolio record:

- `BACKGROUND_EXPOSED`;
- `CONTROLLED_STIMULUS_EXPOSED`.

The delivery service accepts only `session_id` plus an idempotency `request_id`.
Participant/episode/step/date/market state and manipulation timing are derived
from authoritative backend state.

## Background delivery

A first background delivery is authorised only at `BACKGROUND_REQUIRED`.
The service:

1. resolves trusted participant context;
2. projects the canonical participant-visible background for the authoritative date;
3. hashes the exact participant-visible payload;
4. appends `BACKGROUND_EXPOSED` to the separate event ledger;
5. advances the server-owned orchestration stage.

The existing legacy-compatible `GET /session/{session_id}/background` is not
modified in this phase. Public endpoint wiring remains Phase 14B3C work.

## Controlled-stimulus release delivery

The client never supplies a visibility moment. The current server-owned stage
selects exactly one manipulation release:

- `MISINFORMATION_DELIVERY_REQUIRED` -> `POST_MISINFORMATION_RELEASE`;
- `CORRECTION_DELIVERY_REQUIRED` -> `POST_CORRECTION_RELEASE`.

The service explicitly requires `formal_frozen` Phase 11 material and the frozen
Phase 12 source-cue mapping. It uses `StimulusEngine.participant_payload(...)`
to authorise visibility, then returns only the newly released formal item.
Hashes and internal manifest fields are never included in the participant
payload; they are recorded only in provenance.

This phase records the authoritative release exposure. It does not add mouse,
scroll, dwell, attention, or repeated-render telemetry. Persistent visibility at
later checkpoints remains governed by the existing `StimulusEngine` contract and
will be exposed through the final frontend/runtime read path without changing
stimulus timing.

## Cross-database recovery

The participant event ledger and human-domain database are intentionally
separate, so there is no cross-database atomic transaction. The safe ordering is:

`prepare exact payload -> append exposure event -> advance orchestration stage`

If execution stops after the event append but before stage advancement, a retry
first finds the append-only event, verifies the reconstructed payload digest and
trusted context, then completes the missing stage transition. If the stage was
already advanced and the response was lost, the same request replays the same
payload without adding a second event.

## Explicit non-goals

Phase 14B3B does **not**:

- add or modify a public FastAPI route;
- change `main.py` runtime dependency binding;
- perform balanced-random episode allocation;
- change the Phase 10 protocol;
- change Phase 11 formal stimulus text/timing;
- change Phase 12 source-cue wording;
- mutate Agent-world/forum state;
- settle participant trades;
- submit J0..J4 judgements;
- call an LLM or network service.
