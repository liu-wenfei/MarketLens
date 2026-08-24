# Phase 13C — Canonical Episode Freeze Audit and Predeclared Execution Contract

## Scope

Phase 13C freezes the **plan and acceptance contract** for the single formal
canonical TwinMarket Agent-world episode. It does **not** execute the paid LLM
backend, generate formal Agent content, create the final canonical DB pair, or
translate participant-facing text.

The Phase 10 v1.1 protocol already requires a canonical world that is generated
once before participant exposure, shared across participants, immutable during
formal collection, and observed only after each Agent-world state is completed.
Phase 13C turns that methodological requirement into a hash-pinned execution
plan before any full-horizon paid run is attempted.

## Reuse audit

The formal episode producer must reuse the already validated paths rather than
implement a new market simulator:

- Phase 3 population selector / bounded fixture builder for the exact N30
  membership;
- Phase 4 sparse heterogeneous activation with state carry-forward;
- Phase 9 contiguous calendar-day orchestration;
- Phase 6 bounded graph/prominence recomputation;
- inherited `simulation.process_user_input(...)` for each active Agent;
- Phase 7 wrappers around inherited OPEN matching / price formation / Agent
  portfolio update and CLOSED-day Profiles propagation;
- inherited ForumDB post, belief, reaction, and score-update functions;
- Phase 7 natural-news loader and protected `trading_days.csv` calendar.

No participant decision, controlled misinformation, or authoritative correction
enters the Agent world.

## Why the Phase 10 real-backend runner is not the formal producer

The Phase 10 N30 validation runner is intentionally a feasibility harness. It
creates `runtime.db` and `forum.db` inside a Python `TemporaryDirectory` and the
PASS path deletes that workspace unconditionally in `finally`. It preserves a
workspace only for a non-PASS debug run when explicitly requested.

Therefore a formal canonical episode must **reuse the execution pipeline but not
reuse the feasibility workspace lifecycle**. A successful formal producer must
write to a dedicated formal staging location, validate the complete 27-tick
state chain, then seal and hash-pin the final DB pair.

## Frozen formal episode identity

```text
episode_id = marketlens-canonical-episode-v1
protocol_version = 1.1
population = N30
population seed = marketlens-dev-population-01
N30 membership SHA256 =
60d846b21c15e2213f6f897a17a7ea98039fbf461abe54ee89e1b6779d24b2d4
activation seed = marketlens-phase09b-activation-01
T_init = 2023-06-15
T_visible = 2023-06-19
T_end = 2023-07-11
world ticks = 27 calendar days
OPEN = 17
CLOSED = 10
```

The same activation seed was established before the long-horizon formal run and
was already used by the once-only N30 real-backend feasibility validation. It is
not selected from the 100 adequacy-analysis seeds based on outcomes.

The frozen 27-day reference plan contains **193 inherited Agent pipeline
executions**. Its first three active counts remain `10 / 7 / 3`, matching the
completed OPEN / OPEN / CLOSED N30 real-backend validation.

## Formal asset layout

After a valid formal run and freeze, the participant-facing source of truth is:

```text
data/marketlens/canonical_episode/v1/agent_world.db
data/marketlens/canonical_episode/v1/forum.db
data/marketlens/canonical_episode/v1/episode_manifest.json
```

The final `agent_world.db` is the continuous N30 working runtime after the full
27-tick horizon. It contains the daily Profiles/StockData history needed by the
participant shadow portfolio and source-cue lookup. The final `forum.db` retains
cumulative Agent social history. Phase 13B binds these files read-only and
verifies their exact SHA-256 values.

Raw execution evidence (conversation records, day-level decision/post/reaction
records, daily metrics, and attempt logs) belongs under:

```text
artifacts/formal/canonical_episode/marketlens-canonical-episode-v1/
```

Raw evidence is not a second market state and must not be used as a substitute
for the frozen DB pair.

## Predeclared acceptance gates

A completed formal episode is technically eligible for freeze only if:

- all 27 contiguous calendar ticks complete;
- every active Agent pipeline in the predeclared activation plan completes;
- the exact active-Agent plan and OPEN/CLOSED market actions match the frozen
  plan;
- the working Agent-world and forum state remains continuous across days;
- protected source assets remain unchanged;
- participant data is absent;
- controlled misinformation/correction is absent from the Agent world;
- no custom matching, price formation, Agent portfolio, TradingDetails,
  forum, or belief logic is introduced;
- exact-date participant price coverage is complete for the frozen participant
  decision dates;
- every participant-visible forum author/date can resolve its inherited profile
  snapshot for the Phase 12 source cue;
- the final Agent-world and forum DBs are hash-pinned in the formal manifest.

## Outcome-blind acceptance / rerun policy

Formal acceptance deliberately has **no** gate on:

- number of posts;
- number of trades or matched trades;
- price direction or volatility;
- sentiment or tone;
- whether a desired misinformation/correction effect appears.

Those are natural episode outcomes, not reasons to choose another world.

No seed substitution, seed fishing, or partial-resume path is permitted. A
technically invalid attempt (for example transport/API failure, Agent pipeline
failure, database corruption, protected-input drift, or state-chain violation)
may be restarted **from the same frozen initial state with the same plan** only
after the failed attempt evidence is retained. A code or contract change requires
a new execution-plan version before another formal attempt.

A valid completed episode is generated once and then shared unchanged across all
participants; it must not be rerun because its natural content or market path is
unattractive.

## Translation ordering

No formal Agent/forum translation pack may be produced before the canonical
episode is frozen. The required ordering is:

```text
freeze execution plan
→ generate one valid canonical 27-tick Agent world
→ freeze agent_world.db + forum.db + episode manifest
→ derive participant source-text inventory
→ review/freeze English text pack
→ bind Phase 13B formal participant projection
```

This preserves the Phase 13B rule that participant English is a deterministic,
hash-pinned projection of a single already-frozen source world, never a live
translation process.

## Current status

Phase 13C is a **zero-LLM contract only**. No canonical formal episode assets are
created by this patch, and formal participant background projection must remain
fail-closed until the later paid producer has completed and the DB pair has been
validated and frozen.
