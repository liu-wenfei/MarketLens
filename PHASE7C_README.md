# Phase 7C — One-day TwinMarket full-chain preflight

**Status:** NON-FORMAL engineering preflight only.

This layer does not implement a MarketLens market. It wires the already-frozen
MarketLens population, activation and social-graph layers into the inherited
TwinMarket reasoning and market transition for **one day only**.

## Executed chain

```text
Phase 3 bounded N20 runtime
  -> inherited Phase 6 social graph (history through 2023-06-14)
  -> deterministic dynamic top-user IDs
  -> Phase 4 natural activation (explicit seed; no resampling)
  -> complete 2023-06-15 TwinMarket daily-news list
  -> inherited simulation.process_user_input() for active Agents only
  -> exact user_id -> decision_result JSON
  -> Phase 7B advance_trading_day()
  -> inherited trader.matching_engine.test_matching_system()
  -> isolated TwinMarket Agent-world StockData / TradingDetails / Profiles state
```

## Hard boundaries

- One date only: `2023-06-15`.
- History cutoff: `2023-06-14`.
- `day_1st=True`.
- `prob_of_technical=0.0`; activated Technical Agents still execute independent
  inherited reasoning instead of the random shortcut.
- The source Phase 3 runtime DB is never mutated; all market mutation happens on
  a temporary copy.
- Participant state is never read and participant decisions are never sent to
  TwinMarket matching.
- Agent decisions **are** sent to the inherited Agent-market matching system.
- The full daily news list is supplied unchanged to every active inherited
  pipeline. TwinMarket still controls direct news reading through its inherited
  role-dependent/top-user behaviour.
- No forum action execution or multi-day belief/forum propagation is enabled.
- No Phase 8 misinformation/correction stimulus is injected here.
- No custom MarketLens price formation, order matching, Agent portfolio update,
  StockData writer, TradingDetails writer or Profiles writer exists here.

## Important coverage note

With the already-used development activation seed
`marketlens-phase05b-activation-01`, the natural active subset may contain no
Phase 6 dynamic top user. That is **not** a reason to resample or change seed.
The full-chain run remains valid for natural activation/market integration, but
`top_user_direct_news_branch_exercised` will be false. If needed, a separately
labelled forced-one-top-user routing gate should be run later without using its
decision as natural market evidence.

## Passing condition

A PASS requires all naturally active Agents to finish inherited reasoning,
strictly serializable inherited decision JSON, the inherited market call to
advance the temporary DB, exactly one `StockData` row per bounded stock on
2023-06-15, exactly one `Profiles` row per bounded Agent on 2023-06-15, and all
protected source inputs to retain their original SHA256 values.

`TradingDetails` is allowed to remain zero because valid Agent decisions can
still produce no matched orders; TwinMarket then advances the date using its
inherited fallback behaviour.
