# Phase 13C — Canonical Episode-Pool Freeze Audit

## Decision

Phase 13C freezes a **three-episode canonical Agent-world pool**, not one participant-specific live world and not one single canonical world.

The formal pool is pre-generated before participant exposure. Every episode uses the **same frozen N30 population, the same Phase 4 activation sequence, the same Phase 10 v1.1 horizon, and the same inherited TwinMarket execution pipeline**. The three executions are repeated stochastic realizations of the same experimental world specification.

Participants are later assigned across the frozen pool using a **balanced random assignment**. `episode_id` must be retained in participant records and used as an analysis/blocking variable where appropriate.

## Why this replaces the earlier single-episode proposal

A single canonical episode gives maximum control, but makes the experiment depend on one stochastic LLM-agent market trajectory. Generating a small, predeclared pool improves robustness to episode-specific market/forum paths without creating a new world for every participant.

The rejected alternative is:

```text
participant 1 -> newly generated world 1
participant 2 -> newly generated world 2
...
```

That would confound participant differences with uncontrolled world-level variation and would make raw profit difficult to compare.

The accepted design is:

```text
                    ┌─ episode_01 ─ participants assigned here
frozen protocol ────├─ episode_02 ─ participants assigned here
                    └─ episode_03 ─ participants assigned here
```

All three episodes exist before the first participant session.

## Frozen shared identity

```text
episode_pool_id = marketlens-canonical-episode-pool-v1
episode_count = 3

episode_ids:
- marketlens-canonical-episode-v1-e01
- marketlens-canonical-episode-v1-e02
- marketlens-canonical-episode-v1-e03

protocol_version = 1.1
population = N30
population seed = marketlens-dev-population-01
N30 membership SHA256 =
60d846b21c15e2213f6f897a17a7ea98039fbf461abe54ee89e1b6779d24b2d4

activation seed = marketlens-phase09b-activation-01
T_init = 2023-06-15
T_visible = 2023-06-19
T_end = 2023-07-11
world ticks per episode = 27
OPEN per episode = 17
CLOSED per episode = 10
Agent pipeline executions per episode = 193
Agent pipeline executions for full three-episode pool = 579
```

The first three active counts remain `10 / 7 / 3`, matching the completed once-only N30 real-backend feasibility validation.

## What varies across the three episodes

The protocol does **not** deliberately change population, activation seed, decision dates, participant stimulus, or inherited market rules between episodes.

The episodes are repeated executions of the same stochastic Agent world. Natural differences may therefore arise in:

- LLM reasoning text;
- Agent posts and reactions;
- belief evolution;
- inherited market activity;
- price trajectory;
- cumulative forum history.

No minimum amount of cross-episode difference is required. If two technically valid episodes happen to be similar, that is a valid natural result and **not a reason to rerun either episode**.

## Participant assignment

After all three episodes and their participant-facing text assets are frozen:

```text
participant -> balanced random assignment -> one frozen episode_id
```

Required rules:

- assignment is balanced across the three episode IDs as far as the final sample permits;
- assignment cannot depend on episode profitability, price direction, post volume, sentiment, or any participant outcome;
- the assigned `episode_id` is stored with participant data;
- a participant never causes a new Agent-world execution;
- participant trades remain shadow trades and never mutate the assigned episode.

This allows participant outcomes, including profit/return as a secondary behavioural measure, to be interpreted with `episode_id` available as a world-level control/blocking factor.

## Formal asset layout

After three technically valid executions are frozen:

```text
data/marketlens/canonical_episode/v1/
├── pool_manifest.json
├── episode_01/
│   ├── agent_world.db
│   ├── forum.db
│   └── episode_manifest.json
├── episode_02/
│   ├── agent_world.db
│   ├── forum.db
│   └── episode_manifest.json
└── episode_03/
    ├── agent_world.db
    ├── forum.db
    └── episode_manifest.json
```

Raw execution evidence remains separate:

```text
artifacts/formal/canonical_episode/<episode_id>/
```

Raw logs are evidence, not a second market state.

## Reuse audit

The formal producer must reuse the already validated inherited execution path from the Phase 9/10 real-backend work, including inherited TwinMarket Agent reasoning, forum/belief progression, matching, price formation, and Agent portfolio updates.

The Phase 10 feasibility runner itself is **not** a formal episode producer because its successful run lives in a `TemporaryDirectory` and is deleted after validation. Its execution pipeline may be reused, but its debug/temporary workspace lifecycle must not be reused for formal assets.

## Predeclared technical acceptance gates — applied independently to each episode slot

An episode slot is technically eligible for freeze only if:

- all 27 contiguous calendar ticks complete;
- all 193 predeclared active-Agent pipeline executions complete;
- the exact shared activation plan is followed;
- authoritative OPEN/CLOSED actions match the protected calendar;
- the Agent-world and forum state chain is continuous;
- protected source assets remain unchanged;
- participant data is absent;
- controlled misinformation/correction is absent from the Agent world;
- no custom matching, price formation, Agent portfolio, TradingDetails, forum, or belief logic is introduced;
- exact-date participant price coverage is complete for the frozen participant decision dates;
- every participant-visible forum author/date can resolve the inherited profile snapshot required by the Phase 12 source cue;
- the final Agent-world and forum DBs are hash-pinned in that episode's manifest.

The pool manifest is frozen only after all three predeclared episode IDs independently pass these technical gates.

## Outcome-blind episode retention and rerun policy

Formal acceptance deliberately has **no** gate on:

- number of posts;
- number of trades or matched trades;
- price direction or volatility;
- sentiment or tone;
- desired misinformation/correction effect;
- minimum divergence between episodes;
- whether two episodes are considered "too similar".

A technically valid completed episode **must be retained** in its predeclared slot.

Forbidden:

```text
seed substitution
seed fishing
partial resume
run extra worlds and choose the best three
replace an episode because profit path looks unattractive
replace an episode because it is too similar to another episode
exclude a valid episode after reviewing natural outcomes
```

A technically invalid attempt (for example API/transport failure, Agent pipeline failure, DB corruption, protected-input drift, or state-chain violation) may restart **that same episode slot from the same frozen initial state and same shared execution plan** only after failed-attempt evidence is retained.

A code or contract change requires a new plan version before further formal execution.

## Translation ordering

No formal Agent/forum translation pack is generated before the source episode pool is frozen.

Required ordering:

```text
freeze shared three-episode execution contract
→ generate/freeze episode_01
→ generate/freeze episode_02
→ generate/freeze episode_03
→ freeze pool_manifest.json
→ derive participant source-text inventories per episode
→ review/freeze English text packs
→ bind Phase 13B participant projection to the assigned episode_id
```

No live translation is introduced.

## Current status

Phase 13C remains a **zero-LLM contract only**. This patch does not execute any of the three paid canonical episodes. Formal assets and formal translation assets must therefore remain absent/fail-closed until the later producer executes the already-frozen plan.
