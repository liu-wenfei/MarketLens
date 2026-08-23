# MarketLens Phase 10 — Experiment Protocol Audit & Protocol v1.1 Long-Horizon Amendment

**Status:** PHASE 10 PROTOCOL v1.1 — 15 DECISION DAYS / N30 / REAL-BACKEND FEASIBILITY PASS
**Phase:** 10 — Experiment Protocol Audit & Freeze
**LLM/API cost of this audit/amendment:** 0

## 1. Scope and amendment rationale

This document records the bounded Phase 10 targeted audit, the tagged Protocol v1.0 timing freeze, and the subsequent outcome-blind long-horizon amendment to Protocol v1.1.

Protocol v1.0 correctly froze the world/participant causal boundary, canonical shadow-price source, same-state immediate contrasts, and N20/N30 adequacy rule. After v1.0 was tagged, zero-LLM design-impact comparisons were used to compare behavioural sampling density and longer symmetric intervals without looking at participant outcomes or LLM-generated effects. This v1.1 amendment retains the full Git history and adopts the selected 15-decision long-horizon design plus N30 after the already-predeclared N30 real-backend feasibility gate PASSed.

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

## 6. Final Phase 10 v1.1 timing design

The protocol distinguishes:

```text
world_tick
agent_world_date
experiment_step
formal_judgement_event
```

They are not interchangeable.

### 6.1 Immediate pre/post manipulation contrasts

Immediate effects remain same-state contrasts:

```text
same sealed S(t)
→ J0 baseline judgement/confidence
→ misinformation release
→ J1 immediate post-misinformation judgement/confidence
→ one shadow-trade decision
```

and:

```text
same sealed S(t)
→ J2 persistence / pre-correction judgement/confidence
→ authoritative correction release
→ J3 immediate post-correction judgement/confidence
→ one shadow-trade decision
```

Therefore `J0/J1` share one completed canonical state and `J2/J3` share one completed canonical state. J4 is the later post-correction judgement after intervening simulated Agent-world progression.

### 6.2 Outcome-blind decision-day and interval selection

Protocol v1.0 froze 7 participant decision days and 3 OPEN-state transitions per delayed phase. Before any formal participant outcome existed, zero-LLM design-impact analyses compared:

```text
0 / 2 / 4 / 7 / 9 / 11 decision days
```

for behavioural sampling density, followed by longer symmetric candidates:

```text
11 / 13 / 15 / 17 decision days
= 5 / 6 / 7 / 8 OPEN-state transitions per phase
```

No candidate was selected from misinformation/correction effect size. The selected design is:

```text
participant decision days = 15
OPEN transitions per phase = 7
intermediate behavioural-only observations per phase = 6
```

The 15-decision candidate was selected because, on the inherited calendar, it gives equal delayed windows around the correction checkpoint:

```text
misinformation → correction = 7 OPEN transitions = 11 simulated calendar days
correction → J4             = 7 OPEN transitions = 11 simulated calendar days
```

The 17-decision alternative adds only one intermediate behavioural point per phase while losing simulated-calendar symmetry (`14 / 10` elapsed days) and adding participant/simulation burden.

This is simulated-time progression, not a claim of 11 days of real human memory retention.

### 6.3 Participant decision cadence

Every participant checkpoint occurs on an inherited OPEN date and records exactly one behavioural decision:

```text
BUY / SELL / HOLD
+ quantity for BUY/SELL
+ automatic participant portfolio state
```

`HOLD` remains a valid behavioural observation. Formal judgement is not repeated at every decision point.

Final v1.1 counts:

