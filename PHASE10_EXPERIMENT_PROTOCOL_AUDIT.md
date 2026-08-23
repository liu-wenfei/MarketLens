# MarketLens Phase 10 — Experiment Protocol Audit & Frozen Candidate Contract

**Status:** PHASE 10 PROTOCOL V1 FROZEN — ZERO-LLM EXACT-HORIZON GATE PASS
**Phase:** 10 — Experiment Protocol Audit & Freeze
**LLM/API cost of this audit:** 0

## 1. Scope

This document records the bounded Phase 10 targeted audit and the user-confirmed protocol candidate. It does not redesign frozen Phase 4/6/7/9 behavior and does not implement Phase 11 controlled stimuli.

Source hierarchy for this patch:

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
→ graph build using history through t-1
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

Consequences frozen by Phase 10:

- `world_tick + 1` means next calendar day, not next trading day.
- CLOSED/weekend days remain world ticks.
- OPEN does not depend on active-Agent/order/match counts.
- belief and graph/top-user state used for tick `t` are determined before current-day generated posts/actions.
- MarketLens must not rebuild graph after day completion merely to create a participant snapshot.
- participant exposure occurs only after completed canonical state `S(t)` is sealed.

The current inherited implementation derives its trading-day set from `data/trading_days.csv:pretrade_date`; Phase 10 records rather than silently replaces this behavior.

## 3. Current MarketLens targeted audit

### Phase 4 activation

Preserved:
- heterogeneous Agent-specific probabilities;
- deterministic seeded Bernoulli sampling;
- activation-local recency carry-forward;
- no participant feature, `user_type`, strategy, truth, or dynamic prominence as an activation shortcut;
- no weekend/closed-day throttling;
- zero-active is valid.

### Phase 6 graph/prominence

Preserved:
- inherited `build_graph_new(...)` delegation;
- bounded runtime membership;
- dynamic degree-derived `is_top_user`;
- stable `user_type` remains separate from dynamic prominence.

### Phase 7 market/news

Preserved:
- OPEN delegates to inherited TwinMarket matching/market mechanics;
- CLOSED delegates to inherited non-trading profile propagation;
- no MarketLens matching engine, price formula, Agent portfolio updater, or TradingDetails writer;
- TwinMarket background news remains separate from participant-only experimental stimuli.

### Phase 9 multi-day continuity

Existing N20 real-backend evidence validates three sequential calendar dates (OPEN / OPEN / CLOSED) with:
- real Agent reasoning;
- forum posts/actions;
- belief propagation;
- graph/top-user change;
- inherited market/non-trading updates;
- Agent runtime state continuity;
- participant/source isolation.

## 4. Participant portfolio/isolation audit

Participant state remains session-scoped and does not write to Agent Profiles, TradingDetails, StockData, forum, belief, or graph state.

The participant remains a price-taking shadow investor:

```text
Participant → own portfolio ✅
Participant → Agent matching/price/state ❌
```

## 5. Shadow-price source gap found by audit

Earlier participant portfolio code uses `CsvClosePriceProvider` over `data/stock_data.csv:close`.

That source was adequate for the earlier isolated portfolio layer but is not valid for the formal Phase 10 shared-world contract, because Phase 7/9 Agent-world prices are dynamically written by inherited TwinMarket into runtime `StockData.close_price`.

Formal Phase 10 therefore freezes:

