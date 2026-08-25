# MarketLens Phase 14B1 — Participant Episode Assignment Binding

**Status:** BOUNDED PERSISTENCE CONTRACT

## Purpose

Persist the authoritative relationship between a human participant session and one frozen canonical episode so later Phase 14 provenance events can obtain `episode_id` from the backend rather than from the frontend.

## Frozen design

- `participant_episode_assignments` lives in the existing MarketLens human-domain database.
- `participant_events.db` remains an append-only provenance ledger and is not the assignment source of truth.
- One session may have exactly one canonical episode assignment.
- `participant_id` is derived from the existing `sessions` row; callers do not supply participant identity.
- Pool identity and valid episode identities are reused from `marketlens.episode.contract` (`EPISODE_POOL_ID`, `EPISODE_IDS`).
- The persistence layer does not choose an episode.
- No random allocator is implemented in Phase 14B1.
- No public participant assignment endpoint is added.
- No formal participant assignment is executed before the three-episode pool is finalized.
- No Agent-world, forum, stimulus, trading, or participant-portfolio state is mutated by assignment binding.

## Idempotency

Rebinding the same session to the exact same semantic assignment returns the existing row. Rebinding the session to a different episode, pool/method/version is rejected.

## Methodological boundary

Phase 13C freezes the policy name `balanced_random_across_episode_pool`, but Phase 14B1 does not invent the exact randomization algorithm, seed, block construction, or participant enrolment procedure. Those remain separate formal-experiment allocation details and must not be hidden inside a persistence patch.
