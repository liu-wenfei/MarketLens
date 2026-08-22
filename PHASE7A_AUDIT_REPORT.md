# MarketLens Phase 7A Audit Report v2.0

**Phase:** 7A — Dynamic TwinMarket Market/News Environment
**Date:** 22 August 2026
**Status:** **AUDIT COMPLETE / CONTRACT READY TO FREEZE**
**Implementation rule:** **CALL INHERITED TWINMARKET FUNCTIONS; DO NOT REIMPLEMENT MARKET LOGIC**

---

## 1. Final architectural decision

MarketLens will preserve TwinMarket's dynamic Agent-market feedback loop.

The canonical Agent world is allowed to evolve through inherited TwinMarket market mechanics:

```text
bounded Agents
→ sparse activation
→ inherited Agent reasoning
→ Agent orders
→ inherited TwinMarket matching
→ StockData update
→ TradingDetails update
→ Profiles update
→ next-step graph / prominence / reasoning
```

The human participant remains isolated:

```text
participant judgement/trade
→ participant-only state

participant action
-X→ TwinMarket Agent market
```

Therefore the corrected invariant is:

> **Participant decisions must never alter the Agent world. Agent decisions retain TwinMarket's inherited ability to alter the simulated Agent-market state.**

---

## 2. Non-negotiable Phase 7 implementation rule

MarketLens Phase 7 must not implement a parallel market engine.

### MarketLens MUST NOT add

- a new closing-price formula;
- a new order matcher;
- a new liquidity-balancing rule;
- a new Agent cash/holdings update algorithm;
- a new TradingDetails writer;
- a new Profiles evolution algorithm;
- a new holiday-market update formula;
- a new news-interpretation path.

### MarketLens MAY add only

- orchestration;
- bounded-runtime selection;
- date/step control;
- active-Agent routing;
- dynamic `top_user` routing from Phase 6;
- input/output validation;
- participant-isolation guards;
- temporary-workspace isolation;
- audit metadata and hashes;
- fail-closed checks.

If an inherited TwinMarket function cannot safely be called, implementation must stop and document why before any adaptation is proposed.

---

## 3. Inherited daily execution chain

TwinMarket's `simulation.py` imports and calls:

```python
from trader.matching_engine import (
    test_matching_system,
    update_profiles_table_holiday,
)
from trader.utility import init_system
```

The inherited daily path is:

```text
init_system(...)
        ↓
load daily StockData/news/trading day
        ↓
process_user_input(...)
        ↓
write daily Agent decision JSON
        ↓
if trading day:
    test_matching_system(...)
else:
    update_profiles_table_holiday(...)
        ↓
forum actions / next date
```

MarketLens should reproduce this orchestration selectively around the already-integrated Phase 3–6 layers rather than calling the whole `init_simulation()` blindly.

---

## 4. `init_system()` — inherited destructive reset boundary

`trader.utility.init_system()` deletes state on or after the chosen start date from:

- `Profiles`
- `StockData`
- `TradingDetails`

and also clears future forum state.

This is useful and correct for starting/restarting a TwinMarket trajectory, but it is **destructive**.

### Phase 7 decision

**CALL INHERITED `init_system()` only on an isolated writable runtime/forum copy.**

Never call it on:

- `data/sys_1000.db`;
- the Phase 3 source database;
- a participant database;
- any frozen evidence artifact.

Phase 7 should preserve the Phase 5 preflight principle of writable temporary runtime copies.

No MarketLens replacement reset routine is required.

---

## 5. `test_matching_system()` — inherited market mutation boundary

`test_matching_system(...)` is the main inherited trading-day entry point.

It:

1. reads `StockData` and `StockProfile`;
2. reads the daily decision JSON;
3. converts valid Agent decisions into orders;
4. generates stock/order data;
5. runs `process_trading_day(...)`;
6. updates market and Agent state;
7. falls back to holiday-style updates if no usable decisions exist.

### Phase 7 decision

**CALL `test_matching_system()` directly.**

Do not call its internal matching subfunctions from MarketLens unless a narrowly documented test requires it.

