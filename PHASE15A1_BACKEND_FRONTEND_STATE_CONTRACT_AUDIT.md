# MarketLens Phase 15A1 — Backend/frontend state contract

**Status:** BOUNDED IMPLEMENTATION PATCH
**Evidence class:** NON-FORMAL / ZERO-LLM
**Base:** `phase14-participant-runtime-v1.0` (`83878ba`)
**Contract version:** `1.0`

## Purpose

Phase 15A1 adds a read-only participant presentation adapter over the frozen
Phase 14 runtime. It does not reopen Phase 10 timing, Phase 11 controlled
stimulus content/timing, Phase 12 source cues, Phase 13 canonical episodes, or
Phase 14 orchestration transitions.

The frontend must not infer protocol state by probing endpoints for `409`
responses. It receives a neutral, server-derived view contract and a set of
allowed actions.

## Public Phase 15 participant contract

### `GET /session/{session_id}/view`

Returns `ParticipantViewState` with:

- contract version;
- server-owned current-step assertion and 1-based period progress;
- current participant-visible date and experiment status;
- fixed assessment target stock;
- neutral `required_action`;
- neutral assessment mode when an assessment is required;
- market/calendar presentation state;
- server-derived `allowed_actions`.

The response deliberately excludes raw Phase 14 `current_stage`, J0..J4,
episode assignment/provenance, treatment identity and visibility moments.

Neutral action mapping:

| Frozen backend stage | Phase 15 required action | Assessment mode |
| --- | --- | --- |
| `BACKGROUND_REQUIRED` | `LOAD_MARKET_INFORMATION` | null |
| `J0_REQUIRED`, `J2_REQUIRED` | `SUBMIT_ASSESSMENT` | `PRE_UPDATE` |
| `J1_REQUIRED`, `J3_REQUIRED` | `SUBMIT_ASSESSMENT` | `POST_UPDATE` |
| `J4_REQUIRED` | `SUBMIT_ASSESSMENT` | `LATER` |
| misinformation/correction delivery stages | `LOAD_INFORMATION_UPDATE` | null |
| `ROUND_ACTIVE` | `ROUND_ACTIVE` | null |
| `COMPLETED` | `COMPLETED` | null |

`preview_trade` and `submit_trade` are true only when both conditions hold:

1. frozen orchestration is `ROUND_ACTIVE`; and
2. the authoritative market/calendar permits participant trading.

The existing Phase 14 `participant_trading_enabled` market flag alone is not a
frontend authorization signal.

### `POST /session/{session_id}/assessment`

Participant-safe formal assessment submission. The client supplies only:

- `request_id`;
- action;
- confidence;
- evidence source selections;
- optional rationale.

The client cannot supply stock target, J0..J4 identity, experiment step, date,
stage or treatment moment. The formal target stock is derived from the frozen
formal stimulus material and is also enforced inside the runtime judgement
service.

### `POST /session/{session_id}/information-update`

Participant-safe controlled information delivery. The response contains only:

- session/date;
- headline/body;
- frozen participant-facing source label/descriptor.

It does not expose `kind`, `stimulus_id`, `corrects_stimulus_id`, hashes,
material version or other treatment/provenance fields.

## Phase 14 compatibility routes

The Phase 14 routes `/judgement` and `/exposure/stimulus` are retained so the
frozen backend regression remains intact, but they are removed from the public
OpenAPI schema and are not part of the Phase 15 frontend contract.

## Server-owned invariants

The frontend never controls:

- episode assignment or episode identity;
- `agent_world_date` / current date progression;
- experiment-step progression;
- raw orchestration stage;
- J0..J4 identity;
- controlled-stimulus identity/kind/hash/version;
- misinformation/correction visibility moment;
- OPEN/CLOSED authority or canonical price;
- next checkpoint;
- formal assessment target stock.

## Idempotency

Phase 15 presentation routes reuse the Phase 14 idempotent domain services.
Frontend retries must reuse the same request ID for the same intended action.
A lost HTTP response therefore does not create a second background exposure,
information-update exposure, formal assessment or round completion.

## Bounded scope

This patch does **not**:

- change Phase 14 state transitions;
- change judgement timing;
- change stimulus text or source cues;
- change canonical episodes;
- touch TwinMarket Agent-world databases;
- change portfolio settlement or matching;
- add a participant allocator;
- add UI components;
- make LLM/API calls.

## Acceptance gate

Phase 15A1 closes only after all of the following pass:

- dedicated Phase 15A1 tests;
- existing `tests/marketlens/human` regression;
- full MarketLens regression suite;
- zero-LLM preflight;
- `git diff --check`;
- scope review confirming no frozen Agent-world/canonical-episode mutation.

Passing this gate closes the backend/frontend state contract only. It is not
formal participant evidence.
