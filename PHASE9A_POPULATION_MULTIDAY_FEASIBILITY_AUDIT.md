# MarketLens Phase 9A — Population & Multi-Day Feasibility Audit

**Status:** AUDIT / DESIGN FREEZE BEFORE IMPLEMENTATION
**Date:** 22 August 2026
**Precondition:** Phase 8 measurement facade complete and ready to freeze
**TwinMarket baseline:** `de5f2446fcba0d0aba533a6adaede034160e29b4`
**Phase 7 frozen tag:** `phase07-dynamic-twinmarket-market-news-v1.0`

---

## 1. Audit question

Phase 9 must answer two separate engineering questions:

1. **Population feasibility:** what bounded Agent population size is computationally feasible and still provides a useful dynamic Agent-world background?
2. **Multi-day feasibility:** can MarketLens carry the inherited Agent world forward across sequential calendar days without reimplementing TwinMarket forum, belief, market, portfolio, or holiday behaviour?

This phase is engineering feasibility. It is **not** formal experiment evidence and does not freeze the final participant protocol.

---

## 2. Baseline integrity finding

The `simulation.py` in the legacy ZIP is byte-identical to the official TwinMarket baseline used by MarketLens:

```text
SHA256
046512ad9995739ecdd648ac1f66b8f238bcef8beecc99e04a29a6f9fbe74254
```

Therefore its multi-day control flow is valid evidence for understanding the inherited baseline.

However, several other files in the legacy ZIP are later project modifications, including:

```text
util/ForumDB.py
util/UserDB.py
trader/trading_agent.py
```

Those modified ZIP versions must **not** be copied wholesale into current MarketLens.

The current repository's inherited baseline/core remains authoritative.

---

# 3. What original TwinMarket already owns

Original `simulation.init_simulation(...)` already demonstrates the complete inherited day sequence:

```text
calendar date
    ↓
determine trading/non-trading day
    ↓
load current belief source
    ↓
build historical graph
    ↓
derive dynamic top users
    ↓
run Agent reasoning
    ↓
write decision / reaction / post outputs
    ↓
create Agent posts
    ↓
trading day:
    inherited matching
non-trading day:
    inherited holiday profile update
    ↓
Day 2+:
    execute forum actions
    update forum scores
    ↓
advance one calendar day
```

This confirms that MarketLens does **not** need to invent a multi-day belief, forum, graph, market, or holiday model.

---

# 4. Direct inherited-call map

Phase 9 should call the following inherited functionality rather than reproduce it.

| Required behaviour | Inherited owner | Phase 9 rule |
|---|---|---|
| Agent reasoning | `simulation.process_user_input(...)` | **CALL DIRECTLY** |
| Graph construction | `simulation.build_graph_new(...)` | **CALL DIRECTLY** |
| Dynamic top-user selection | `simulation.get_top_n_users_by_degree(...)` | **CALL DIRECTLY**, retain deterministic tie policy already frozen by Phase 6 where needed |
| Decision → order semantics | `trader.matching_engine.read_json(...)` | **CALL / READ inherited semantics** |
| Market advance / matching | `trader.matching_engine.test_matching_system(...)` | **CALL DIRECTLY once per open trading day** |
| Closed-day Agent profile carry-forward | `trader.matching_engine.update_profiles_table_holiday(...)` | **CALL DIRECTLY on authoritative non-trading day** |
| Agent post creation | `util.ForumDB.create_post_db(...)` | **CALL DIRECTLY** |
| Forum action execution | `util.ForumDB.execute_forum_actions(...)` | **CALL DIRECTLY** |
| Forum score update | `util.ForumDB.update_posts_score_by_date_range(...)` | **CALL DIRECTLY** |
| Next-day belief source | `util.ForumDB.get_all_users_posts_db(...)` | **CALL DIRECTLY / read-only** |
| Initial isolated reset | `trader.utility.init_system(...)` | **CALL DIRECTLY only on an isolated copied runtime** |
| Market-open status | `data/trading_days.csv` | **AUTHORITATIVE** |

MarketLens may orchestrate these calls and record evidence, but must not replace their behaviour.

---

# 5. Why Phase 9 must NOT simply call `simulation.init_simulation(...)`

Although `init_simulation(...)` owns the inherited multi-day sequence, using it wholesale would violate already-frozen MarketLens behaviour.

The baseline function:

- obtains all Agent IDs from the supplied DB;
- applies one global `activate_prob`;
- independently draws `random.random() < activate_prob`;
- internally owns the whole date loop;
- computes `top_n` from its `node` argument;
- does not use the frozen Phase 4 heterogeneous sparse activation policy.

MarketLens Phase 4 is already frozen.

Therefore:

```text
simulation.init_simulation(...)
    = reference sequence / inherited source of truth
    ≠ MarketLens Phase 9 execution entry point
```

The correct approach is a **thin per-day orchestrator** that follows the inherited sequence while continuing to use MarketLens's frozen bounded population and Phase 4 activation.

---

# 6. Legacy Phase B code audit

