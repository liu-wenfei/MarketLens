# MarketLens Phase 14A — Participant Event Ledger Audit

## Scope

Phase 14A adds only the participant experimental provenance storage boundary. It does not wire API routes, does not change participant decision/trading behaviour, does not change stimulus timing, and does not read or mutate TwinMarket Agent-world databases.

## Frozen storage decision

The participant experimental event ledger uses a separate database:

`data/marketlens/human/participant_events.db`

All participants share the normalized `participant_events` table. Logical isolation is through `participant_id` and `session_id`; the design deliberately avoids one table or one database per participant.

## Source-of-truth rule

The event ledger is not a second participant backend.

- session state remains authoritative in the existing session store;
- judgement/confidence content remains authoritative in the existing decision store;
- participant orders/trades/holdings remain authoritative in the existing portfolio stores;
- `participant_events.domain_record_id` references those domain identities without duplicating their payload fields.

The ledger records experimental provenance: which participant/session/episode/step/date/event occurred under which market/exposure context.

## Stored fields

The Phase 14A table contains:

- `event_id`
- `request_id`
- `session_id`
- `participant_id`
- `episode_id`
- `experiment_step`
- `agent_world_date`
- `event_type`
- optional `domain_record_id`
- optional controlled-stimulus `stimulus_id`, `stimulus_version`, `stimulus_sha256`
- optional `source_cue`
- `market_open`
- `participant_trading_enabled`
- optional participant-visible `payload_digest`
- `occurred_at_utc`

## Event types

The bounded v1 event vocabulary is:

- `BACKGROUND_EXPOSED`
- `CONTROLLED_STIMULUS_EXPOSED`
- `JUDGEMENT_SUBMITTED`
- `CONFIDENCE_RECORDED`
- `ORDER_SUBMITTED`
- `TRADE_SETTLED`
- `PORTFOLIO_STATE_RECORDED`

No mouse movement, hover, scroll-depth, clickstream, dwell-time, or other new participant-behaviour variable is added.

## Append-only and idempotency

`event_id` is the immutable event identity. Repeated submission of the same `(session_id, request_id, event_type)` with the same payload is idempotent; a changed payload is rejected as a conflict.

SQLite receives update/delete denial triggers so existing participant-event rows cannot be edited or removed through the database after insertion. The public store itself exposes only append/read operations.

## Isolation from Agent world

The Phase 14 database is not stored under a canonical episode directory and contains no Agent-world tables. Phase 14A performs no write to:

- `agent_world.db`
- `forum.db`
- inherited TwinMarket databases
- participant portfolio state

The logger observes; it does not cause.

## Deliberately deferred to Phase 14B

Phase 14A does **not** yet wire logging into API/service actions. Phase 14B must derive trusted context from the backend rather than accepting arbitrary client claims for:

- session/participant identity;
- canonical `episode_id` assignment;
- current `experiment_step`;
- authoritative `agent_world_date`;
- market-open/trading-enabled state;
- frozen stimulus ID/version/hash;
- participant-visible payload digest.

This split keeps persistence verifiable before causal runtime integration.
