# MarketLens Phase 10 — Experiment Protocol Audit & Timing Amendment

**Status:** PHASE 10 PROTOCOL V1 TIMING AMENDED — ZERO-LLM STRUCTURAL + EXACT-HORIZON GATES PASS
**Phase:** 10 — Experiment Protocol Audit & Freeze
**LLM/API cost of this audit/amendment:** 0

## 1. Scope and amendment rationale

This document records the bounded Phase 10 targeted audit and the final timing amendment agreed after the first Phase 10 protocol commit.

The earlier commit correctly froze the world/participant causal boundary, canonical shadow-price source, and N20/N30 adequacy rule, but represented the five formal judgement events on five different Agent-world dates. The timing amendment retains the Git history and changes only the experiment-time contract so that immediate pre/post manipulation contrasts share the same completed canonical state.

The amendment does **not** redesign frozen Phase 4/6/7/9 behavior and does **not** implement Phase 11.

Source hierarchy:

1. current committed `dissertation` branch/code;
2. `MarketLens_New_Chat_Handoff_2026-08-23_v2.md`;
3. previously frozen Phase 4/6/7/8/9 evidence;
4. legacy ZIP only for snapshot/round/date/fixed-market contrast.

## 2. Current TwinMarket targeted audit

Current inherited daily ordering is preserved as:

```text
calendar date t
→ OPEN/CLOSED from inherited trading calendar semantics
→ exact-date TwinMarket background news
→ pre-day belief source
→ graph build using inherited historical cutoff
→ dynamic top-user derivation
→ Phase 4 activation
→ active-Agent inherited reasoning
→ current-day post creation
→ OPEN: inherited matching/market update
   CLOSED: inherited non-trading profile propagation
→ forum actions / score update where enabled
→ completed canonical state S(t)
→ next calendar date
```

Frozen consequences:

- `world_tick + 1` means next calendar day, not next trading day;
- CLOSED/weekend days remain Agent-world ticks;
- OPEN does not depend on active-Agent/order/match counts;
- graph/top-user state used for tick `t` is not rebuilt merely for participant display;
- participant exposure occurs only after completed canonical state `S(t)` is sealed;
- current inherited OPEN/CLOSED authority remains `data/trading_days.csv:pretrade_date`.

## 3. Current MarketLens targeted audit

### Phase 4 activation

Preserved:
- heterogeneous Agent-specific stochastic activation;
- deterministic seeded sampling;
- activation recency/state carry-forward;
- no participant input;
- no weekend/closed-day throttling;
- zero-active remains a valid stochastic state.

### Phase 6 graph/prominence

Preserved:
- inherited `build_graph_new(...)` delegation;
- bounded runtime membership;
- dynamic degree-derived `is_top_user`;
- stable `user_type` remains distinct from dynamic prominence.

### Phase 7 market/news

Preserved:
- OPEN delegates to inherited TwinMarket matching/market mechanics;
- CLOSED delegates to inherited non-trading profile propagation;
- no MarketLens matching engine, price formula, Agent portfolio updater, or TradingDetails writer;
- TwinMarket background news remains distinct from participant-only experimental stimuli.

### Phase 9 multi-day continuity

Existing N20 real-backend evidence already validates sequential OPEN / OPEN / CLOSED execution with real Agent reasoning, forum/belief propagation, graph/top-user change, inherited market/non-trading updates, and participant/source isolation.

## 4. Participant portfolio/isolation and exact shadow-price source

Participant state remains session-scoped and does not write to Agent Profiles, TradingDetails, StockData, forum, belief, or graph state.

```text
Participant → own portfolio ✅
Participant → Agent matching/price/state ❌
```

Formal participant settlement uses:

```text
sealed canonical Agent-world state S(t)
→ StockData
→ exact stock_id
→ exact agent_world_date
→ close_price
→ participant shadow settlement only
```

Fail-closed rules:
- no frontend price override;
- no historical CSV settlement in formal mode;
- no forward fill;
- no nearest-date fallback;
- no participant call into Agent matching;
- missing exact canonical price means no participant execution.

The earlier `CsvClosePriceProvider` is retained only for earlier development/backend compatibility. Formal participant sessions will later be wired to sealed canonical state through the participant-visible-state layer.

## 5. Legacy ZIP targeted contrast

Legacy round/date/snapshot/fixed-market runtime control must not return:

