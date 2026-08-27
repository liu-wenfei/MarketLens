# Phase 15A2.0 — Server-Owned Participant Bootstrap and Episode Allocation

**Status:** BOUNDED IMPLEMENTATION PATCH
**Evidence class:** NON-FORMAL / ZERO-LLM
**Base:** Phase 15A1 backend/frontend state contract

## Scope

This patch closes the participant-session bootstrap gap found after Phase 15A1.
It does not build the participant UI, alter the frozen Phase 14 orchestration
state machine, generate Agent worlds, rerun canonical episodes, or call an LLM.

## Frozen assignment policy

Phase 13C requires `balanced_random_across_episode_pool`: assignment must be as
balanced as the final sample permits and must not depend on episode outcomes.
The server therefore allocates only among the currently least-used frozen
episodes. If more than one episode is tied for the minimum count, the default
server chooser uses `SystemRandom.choice` across that minimum-count set.

The persisted formal metadata is:

- `assignment_method = balanced_random_across_episode_pool`
- `assignment_version = phase15a2-balanced-random-v1`

No participant-facing request accepts `episode_id`, pool identity, assignment
method/version, seed, experiment step, date, or stage.

## Transaction boundary

The count -> minimum-set -> random tie-break -> insert unit is serialized inside
one database transaction.

- SQLite: a no-op write to the authoritative session row acquires SQLite's
  single-writer reservation before assignment counts are read.
- PostgreSQL: the assignment table is locked in `SHARE ROW EXCLUSIVE` mode
  before the count/choose/insert unit.
- Other dialects fail closed for formal balanced allocation.

This preserves `max(episode assignment counts) - min(...) <= 1` under concurrent
formal bootstrap requests on supported databases.

## Participant bootstrap API

The Phase 15 participant-facing creation route is:

`POST /participant-session`

Payload:

```json
{
  "participant_id": "...",
  "request_id": "..."
}
```

The schema rejects extra fields. The server performs:

1. idempotent session/account creation;
2. server-owned balanced episode allocation;
3. idempotent protocol orchestration initialization;
4. participant-safe `SessionRead` response.

The response does not expose assignment identity. The browser then uses the
Phase 15A1 `GET /session/{session_id}/view` contract.

The legacy/dev `POST /session` route remains callable so frozen Phase 14/15A1
tests and non-formal wiring do not change, but it is removed from OpenAPI to
prevent participant clients from treating it as the Phase 15 bootstrap route.

## Retry semantics

A retry with the same participant and session request ID resolves the existing
session. The allocator returns the already-persisted exact formal binding and
orchestration initialization remains idempotent. A retry never re-randomizes the
session.

## Complete-pool gate

`POST /participant-session` fails closed unless the participant runtime contains
all three frozen canonical episode IDs. Partial projection fixtures remain
usable by older tests through legacy routes but are not a formal bootstrap
configuration.

## Deliberately deferred from this patch

A production formal-runtime launcher is not added here because the audited
repository contains the formal `ParticipantBackgroundProjection` contract but
no production loader or frozen per-episode `FrozenTextPack` asset contract.
Inventing participant text assets or a path convention in this bootstrap patch
would violate the audit-first workflow. The launcher remains the next bounded
Phase 15A2 task after those existing local assets are located/frozen.

Browser JavaScript/runtime integration and same-origin static serving also
remain outside Phase 15A2.0.