This keeps TwinMarket's own call sequence authoritative.

---

## 6. Inherited closing-price mechanism

`calculate_closing_price(...)`:

- requires both buy and sell sides to trade;
- sorts buy orders by descending price then time;
- sorts sell orders by ascending price then time;
- considers candidate order prices;
- computes executable volume at each candidate;
- selects the first price achieving the maximum executable volume;
- returns the previous close with zero volume when the sides cannot match.

This is inherited TwinMarket price formation.

### Phase 7 decision

**KEEP unchanged by calling `test_matching_system()` rather than reimplementing it.**

---

## 7. Inherited synthetic liquidity / order replication

Before matching, `process_daily_orders(...)` checks buy/sell quantity imbalance.

When the stronger side is at least 2.5 times the weaker side, TwinMarket may copy orders from the weaker side, up to three copies, using synthetic user ID `ZYF`.

This is part of the inherited market mechanism.

### Phase 7 decision

**KEEP unchanged.**

MarketLens must not add, remove, tune, or replace this mechanism in Phase 7.

The behaviour should be documented as an inherited simulation assumption, not presented as a real exchange mechanism.

---

## 8. Important inherited limitation: ±10% code is not enforced

`calculate_closing_price(...)` computes:

```python
upper_limit = last_price * 1.1
lower_limit = last_price * 0.9
```

but the visible implementation does not use these values to filter the candidate prices or final `best_price`.

Therefore the source comments/docstring claim a ±10% price-limit constraint that the actual algorithm does not visibly enforce.

### Phase 7 decision

**DO NOT fix this in Phase 7.**

Reason:
- fixing it would alter inherited market logic;
- the user explicitly wants TwinMarket market behaviour preserved;
- Phase 7 is integration, not market-model redesign.

Record it as a **known inherited limitation**.

Do not claim in the dissertation that the current inherited execution strictly enforces the ±10% limit unless later source/tests demonstrate otherwise.

---

## 9. `StockData` evolution

When a stock has a simulated trading result, TwinMarket uses the matched closing price and derives price change / percentage change from the previous simulated close.

When a stock has no simulated result, TwinMarket uses the real historical market percentage change to evolve the previous simulated price.

It then derives valuation metrics relative to the real daily reference and inserts a new `StockData` row, including moving averages and volume statistics.

Therefore TwinMarket is a **hybrid dynamic market**:

```text
Agent-driven matching where simulated orders produce a result
+
historical-market anchoring where they do not
```

### Phase 7 decision

**KEEP unchanged through inherited calls.**

Do not create a MarketLens fallback-price rule.

---

## 10. `TradingDetails` evolution

`update_trading_details_table(...)` writes executed Agent trades to `TradingDetails`:

- user ID;
- date;
- industry;
- stock ID;
- execution price;
- stock name;
- direction;
- executed volume;
- valid flag.

Synthetic `ZYF` liquidity orders are excluded from this Agent historical table.

This matters because Phase 6's graph is built from `TradingDetails`.

Thus the inherited system naturally creates:

```text
Day t trades
→ TradingDetails
→ Day t+1 graph
→ dynamic prominence
```

### Phase 7 decision

**KEEP unchanged.**

No MarketLens TradingDetails writer should be added.

---

## 11. `Profiles` evolution

`update_profiles_table(...)` updates the Agent-world financial state from executed transactions.

The inherited implementation adjusts:

- cash;
- positions;
- market value;
- total value;
- position ratios;
- returns;
- followed industries;
- next dated `Profiles` state.

### Phase 7 decision

**KEEP unchanged.**

No MarketLens Agent portfolio/state calculator should be added.

This is distinct from the already-built **participant-only portfolio engine**, which remains isolated.

---

## 12. Non-trading/empty-decision evolution

When no usable decisions exist, `test_matching_system()` invokes inherited holiday-style updates.

`update_stock_data_table_holiday(...)` still advances market prices using real historical percentage changes.

`update_profiles_table_holiday(...)` creates the next dated Agent profile state without normal trading execution.

### Phase 7 decision

**CALL inherited fallback functions through `test_matching_system()` where possible.**

