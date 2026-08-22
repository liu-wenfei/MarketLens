# MarketLens Phase 7B — Inherited Dynamic Market/News Integration

**Status:** DEVELOPMENT IMPLEMENTATION / NOT FORMAL EXPERIMENT FREEZE

## Rule for this phase

> **Call TwinMarket. Do not reimplement TwinMarket market logic.**

MarketLens Phase 7B adds only orchestration, validation, isolation and audit
boundaries around inherited TwinMarket functions.

### Inherited functions called directly

```python
trader.utility.init_system(...)
trader.matching_engine.test_matching_system(...)
trader.matching_engine.update_profiles_table_holiday(...)
```

The following remain fully inherited and are **not** reproduced in MarketLens:

- closing-price calculation;
- order matching;
- synthetic-liquidity behaviour;
- StockData update mathematics;
- TradingDetails writes;
- Profiles cash/position/return updates;
- non-trading-day Agent-state evolution.

## Human isolation

```text
Agent decision      → inherited matching engine       YES
Participant trade   → inherited matching engine       NO

Participant trade   → participant-only portfolio      YES
Participant state   → Agent Profiles/StockData        NO
```

This package imports no participant service/database module.

## News

MarketLens only loads the exact TwinMarket daily news list and passes the list
through unchanged. It does not rank, summarise, truncate, top-k, rewrite or
interpret news.

Direct news use remains an inherited Agent behaviour and will be connected to
Phase 6 dynamic `top_user` state in the later Phase 7 real-backend gate.

## What this first Phase 7B gate proves

- wrappers delegate to the inherited market functions using their existing
  call signatures;
- reset/mutation functions can be guarded against protected source paths;
- daily TwinMarket news is loaded without reduction;
- Phase 7 MarketLens-owned code contains no SQL market mutation or price/matching
  implementation;
- no participant module is used;
- no LLM/API is required for this gate.

## Not yet executed in this package

This first local gate does **not** run a paid Agent day and does not yet enable
multi-day forum propagation.

After the narrow tests pass, the next gate is a temporary-copy, no-LLM inherited
market mutation preflight. Only after that passes should dynamic top-user + news
be connected to the real Agent reasoning pipeline.