## 6.1 `run_phase_b_execution.py`

Useful patterns:

- imports `simulation`;
- directly calls `simulation.build_graph_new(...)`;
- directly calls `simulation.get_top_n_users_by_degree(...)`;
- directly calls `simulation.process_user_input(...)`;
- uses isolated runtime copies;
- labels real-backend execution non-formal;
- explicitly refuses multi-day execution until propagation is validated.

Do **not** reuse the runner itself because it also contains obsolete assumptions:

```text
exogenous/fixed market trajectory
Agent decisions not applied to price
one-day-only execution
old Phase-B instrumentation
structured-output prompt injection
old candidate-fixture architecture
```

These conflict with current dynamic Agent-world MarketLens.

## 6.2 Old structured/instrumentation layer

Do not reuse.

It monkeypatches Agent inference and can alter error behaviour / prompts.

Phase 8 has already established the cleaner rule:

```text
observe inherited output
do not instrument Agent inference
```

## 6.3 Old constrained Phase-B candidate builder

Do not reuse for current population construction.

It deliberately forces:

```text
>= 1 influential
>= 1 smaller blogger
>= 1 ordinary investor
```

for every candidate N.

Current MarketLens Phase 3 explicitly freezes the opposite principle:

```text
strategy ratio preserved
user_type inherited
no user_type quota
no rare-category oversampling
```

Therefore forcing source-tier coverage would change the current population policy.

---

# 7. What CAN be reused from the legacy population work

The old **no-LLM structural sampling methodology** is aligned with current Phase 3 at the conceptual level:

```text
strategy-stratified
without replacement
user_type inherited
no user_type reassignment
many deterministic seeds
measure representation/fidelity
```

This can be used as a **Phase 9 structural sensitivity audit**, not as runtime population logic.

It costs zero LLM calls.

---

# 8. Re-run of the old structural sensitivity method against the verified source DB

The audit was executed against the source database with SHA256:

```text
90b19c5cb9dac6708dff06fe4def5205cecef1a90da0f74eec449dab5a6769c3
```

Verified source composition:

```text
N = 1000

Fundamental = 400
Technical   = 600

Influential user = 11
Smaller blogger  = 77
Ordinary investor = 912
```

The adaptive no-LLM sensitivity check tested:

```text
N = 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60
```

using 10,000 seeds.

Result:

```text
stop_reason = max_n_reached_no_plateau_detected
early_stopping_triggered = false
```

The main reason is the extreme rarity of the inherited influential-user tier.

Approximate / observed coverage:

| N | P(≥1 influential) | P(≥1 smaller blogger) | P(all 3 source tiers) |
|---:|---:|---:|---:|
| 10 | 10.9% | 55.1% | 5.4% |
| 20 | 20.8% | 80.2% | 16.3% |
| 30 | 29.2% | 91.3% | 26.7% |
| 40 | 37.3% | 96.2% | 35.9% |
| 50 | 43.8% | 98.3% | 43.1% |
| 60 | 50.1% | 99.2% | 49.6% |

This is **not** evidence that N must be 60.

It demonstrates that:

> requiring every bounded sample to contain a stable `user_type = influential` Agent is incompatible with strict inherited sampling at modest N.

That is acceptable because MarketLens already distinguishes:

```text
stable user_type
    ≠
dynamic is_top_user
```

Dynamic graph prominence continues to exist even when a bounded sample contains no inherited 大V persona.

Therefore final N must **not** be selected by demanding rare source-tier coverage.

---

# 9. Candidate N recommendation for Phase 9 engineering comparison

For paid/dynamic feasibility, use:

```text
N10
N20
N40
```

as **engineering comparison points**, not final candidates.

Reasons:

- all admit the exact inherited 40:60 strategy ratio;
- N20 is the existing verified development fixture;
- N10 gives a lower-cost/sparser boundary;
- N40 gives a clean 2× population scale above N20;
- expected sparse activation scales approximately from ~2 → ~4 → ~8 active Agents per step under a ~0.20 average activation level;
- dynamic top-user counts naturally scale approximately 1 → 2 → 4 under the current 10% rule;
- this creates a useful low / current / higher comparison without paying for every +5 population increment.

Do **not** interpret these as final N values yet.

If the N40 dynamic run shows little benefit relative to N20, there is no reason to expand immediately to N60 merely to chase stable source-tier coverage.

---

# 10. Multi-day validation horizon

Before paid population comparison, first validate multi-day state continuity using the already-verified **N20 development population**.

Recommended engineering horizon:

```text
2023-06-15  Thursday   trading day
2023-06-16  Friday     trading day
2023-06-17  Saturday   non-trading day
```

This three-calendar-day horizon is deliberately useful.

It exercises:

### Day 1
- initial belief source;
- graph/top-user;
- Phase 4 activation;
- inherited Agent reasoning;
- inherited market;
- posts.

### Day 2
- next-day belief source from forum state;
- previous-day graph/TradingDetails history;
- dynamic top-user recomputation;
- new Phase 4 activation;
- inherited Agent reasoning;
- inherited market;
- Day-2 forum actions and post-score updates.