For explicitly non-trading days, use TwinMarket's inherited `update_profiles_table_holiday()` path consistent with `simulation.py`.

Do not invent a MarketLens holiday rule.

---

## 13. News loading and direct consumption

`simulation.py` loads:

```text
data/sorted_impact_news.pkl
```

and selects the current date's news list.

The complete list is passed into the inherited Agent pipeline.

TwinMarket direct news processing remains role-dependent:

```text
dynamic `is_top_user`
→ inherited `_read_news()`
```

### Phase 7 decision

**KEEP inherited news interpretation and role routing.**

MarketLens may validate and supply the daily list but must not:

- summarise it;
- top-k it;
- re-rank it;
- rewrite it;
- interpret it in a new MarketLens prompt.

---

## 14. Phase 6 → Phase 7 integration

Phase 6 deliberately stopped before supplying real dynamic prominence into the Agent reasoning path because `is_top_user` triggers inherited news handling.

Phase 7 is the correct point to connect:

```text
Phase 6 deterministic top_user IDs
+
daily TwinMarket news
+
Phase 4 active IDs
        ↓
Phase 5 inherited process_user_input(...)
```

### Phase 7 decision

**ENABLE this routing without changing TwinMarket's Agent prompt/news code.**

---

## 15. Participant isolation

Participant actions must never be written into:

- daily Agent decision JSON consumed by `test_matching_system()`;
- Agent `Profiles`;
- Agent `TradingDetails`;
- Agent `StockData`;
- forum DB;
- Agent belief state.

Participant trades remain entirely inside the MarketLens participant portfolio layer.

### Hard invariant

```text
Agent decision → inherited matching engine    YES
Participant trade → inherited matching engine NO
```

---

## 16. Canonical world meaning

For MarketLens, "canonical Agent world" does **not** mean "externally frozen price series."

It means:

> one bounded, controlled Agent world whose state evolves according to inherited TwinMarket dynamics and is never changed by human participant actions.

The world is dynamic internally:

```text
Agent → market → Agent → graph → Agent
```

while human participants are read-only observers of that world except for their own isolated judgement/portfolio state.

---

## 17. Multi-session caution

A live dynamic Agent world must not be duplicated implicitly per participant unless the formal experimental design explicitly wants participant-specific worlds.

Otherwise independent LLM stochasticity could create different market worlds.

This is a later orchestration/deployment decision, not a reason to alter TwinMarket market logic.

### Phase 7 decision

**DEFER final live-world/session scheduling policy.**

Phase 7 validates the Agent-world dynamics first.

---

## 18. What Phase 7B is allowed to implement

Phase 7B should be an orchestration layer, not a market layer.

Recommended responsibilities:

```text
prepare isolated writable Agent runtime/forum
        ↓
call inherited init_system(...)
        ↓
for step/date:
    load/validate current TwinMarket market + news
    obtain Phase 6 graph/top_user
    obtain Phase 4 active subset
    call Phase 5 inherited reasoning
    write decision artifact in inherited expected shape
    call inherited test_matching_system(...)
    verify inherited DB state advanced
```

No alternative price or state-update logic should exist in this wrapper.

---

## 19. Recommended code boundary

A thin MarketLens owner layer may be added, for example:

```text
marketlens/market/runtime/
├── __init__.py
├── inherited_market.py
└── models.py

tests/marketlens/market/
├── test_inherited_market_calls.py
└── test_agent_world_isolation.py

scripts/preflight/
└── run_phase07_inherited_market.py

PHASE7B_README.md
```

`inherited_market.py` should mainly adapt paths/inputs and CALL:

```python
trader.utility.init_system(...)
trader.matching_engine.test_matching_system(...)
trader.matching_engine.update_profiles_table_holiday(...)
```

It must not contain any price-formation mathematics.

---

## 20. Required tests before any paid run

### Call-delegation tests
Verify the MarketLens wrapper calls inherited functions with the correct:

- date;
- bounded runtime DB;
- isolated forum DB;
- inherited decision JSON path;
- output/log path.

### Anti-reimplementation tests
Source-level test or review should verify Phase 7 MarketLens-owned code does not define:

