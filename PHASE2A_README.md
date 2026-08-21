# MarketLens Phase 2A — Asset Sources and Participant Account Foundation

## Scope

Phase 2A adds only the read-only market-data adapters and the participant-only
account foundation needed by the later portfolio gates.

Implemented here:

- read `data/stock_profile.csv` as the authoritative 10-instrument asset catalog;
- interpret the inherited `weight` field as `market_weight`, never as a
  participant portfolio weight;
- read exact-date close prices from `data/stock_data.csv`;
- add a small `AccountState` value object derived from the audited v4.2 account
  concept, without importing its protocol engine;
- create one participant portfolio row per MarketLens session;
- create an empty holdings table for later settlement;
- keep accounts isolated by `session_id`;
- preserve all Phase 1.1 behaviour.

The development initial cash is `10000.00`. It is an engineering default only,
not a frozen experimental parameter.

## Explicitly out of scope

Phase 2A does **not** add:

- BUY / SELL / HOLD execution;
- order preview;
- target-only settlement;
- multi-order round handling;
- transaction persistence;
- transaction fees, position caps, leverage, or short-selling policy;
- portfolio API endpoints;
- Agent calls, Agent portfolios, matching-engine integration, or market impact;
- rumour/correction logic, experiment timeline, source cues, frontend, Azure, or
  PostgreSQL migration.

Those remain later gates. The inherited TwinMarket core must remain unchanged.

## Data-source boundary

`AssetCatalog` and `CsvClosePriceProvider` are read-only adapters. The price
provider performs exact-date lookup only. It does not choose the participant's
allowed experiment date and intentionally provides no "latest" fallback. The
experiment-state layer will own date authorisation later.