```text
5 formal judgement events
across 3 formal judgement dates
15 participant decision days
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

This prevents stimulus disappearance from acting as an unintended truth cue. Phase 11 implements these frozen release/visibility rules; it does not redesign them.

## 8. Warm-up structural gate

Warm-up remains outcome-blind. The predeclared candidate set is `W2/W3/W4/W5/W6` calendar ticks. A candidate is sufficient only if it has at least two episode-local OPEN ticks and one CLOSED tick before entry, an OPEN participant entry date, and complete background-news coverage. The smallest sufficient candidate is selected.

The existing zero-LLM gate remains:

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

## 9. Final v1.1 exact timeline

The inherited trading calendar gives 17 OPEN and 10 CLOSED ticks across the 27-tick canonical horizon. Participant decisions occur on every participant-visible OPEN state from `2023-06-19` through `2023-07-11`.

| tick | date | market | step | participant event | formal judgements |
|---:|---|---|---:|---|---|
| 0 | 2023-06-15 | OPEN | — | warm-up | — |
| 1 | 2023-06-16 | OPEN | — | warm-up | — |
| 2 | 2023-06-17 | CLOSED | — | warm-up | — |
| 3 | 2023-06-18 | CLOSED | — | warm-up | — |
| 4 | 2023-06-19 | OPEN | 0 | baseline → misinformation → immediate response | J0, J1 |
| 5 | 2023-06-20 | OPEN | 1 | misinformation-phase behaviour | — |
| 6 | 2023-06-21 | OPEN | 2 | misinformation-phase behaviour | — |
| 7–10 | 2023-06-22…25 | CLOSED | — | world-only progression | — |
| 11 | 2023-06-26 | OPEN | 3 | misinformation-phase behaviour | — |
| 12 | 2023-06-27 | OPEN | 4 | misinformation-phase behaviour | — |
| 13 | 2023-06-28 | OPEN | 5 | misinformation-phase behaviour | — |
| 14 | 2023-06-29 | OPEN | 6 | misinformation-phase behaviour | — |
| 15 | 2023-06-30 | OPEN | 7 | persistence → correction → immediate response | J2, J3 |
| 16–17 | 2023-07-01…02 | CLOSED | — | world-only progression | — |
| 18 | 2023-07-03 | OPEN | 8 | post-correction behaviour | — |
| 19 | 2023-07-04 | OPEN | 9 | post-correction behaviour | — |
| 20 | 2023-07-05 | OPEN | 10 | post-correction behaviour | — |
| 21 | 2023-07-06 | OPEN | 11 | post-correction behaviour | — |
| 22 | 2023-07-07 | OPEN | 12 | post-correction behaviour | — |
| 23–24 | 2023-07-08…09 | CLOSED | — | world-only progression | — |
| 25 | 2023-07-10 | OPEN | 13 | post-correction behaviour | — |
| 26 | 2023-07-11 | OPEN | 14 | later post-correction | J4 |

Final participant-critical decision dates:

```text
2023-06-19, 2023-06-20, 2023-06-21,
2023-06-26, 2023-06-27, 2023-06-28, 2023-06-29, 2023-06-30,
2023-07-03, 2023-07-04, 2023-07-05, 2023-07-06, 2023-07-07,
2023-07-10, 2023-07-11
```

Final world contract:

```text
T_init = 2023-06-15
T_visible = 2023-06-19
T_end = 2023-07-11
formal world ticks = 27
participant-visible simulated span = 23 calendar days inclusive
participant decision days = 15
formal judgement events = 5
formal judgement dates = 3
```

## 10. Exact-horizon population adequacy and N30 real-backend gate

The population thresholds were **not** relaxed when the horizon was lengthened:

```text
critical-any-zero trajectories <= 5/100
minimum mean active on every participant-critical date >= 3.0
100 predeclared activation seeds
full-horizon activation-state carry-forward
no seed fishing
```

For the selected 27-tick / 15-decision horizon, the zero-LLM comparison gives:

```text
N20: FAIL
critical-any-zero trajectories = 9/100
minimum critical-date mean active = 3.88
overall mean active = 4.0737

N30: PASS
critical-any-zero trajectories = 0/100
minimum critical-date mean active = 6.26
overall mean active = 6.6807
```

Because N20 failed and N30 passed, the predeclared rule required one bounded N30 real-backend validation before final freeze. That validation was executed once on clean commit `8b4704b` using the already-established seeds and fixed N30 membership:

```text
population seed = marketlens-dev-population-01
N30 membership SHA256 = 60d846b21c15e2213f6f897a17a7ea98039fbf461abe54ee89e1b6779d24b2d4
activation seed = marketlens-phase09b-activation-01
2023-06-15 OPEN   10 active
2023-06-16 OPEN    7 active
2023-06-17 CLOSED  3 active
```

Real-backend result:

```text
PASS
posts created = 20
ForumDB belief Agents observed = 25
later-day forum action calls = 10
activation continuity = PASS
graph bounded to N30 = PASS
same working runtime/forum across days = PASS
OPEN / OPEN / CLOSED inherited paths = PASS
```

No retry, seed substitution, forced activation, custom matching, custom pricing, or alternative forum/belief logic was used.

Therefore the v1.1 formal population is:

```text
FINAL N = 30
```

The real-backend run remains non-formal engineering feasibility evidence; it is not participant or formal experiment evidence.

## 11. Evidence classification and limitations

The timing, long-horizon comparison, population adequacy gate, and N30 backend validation are engineering/design evidence. They do not establish which interval produces a stronger misinformation effect, estimate human fatigue, or prove real-time long-term retention.

J4 must be described as a later judgement **after intervening simulated market-world progression**, not as an 11-day real-world follow-up.

The exact canonical 27-tick Agent world is still to be generated/frozen later under the formal experiment workflow. Its outputs must not be used to reselect the already-frozen population, dates, or interval merely because one trajectory looks more desirable.

## 12. Phase 10 v1.1 amendment boundary

This amendment changes only:

- the frozen simulated horizon and participant decision cadence;
- delayed OPEN-state intervals;
- exact protocol timeline;
- final population from N20 to N30 following unchanged adequacy gates and the completed real-backend gate;
- exact-horizon zero-LLM validation/reporting and associated tests/evidence.

It does **not** change:

- Phase 4 activation algorithm;
- Phase 6 graph/prominence algorithm;
- Phase 7 market/news mechanics;
- inherited matching/price formation;
- participant isolation;
- canonical shadow-price source;
- participant-only misinformation/correction boundary;
- same-state J0/J1 and J2/J3 logic;
- legacy architecture rejection;
- Phase 11 implementation.

## 13. Final Phase 10 v1.1 freeze

After this bounded amendment passes tests, scope checks, the exact 27-tick zero-LLM gate, and a clean-HEAD reproducibility rerun, Phase 10 v1.1 freezes:

```text
T_init = 2023-06-15
W = 4 calendar ticks
T_visible = 2023-06-19
T_end = 2023-07-11
formal world ticks = 27
participant decision days = 15
formal judgement events = 5 across 3 dates
J0/J1 = 2023-06-19, same sealed state
J2/J3 = 2023-06-30, same sealed state
J4 = 2023-07-11
misinformation→persistence = 7 OPEN transitions = 11 simulated calendar days
correction→J4 = 7 OPEN transitions = 11 simulated calendar days
final Agent N = 30
shadow price = sealed canonical StockData.close_price, exact stock/date
```

No Phase 11 stimulus-engine code is included in this amendment.
