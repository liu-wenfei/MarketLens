# MarketLens Phase 3A — Population Source + Deterministic Selection

Phase 3A answers one question only: **which inherited TwinMarket Agent IDs are selected for one bounded MarketLens population?**

This patch intentionally stops before runtime-fixture construction. Phase 3B will later turn the already-validated selected IDs into a TwinMarket-compatible bounded runtime database and final population manifest.

## Frozen Phase 3A scope

Included:

- open `data/sys_1000.db` read-only;
- verify required TwinMarket tables exist;
- require exactly one `Profiles` row and one `Strategy` row per Agent;
- require `Profiles.strategy == Strategy.strategy`;
- validate inherited persona fields and `user_type` presence;
- verify `TradingDetails` contains no orphan Agent IDs;
- hash the source database before/after validation to prove it was not modified;
- select without replacement using deterministic strategy-stratified sampling;
- preserve the source strategy ratio as closely as integer N permits using largest-remainder apportionment;
- use only `user_id`, `strategy`, and the explicit `seed` as selection inputs;
- inherit `user_type` from whichever real personas are selected;
- return stable selected IDs and a SHA256 hash of the selected-ID set.

Explicitly excluded from Phase 3A:

- creating `population_runtime.db`;
- copying `Profiles`, `Strategy`, `TradingDetails`, `StockProfile`, or `StockData` into a new database;
- final population manifest / runtime-fixture hash;
- Agent activation;
- LLM inference;
- belief state;
- social graph or `is_top_user`;
- forum state;
- market/news trajectory;
- misinformation/correction stimuli;
- participant-visible source-status rules;
- formal population-size feasibility or final-N freeze.

## Selection policy

The algorithm is:

`sha256_keyed_strategy_stratified_selection/1.0`

1. Validate the inherited source population.
2. Calculate the required Fundamental/Technical counts for N from the source proportions.
3. Within each strategy stratum, rank candidates by `sha256(seed|stratum|user_id)` with stable `user_id` tie-breaking.
4. Take the required number from each stratum without replacement.

The current inherited source contains 400 `基本面` and 600 `技术面` Agents. For example, N=20 therefore allocates 8 `基本面` and 12 `技术面` Agents.

`user_type` is **not** a quota or selection key. It remains exactly the value attached to each selected inherited persona. Do not repeatedly change the seed until a preferred 大V/小博主/普通股民 composition appears; doing that would indirectly turn `user_type` into a selection criterion.

## Final N is not frozen

`population_size` remains an explicit parameter. Phase 3A freezes the selection mechanism, not the formal experimental N. Final population-size feasibility is a later phase.

## Expected validation

Run:

```bash
python3 -m pytest tests/marketlens/agents -q
```

On the audited `data/sys_1000.db`, this Phase 3A patch contributes 6 Agent-population tests. If the preceding MarketLens baseline has 66 tests, the combined total should therefore be 72 tests.

The inherited TwinMarket core and source data must remain unchanged:

```bash
git diff -- Agent.py simulation.py trader/ util/
git diff -- data/sys_1000.db data/stock_profile.csv data/stock_data.csv
```

Both commands should produce no output.
