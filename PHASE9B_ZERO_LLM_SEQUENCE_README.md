# Phase 9B — Zero-LLM Sequential Orchestration Gate

**Status:** NON-FORMAL ENGINEERING GATE
**Real backend:** NO
**LLM/API calls:** 0
**Market execution:** NO
**Formal experiment evidence:** NO

## Purpose

Phase 9B validates only the new part of the multi-day architecture:

> sequential calendar-day orchestration around already-frozen MarketLens and
> inherited TwinMarket boundaries.

It does not create a second simulation engine.

## Existing components used first

```text
marketlens.market.runtime.news.load_trading_day_set
marketlens.market.runtime.news.load_daily_news

marketlens.agents.activation.profiles.load_activation_profiles
marketlens.agents.activation.policy.ActivationPolicy
marketlens.agents.activation.sampler.sample_activation

marketlens.market.runtime.inherited_market.advance_trading_day
marketlens.market.runtime.inherited_market.advance_non_trading_day
```

The Phase 9B CLI uses the read-only calendar/news/activation components only.
The market dispatcher is unit-tested with injected callables and is reserved for
the later real-backend gate.

## Three-calendar-day engineering horizon

```text
2023-06-15   open
2023-06-16   open
2023-06-17   closed
```

The state model is explicitly based on **calendar days**, matching inherited
TwinMarket day progression.

For each day Phase 9B records:

- current Agent-world date;
- previous-day history cutoff;
- market-open state from `trading_days.csv`;
- future participant-trading availability;
- initial vs forum-derived belief-source contract;
- whether the inherited Day-2+ forum-action stage is enabled;
- daily background-news count;
- frozen Phase 4 active IDs;
- activation-state input/output digest;
- expected Phase 7 market wrapper.

No fixed `19 news items/day` assumption exists.

## Permanent market rule

```text
market_open
← authoritative trading calendar
```

Never:

```text
market_open
← active Agent count
← Agent order count
← matched executions
```

Therefore an open day remains open even when Agent activity is zero.

## What is deliberately deferred

Phase 9B does not claim:

- multi-day LLM reasoning;
- real forum propagation;
- real belief-content propagation;
- market mutation;
- Profiles/StockData/TradingDetails continuity;
- graph changes caused by new TradingDetails;
- final Agent N.

Those are Phase 9C/9D/9E responsibilities.

## Run

```bash
python3 scripts/preflight/run_phase09b_zero_llm_sequence.py \
  --runtime-db artifacts/preflight/phase05b/dev_population_n20/population_runtime.db \
  --trading-calendar data/trading_days.csv \
  --news-pickle data/sorted_impact_news.pkl \
  --start-date 2023-06-15 \
  --end-date 2023-06-17
```

Expected evidence class:

```text
NON-FORMAL / ZERO-LLM SEQUENTIAL ORCHESTRATION GATE
```

The source runtime DB, trading calendar, and news pickle must remain unchanged.