### Day 3
- authoritative market closure;
- no trading-day matching path;
- inherited holiday profile update;
- Agent social/belief environment may continue according to inherited behaviour;
- future participant trading must be considered disabled for this date.

The background-news source contains:

```text
2023-06-15: 19 items
2023-06-16:  7 items
2023-06-17:  0 items
```

Therefore no hard-coded `expected_news_count = 19` may appear in a multi-day invariant.

---

# 11. Important inherited non-trading-day behaviour

Original `PersonalizedStockTrader.input_info(...)` still runs activated Agents on a non-trading day.

On a closed day it can still:

- read/recommend forum posts on Day 2+;
- update belief;
- produce a post/intention.

But it skips the trading-specific branches:

- stock recommendation for trading;
- stock selection;
- trading-data collection;
- final trading decision.

Therefore:

```text
market closed
    ≠
Agent world frozen
```

It means:

```text
market trading closed
social/belief Agent activity may continue
```

This is inherited behaviour and should remain unchanged unless the experiment protocol later explicitly decides otherwise.

Participant trading remains disabled because the market calendar is closed.

---

# 12. Important inherited open-day edge case

`test_matching_system(...)` has an internal branch:

```text
open trading day
+ no valid Agent orders
    ↓
holiday-style Profiles / StockData carry-forward
```

This is an inherited implementation fallback.

It must **not** be used to determine market-open status.

The authoritative rule remains:

```text
market_open
← trading_days.csv
```

not:

```text
matching branch
Agent order count
matched trade count
```

---

# 13. Proposed Phase 9 implementation boundary

Phase 9 should add a thin MarketLens-owned sequential runner, conceptually:

```text
marketlens/market/
└── multiday.py

scripts/preflight/
└── run_phase09_multiday_feasibility.py
```

The runner should:

1. copy the bounded runtime DB to an isolated temporary workspace;
2. initialize/copy an isolated forum DB;
3. call inherited reset only on those copies;
4. iterate **calendar dates**;
5. read authoritative trading-day status;
6. obtain belief inputs using inherited forum functions;
7. build graph via inherited TwinMarket function;
8. derive dynamic top users;
9. obtain active IDs using the already-frozen Phase 4 policy;
10. call inherited `simulation.process_user_input(...)` independently for each activated Agent;
11. persist existing Agent result files;
12. call inherited post creation;
13. call inherited market/holiday update;
14. on Day 2+, call inherited forum actions and score update;
15. use Phase 8 facade/measurement concepts to record each day's observable evidence.

MarketLens must not implement new market/forum/belief state formulas.

---

# 14. Phase 9 execution order

Do not immediately run N10/N20/N40 with the real backend.

Use the following gates:

```text
9A  inherited-source audit                         COMPLETE

9B  zero-LLM sequential orchestration tests
    - dates
    - open/closed branch
    - belief-source transition
    - graph call sequence
    - Phase 4 activation carry-forward
    - forum/post call sequence
    - no participant state

9C  N20 × 3-calendar-day real-backend preflight
    2023-06-15 → 2023-06-17
    NON-FORMAL / ENGINEERING FEASIBILITY

9D  inspect runtime/call cost and state continuity

9E  only if 9C passes:
    population feasibility comparison
    N10 / N20 / N40
```

This prevents paying for three populations before knowing that the multi-day orchestration is valid.

---

# 15. Phase 9 pass criteria for the first N20 multi-day preflight

Required:

```text
same isolated runtime persists across all 3 calendar days

Day 1 → Day 2 Profiles continuity
Day 1 → Day 2 StockData continuity
Day 1 → Day 2 TradingDetails continuity where trades exist

Day 1 posts visible to inherited Day 2 forum/belief path
Day 2 belief input demonstrably uses inherited forum-derived state or documented fallback

graph recomputed each day from inherited historical state
dynamic top users recomputed each day

Phase 4 activation policy retained
activation recency state carried across days
no global activate_prob replacement

2023-06-15 market_open = true
2023-06-16 market_open = true
2023-06-17 market_open = false

closed day does not execute normal market matching
closed day follows inherited holiday path

participant data used = false
custom market logic used = false
custom forum logic used = false
custom belief propagation used = false

source population DB unchanged
canonical source data unchanged
```

---

# 16. What Phase 9 must NOT freeze

Even after the 3-day preflight, do not yet freeze:

```text
final Agent N
formal experiment day count
participant round count
participant step ↔ Agent-world date map
rumour timing
correction timing
later-measurement interval
Agent exposure to experimental misinformation/correction
```

Those remain Phase 10 protocol decisions.

---

# 17. Engineering decision

Proceed with **Phase 9B zero-LLM sequential orchestration tests** next.

Do not port the legacy Phase-B runner wholesale.

Do not call `simulation.init_simulation(...)` wholesale.

Build the smallest possible orchestration layer that preserves the already-frozen MarketLens population/activation policy while delegating every available day-level behaviour back to inherited TwinMarket functions.