```text
sealed canonical Agent-world episode/state S(t)
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
- no Agent matching call for participant execution;
- missing exact canonical price means no participant execution.

The patch adds a read-only canonical `StockData.close_price` adapter and keeps the older CSV adapter only for earlier development/backend compatibility. Wiring formal participant sessions to the sealed canonical episode belongs to the later participant-visible-state integration, not to Phase 10 market redesign.

## 6. Legacy ZIP targeted contrast

Legacy architecture used round/date/snapshot/fixed-market concepts as runtime control, including old fixed round mappings and live/prebaked or participant-specific copied environments.

Those mechanisms must not return:

```text
❌ fixed/exogenous participant market
❌ legacy 28-round semantic clock
❌ round → arbitrary frozen date
❌ live/prebaked dual runtime
❌ participant-specific copied Agent world
❌ snapshot as market-generation mechanism
```

Only the storage idea is retained:

```text
TwinMarket dynamically evolves
→ completed S(t)
→ immutable canonical storage
→ all participants observe the same S(t)
```

Snapshot is storage, not generation.

## 7. User-confirmed Phase 10 protocol candidate

```text
T_init    = 2023-06-15
warm-up   = 4 calendar ticks (2023-06-15 .. 2023-06-18)
T_visible = 2023-06-19
T_end     = 2023-06-28
horizon   = 14 calendar world ticks (0..13)
participant checkpoints = 5
```

Exact mapping:

| world_tick | date | market | experiment_step | stage | judgement | shadow trade |
|---:|---|---|---:|---|---:|---:|
| 0 | 2023-06-15 | OPEN | — | warm-up | no | no |
| 1 | 2023-06-16 | OPEN | — | warm-up | no | no |
| 2 | 2023-06-17 | CLOSED | — | warm-up | no | no |
| 3 | 2023-06-18 | CLOSED | — | warm-up | no | no |
| 4 | 2023-06-19 | OPEN | 0 | baseline | yes | yes |
| 5 | 2023-06-20 | OPEN | 1 | misinformation | yes | yes |
| 6 | 2023-06-21 | OPEN | 2 | persistence; no new misinformation dose | yes | yes |
| 7 | 2023-06-22 | CLOSED | — | world-only interval | no | no |
| 8 | 2023-06-23 | CLOSED | — | world-only interval | no | no |
| 9 | 2023-06-24 | CLOSED | — | world-only interval | no | no |
| 10 | 2023-06-25 | CLOSED | — | world-only interval | no | no |
| 11 | 2023-06-26 | OPEN | 3 | correction + immediate judgement | yes | yes |
| 12 | 2023-06-27 | OPEN | — | post-correction world interval | no | no |
| 13 | 2023-06-28 | OPEN | 4 | later post-correction | yes | yes |

Participant-critical dates are all five judgement dates:

```text
2023-06-19
2023-06-20
2023-06-21
2023-06-26
2023-06-28
```

Controlled misinformation and correction remain participant-only. The 2023-06-21 persistence checkpoint keeps the already released misinformation available but does not inject a second dose.

## 8. N20/N30 exact-horizon selection gate

All 100 predeclared activation seeds were run through the full 14-tick horizon with Phase 4 activation-state carry-forward.

N20 is sufficient only if:

1. trajectories containing at least one zero-active outcome on the five participant-critical dates are `<= 5 / 100`;
2. every participant-critical date has mean active Agents `>= 3.0`;
3. bounded membership and activation-state continuity remain valid.

Decision:

```text
N20 passes → select N20 by parsimony.
N20 fails + N30 passes → N30 candidate; run one narrow real-backend N30 validation on 2023-06-20.
Both fail → stop and revisit population adequacy contract; do not seed-fish.
```

Exact-horizon zero-LLM result:

```text
N20: PASS
critical-date any-zero trajectories = 4/100
minimum critical-date mean active = 3.88
overall mean active = 4.0364

N30: PASS
critical-date any-zero trajectories = 0/100
minimum critical-date mean active = 6.67
overall mean active = 6.6671
```

Therefore the frozen Phase 10 population is:

```text
N = 20
```

N20 satisfies the predeclared adequacy gates, so parsimony applies. N30 real-backend validation is not required. Existing N20 Phase 9 real-backend evidence remains the real Agent/forum/belief/market evidence. A full paid Phase 9 rerun is not required.

## 9. Phase 10 patch boundary

This patch adds only:
- this audit;
- machine-readable `protocol_v1.json`;
- protocol validation;
- exact-horizon zero-LLM N20/N30 gate;
- canonical read-only `StockData.close_price` provider boundary;
- tests and non-formal preflight runner.

It does not add:
- Phase 11 stimulus delivery;
- source cues;
- frontend state API;
- canonical Agent-world generation;
- new matching/price logic;
- inherited core changes.

## 10. Phase 10 freeze result

The zero-LLM horizon validation also confirmed:

- protocol OPEN/CLOSED states exactly match inherited `trading_days.csv:pretrade_date` for all 14 ticks;
- `sorted_impact_news.pkl` contains exactly one daily row for every protocol date;
- source Agent DB hash is unchanged by the preflight;
- no LLM/API calls, market execution, forum mutation, or participant data were used.

Phase 10 therefore freezes:

```text
T_init    = 2023-06-15
T_visible = 2023-06-19
T_end     = 2023-06-28
world ticks = 14
participant checkpoints = 5
final Agent N = 20
shadow price = sealed canonical StockData.close_price, exact stock/date
```

Phase 11 may now implement controlled participant-only stimulus delivery against this contract without redesigning the time/world model.