- `calculate_closing_price`;
- `process_daily_orders`;
- Agent position/cash update formulas;
- custom StockData/TradingDetails/Profile SQL writes.

### Isolation tests
Verify participant stores/services are not imported or called by the Agent-market runtime.

### Mutation-scope tests
On temporary DB copies, verify expected inherited tables may change:

- `StockData`
- `TradingDetails`
- `Profiles`

while source/frozen runtime fixtures remain unchanged.

---

## 21. Phase 7 local preflight sequence

Before a real LLM run:

```text
A. inherited market call smoke test using synthetic decision JSON
B. bounded temporary DB one-day mutation audit
C. no-participant-import audit
D. news/top-user routing unit tests
E. full MarketLens regression
```

These tests should exercise actual inherited TwinMarket functions wherever possible.

---

## 22. Phase 7 real-backend gate

After local execution passes:

```text
bounded development population
→ one trading day
→ Phase 4 natural activation
→ Phase 6 dynamic top users
→ real TwinMarket daily news
→ inherited Agent reasoning
→ inherited decision JSON
→ inherited test_matching_system()
→ inspect StockData / TradingDetails / Profiles changes
```

This run remains:

> **NON-FORMAL / REAL-BACKEND PREFLIGHT / NOT FORMAL EXPERIMENT EVIDENCE**

Do not seed-fish active Agents.

If a top-user branch must be explicitly validated and the natural active set contains no top user, use a separately labelled routing gate rather than changing the activation seed.

---

## 23. Known inherited limitations to preserve/document, not fix now

1. ±10% limit variables are calculated but not visibly enforced in `calculate_closing_price()`.
2. synthetic `ZYF` order replication is an inherited liquidity mechanism.
3. market prices are hybrid: Agent-matched for represented orders, real-return anchored otherwise.
4. `test_matching_system()` writes output artifacts as part of its inherited behaviour.
5. the inherited full simulation loop couples later forum behaviour; Phase 7 integration should keep forum propagation separately gated until multi-day validation.

---

## 24. KEEP / CALL / DEFER / FORBID table

| Component | Phase 7 decision |
|---|---|
| `process_user_input()` | **CALL / KEEP** |
| `init_system()` | **CALL on isolated copy** |
| `test_matching_system()` | **CALL / KEEP** |
| inherited matching algorithm | **KEEP unchanged** |
| inherited price formation | **KEEP unchanged** |
| inherited synthetic liquidity | **KEEP unchanged** |
| inherited `StockData` update | **KEEP unchanged** |
| inherited `TradingDetails` write | **KEEP unchanged** |
| inherited `Profiles` update | **KEEP unchanged** |
| inherited holiday update | **KEEP unchanged** |
| inherited news handling | **KEEP unchanged** |
| Phase 6 top-user routing | **CONNECT** |
| Phase 4 activation | **KEEP unchanged** |
| participant → matching engine | **FORBID** |
| participant → Agent DB | **FORBID** |
| custom MarketLens matching logic | **FORBID** |
| custom MarketLens price formula | **FORBID** |
| custom MarketLens Agent portfolio logic | **FORBID** |
| fix inherited ±10% issue now | **DEFER** |
| multi-day forum propagation | **DEFER** |
| formal live-world/session policy | **DEFER** |
| misinformation/correction stimulus | **DEFER to Phase 8** |

---

## 25. Phase 7A final status

```text
Phase 7A inherited market source audit        COMPLETE
Matching/state-update call boundaries          VERIFIED
Participant isolation requirement              FROZEN
"No custom market logic" rule                 FROZEN
Phase 7B implementation                        NOT STARTED
```

### Final contract

> **MarketLens Phase 7 will orchestrate the existing TwinMarket dynamic market; it will not reproduce, simplify, replace, or "improve" TwinMarket's market mechanics.**

The MarketLens contribution in this layer is limited to safe composition:

```text
bounded runtime
+ sparse activation
+ dynamic prominence
+ controlled date/news routing
+ participant isolation
+ auditability
```

The market itself remains TwinMarket.