```text
❌ fixed/exogenous participant market
❌ legacy 28-round semantic clock
❌ round → arbitrary frozen date
❌ live/prebaked dual runtime
❌ participant-specific copied Agent world
❌ snapshot as market-generation mechanism
```

Only immutable storage is retained:

```text
TwinMarket dynamically evolves
→ completed S(t)
→ immutable canonical storage
→ all formal participants observe the same S(t)
```

Snapshot is storage, not generation.

## 6. Final Phase 10 timing design

The protocol distinguishes:

```text
world_tick
agent_world_date
experiment_step
formal_judgement_event
```

They are not interchangeable.

### 6.1 Immediate pre/post manipulation contrasts

To reduce market/news/Agent-world movement as a confound:

```text
same sealed S(t)
→ J0 baseline judgement/confidence
→ misinformation release
→ J1 immediate post-misinformation judgement/confidence
→ one shadow-trade decision
```

and later:

```text
same sealed S(t)
→ J2 persistence / pre-correction judgement/confidence
→ authoritative correction release
→ J3 immediate post-correction judgement/confidence
→ one shadow-trade decision
```

Therefore:

```text
J0 and J1 share one canonical state/date.
J2 and J3 share one canonical state/date.
```

J4 is the later post-correction judgement after intervening Agent-world progression.

### 6.2 Experimental delay unit

`world_tick` remains one calendar day.

Experimental persistence delays are expressed in **OPEN-state transitions**:

```text
misinformation → persistence = 3 subsequent OPEN-state transitions
correction → later J4       = 3 subsequent OPEN-state transitions
```

CLOSED days continue to advance the Agent world but do not count as an OPEN-state transition.

This preserves inherited calendar progression while giving the participant two behavioural-only OPEN checkpoints between each manipulation and the later formal measurement.

### 6.3 Participant decision cadence

Every formal participant checkpoint occurs on an OPEN date and records one behavioural decision:

```text
BUY / SELL / HOLD
+ quantity for BUY/SELL
+ automatic participant portfolio state
```

`HOLD` is a valid behavioural decision.

Formal judgement is **not** required on every participant decision day.

The final design therefore contains:

```text
5 formal judgement events
across 3 formal judgement dates
7 participant decision days
```

## 7. Stimulus persistence contract

Controlled misinformation and correction remain participant-only.

Misinformation:

```text
released once
→ no repeated dose
→ remains available through the persistence phase
→ remains in participant information history after correction
```

Correction:

```text
explicitly links to the misinformation
→ remains available from release through experiment end
```

This prevents stimulus disappearance from acting as an unintended truth cue.

Phase 11 implements these frozen release/visibility rules; it does not redesign them.

## 8. Warm-up structural gate

Warm-up is not selected by looking for desirable Agent outputs.

Predeclared candidate set:

```text
W2 / W3 / W4 / W5 / W6 calendar ticks
```

A candidate is sufficient only if:

1. at least 2 episode-local OPEN ticks occur before participant entry;
2. at least 1 CLOSED tick occurs before participant entry;
3. `T_visible` is OPEN;
4. background-news coverage is complete through participant entry;
5. choose the smallest sufficient candidate.

Zero-LLM structural result:

| Candidate | T_visible candidate | Sufficient | OPEN before entry | CLOSED before entry | T_visible OPEN |
|---|---|---:|---:|---:|---:|
| W2 | 2023-06-17 | no | 2 | 0 | no |
| W3 | 2023-06-18 | no | 2 | 1 | no |
| W4 | 2023-06-19 | yes | 2 | 2 | yes |
| W5 | 2023-06-20 | yes | 3 | 2 | yes |
| W6 | 2023-06-21 | yes | 4 | 2 | yes |

Therefore:

```text
SELECT_W4
T_init    = 2023-06-15
warm-up   = 4 calendar world ticks
T_visible = 2023-06-19
```

## 9. Final exact timeline

The authoritative inherited calendar/news audit confirms `2023-06-29` is OPEN and every date from `2023-06-15` through `2023-06-29` has exactly one daily background-news row.

