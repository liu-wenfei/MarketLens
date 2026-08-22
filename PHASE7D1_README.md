# MarketLens Phase 7D-1 — Inherited Matched-Trade Coverage Gate

**Status:** NON-FORMAL ENGINEERING PREFLIGHT / NOT FORMAL EXPERIMENT EVIDENCE

This gate covers one branch that the natural Phase 7C full-chain run did not
exercise: a real matched Agent trade inside the inherited TwinMarket matching
engine.

It intentionally uses a deterministic, audited two-order fixture on an isolated
copy of the already-bounded N20 Agent runtime:

- date: `2023-06-15`
- stock: `CGEI`
- buyer: `22543333014`
- seller: `25901251490`
- buy price = sell price = `9.75`
- quantity = `100`

The fixture was selected read-only from the N20 development runtime. The buyer
has sufficient cash and the seller has sufficient CGEI holdings before the test.
Equal buy/sell quantity prevents TwinMarket's inherited imbalance-liquidity
copying branch from being needed for this gate.

## What this gate is for

It proves that, on an isolated bounded runtime copy, MarketLens can delegate an
inherited-shape Agent decision JSON to the existing Phase 7B wrapper, which in
turn calls TwinMarket `trader.matching_engine.test_matching_system(...)`, and
that the inherited engine can produce:

- a matched CGEI trade;
- `TradingDetails` rows for the real buyer and seller;
- the next dated `Profiles` state with corresponding inherited cash/holding
  changes;
- the next dated `StockData` state.

## What this gate does **not** prove

- It is not natural Phase 4 activation evidence.
- It does not call an LLM/API.
- It does not test dynamic top-user news routing.
- It is not formal experiment evidence.
- It does not add or replace any TwinMarket market mechanism.

The controlled price/quantity arithmetic in the script is used only as a
postcondition assertion. It is never used to update market state.
