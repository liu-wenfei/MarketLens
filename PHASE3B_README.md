# MarketLens Phase 3B — Freeze + TwinMarket Runtime Fixture

Phase 3B consumes the **already frozen Phase 3A selection mechanism** and turns one explicit `(N, seed)` selection into an auditable bounded TwinMarket runtime input.

## Scope

Phase 3B includes only:

- calling the committed Phase 3A selector; Phase 3B does not implement or alter selection policy;
- writing `selected_agent_ids.txt` for the exact selected membership;
- writing `population_manifest.json` with source hash, selection algorithm/seed/N, selected-ID hash, strategy counts, inherited `user_type` counts, joint counts, and coverage warnings;
- creating `population_runtime.db` in the inherited TwinMarket UserDB shape;
- filtering `Profiles`, `Strategy`, and `TradingDetails` to selected Agents only;
- copying `StockProfile` and `StockData` unchanged;
- verifying source immutability and content digests;
- verifying inherited `util.UserDB.get_all_user_ids(...)` sees exactly the bounded membership.

Phase 3B explicitly excludes:

- any change to Phase 3A selection policy;
- Agent activation;
- LLM inference;
- beliefs;
- social graph / `is_top_user`;
- forum generation;
- news/market trajectory control;
- misinformation/correction stimuli;
- participant-visible source-cue rules;
- formal population-size feasibility or final-N freeze.

## 3A / 3B boundary

Phase 3A owns **who is selected**. Its selector uses only `user_id`, strategy, and the explicit seed, with strategy stratification and inherited `user_type`.

Phase 3B owns **how that exact membership is frozen into a TwinMarket-compatible runtime artifact**. The core `build_runtime_fixture(...)` function receives selected Agent IDs and does not make membership decisions.

The convenience bundle builder calls the Phase 3A selector once using the explicit `(N, seed)` and then immediately freezes that result. There is no second selection algorithm in Phase 3B.

## Output bundle

A provisional bundle contains:

```text
population_manifest.json
selected_agent_ids.txt
population_runtime.db
```

`population_runtime.db` contains:

```text
Profiles        selected Agents only
Strategy        selected Agents only
TradingDetails  inherited history for selected Agents only
StockProfile    unchanged
StockData       unchanged
```

The runtime fixture intentionally remains SQLite because it is a frozen TwinMarket input artifact, not the MarketLens participant/research application database. The latter remains behind the SQLAlchemy/PostgreSQL portability boundary.

## `user_type`

`user_type` remains inherited and descriptive. Phase 3B reports missing source-status categories as warnings and never replaces selected Agents to force a 大V/小博主/普通股民 quota.

## Final N

Phase 3B still does **not** freeze the final formal population size. Bundles are labelled:

`PROVISIONAL / DEVELOPMENT / NOT FORMAL POPULATION FREEZE`

Formal N is selected later using the dedicated feasibility stage, then the same Phase 3A + 3B mechanism can regenerate and freeze the final population.

## Development example

```bash
python3 -m marketlens.agents.population.runtime_cli \
  --source-db data/sys_1000.db \
  --population-size 20 \
  --seed marketlens-dev-population-01 \
  --output-dir /tmp/marketlens-agent-population-n20
```

Do not commit ad-hoc development population bundles as formal evidence.