| world_tick | date | market | experiment_step | participant event | formal judgements | shadow decision |
|---:|---|---|---:|---|---|---:|
| 0 | 2023-06-15 | OPEN | — | warm-up | — | no |
| 1 | 2023-06-16 | OPEN | — | warm-up | — | no |
| 2 | 2023-06-17 | CLOSED | — | warm-up | — | no |
| 3 | 2023-06-18 | CLOSED | — | warm-up | — | no |
| 4 | 2023-06-19 | OPEN | 0 | baseline → misinformation → immediate response | J0, J1 | yes |
| 5 | 2023-06-20 | OPEN | 1 | misinformation-phase behaviour | — | yes |
| 6 | 2023-06-21 | OPEN | 2 | misinformation-phase behaviour | — | yes |
| 7 | 2023-06-22 | CLOSED | — | world-only closed interval | — | no |
| 8 | 2023-06-23 | CLOSED | — | world-only closed interval | — | no |
| 9 | 2023-06-24 | CLOSED | — | world-only closed interval | — | no |
| 10 | 2023-06-25 | CLOSED | — | world-only closed interval | — | no |
| 11 | 2023-06-26 | OPEN | 3 | persistence → correction → immediate response | J2, J3 | yes |
| 12 | 2023-06-27 | OPEN | 4 | post-correction behaviour | — | yes |
| 13 | 2023-06-28 | OPEN | 5 | post-correction behaviour | — | yes |
| 14 | 2023-06-29 | OPEN | 6 | later post-correction | J4 | yes |

Final participant-critical decision dates:

```text
2023-06-19
2023-06-20
2023-06-21
2023-06-26
2023-06-27
2023-06-28
2023-06-29
```

Final world contract:

```text
T_init    = 2023-06-15
T_visible = 2023-06-19
T_end     = 2023-06-29
formal world ticks = 15
participant decision days = 7
formal judgement events = 5
formal judgement dates = 3
```

## 10. Amended exact-horizon N20/N30 gate

The population adequacy rule remains unchanged and is now evaluated over the **actual amended 15-tick horizon and all 7 participant decision-critical dates**.

Predeclared population gates:

1. across 100 full-horizon trajectories, trajectories with at least one zero-active outcome on a participant-critical decision date must be `<= 5/100`;
2. mean active Agents on every participant-critical decision date must be `>= 3.0`;
3. all 100 predeclared seeds must be used with full-horizon activation-state carry-forward;
4. N20 PASS → select N20 by parsimony;
5. N20 FAIL + N30 PASS → one narrow N30 real-backend validation only;
6. no seed fishing.

Zero-LLM amended-horizon result:

```text
N20: PASS
critical-date any-zero trajectories = 4/100
minimum critical-date mean active = 3.88
overall mean active = 4.0347

N30: PASS
critical-date any-zero trajectories = 0/100
minimum critical-date mean active = 6.64
overall mean active = 6.6653
```

Therefore:

```text
FINAL N = 20
```

N30 real-backend validation remains unnecessary because N20 satisfies the unchanged predeclared adequacy gates.

## 11. Evidence classification and limitations

The structural/timing and N20/N30 gates are:

```text
NON-FORMAL ENGINEERING PREFLIGHT
NOT FORMAL EXPERIMENT EVIDENCE
```

They do not:
- generate the canonical Agent world;
- call an LLM;
- select a desirable Agent trajectory;
- mutate inherited market/forum state;
- use participant outcomes;
- prove a real-time long-term psychological persistence effect.

J4 should be interpreted as a later judgement **after intervening simulated market-world progression**, not as a multi-day real-world memory follow-up.

## 12. Phase 10 amendment boundary

This amendment changes only:
- timing semantics;
- the machine-readable protocol timeline;
- participant behavioural decision cadence;
- warm-up structural validation;
- exact-horizon N20/N30 validation/reporting;
- associated tests and audit evidence.

It does not change:
- Phase 4 activation algorithm;
- Phase 6 graph/prominence algorithm;
- Phase 7 market/news mechanics;
- inherited matching/price formation;
- participant isolation;
- canonical shadow-price source;
- participant-only misinformation/correction boundary;
- legacy architecture rejection;
- Phase 11 implementation.

## 13. Final Phase 10 freeze candidate

After the amendment and a clean-tree rerun on the final commit, Phase 10 can be tagged with:

```text
T_init = 2023-06-15
W = 4 calendar ticks
T_visible = 2023-06-19
T_end = 2023-06-29
formal world ticks = 15
participant decision days = 7
formal judgement events = 5 across 3 dates
J0/J1 same state
J2/J3 same state
misinformation→persistence = 3 OPEN transitions
correction→J4 = 3 OPEN transitions
final Agent N = 20
shadow price = sealed canonical StockData.close_price, exact stock/date
```

No Phase 11 code is included here.
