# MarketLens Phase 14B2 — Trusted Participant Context Resolver

**Status:** BOUNDED IMPLEMENTATION PATCH
**Evidence class:** NON-FORMAL / ZERO-LLM
**Base:** Phase 14B1 participant episode assignment binding

## Purpose

Phase 14B2 creates one read-only backend resolver for the provenance fields that
Phase 14B3 will later write to the append-only participant event ledger.

The resolver accepts only `session_id`. It derives the following from existing
authoritative MarketLens components:

- `participant_id` from the human session domain;
- `episode_pool_id`, `episode_id` and assignment metadata from the Phase 14B1
  participant episode assignment source of truth;
- `experiment_step` from the current session;
- `agent_world_date` from the current session and cross-checks it against the
  frozen Phase 10 protocol checkpoint;
- market-open and participant-trading state from the authoritative TwinMarket /
  MarketLens trading calendar.

## Fail-closed invariants

Resolution fails if:

- the session has no episode assignment;
- the session has no current Agent-world date;
- the current session step is not a participant checkpoint;
- session date and frozen protocol checkpoint date disagree;
- assignment participant/session identity disagrees with the human session;
- assignment pool/episode identity is outside the frozen Phase 13C contract;
- trading-calendar OPEN/CLOSED state disagrees with the frozen protocol.

## Explicit non-goals

Phase 14B2 does **not**:

- add a public context/provenance override API;
- accept participant/episode/date/step/market status from the frontend;
- perform balanced random allocation;
- write `participant_events.db`;
- write Agent-world or forum databases;
- mutate participant session or portfolio state;
- wire stimulus exposure events;
- modify stimulus timing or the frozen Phase 10 protocol;
- call an LLM.

## Dependency boundary

The resolver is constructed explicitly from:

- `SessionService`;
- `EpisodeAssignmentService`;
- `TradingCalendar`;
- validated frozen protocol data.

It is intentionally not added to `app.state` in B2. Runtime dependency wiring is
left to Phase 14B3 so this phase remains a small, independently testable contract.

## Core rule

> Experimental provenance is server-derived, not client-asserted.
