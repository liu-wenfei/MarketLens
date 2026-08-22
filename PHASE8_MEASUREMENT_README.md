# Phase 8 — Thin Agent-world Measurement Facade

**Status:** implementation patch
**Evidence class:** engineering measurement only; not formal experiment evidence
**Baseline:** `phase07-dynamic-twinmarket-market-news-v1.0`

## Purpose

Phase 8 does not add a second measurement simulation.

It provides one read-only JSON facade over outputs that TwinMarket / frozen
MarketLens Phase 3-7 already produced, so Phase 9 can compare candidate Agent
populations using the same observable fields.

## Inherited-first priority

1. Market-open state comes from the authoritative TwinMarket trading calendar.
2. Population / activation / graph / news / reasoning metadata come from the
   existing Phase 7C summary.
3. Agent decision JSON is converted to order semantics by inherited
   `trader.matching_engine.read_json`.
4. Market execution observations come from inherited TwinMarket-generated
   `daily_summary_*.csv`, `transactions_*.csv`, and a read-only runtime DB when
   it is preserved.
5. MarketLens only counts, hashes, combines, and serialises those observations.

No silent replacement parser, matching logic, price formula, liquidity logic,
Agent portfolio updater, or TradingDetails writer is allowed.

If a datum was not preserved by the inherited run, Phase 8 reports it as
`not_observed` / `null`.

## Important market-status rule

Participant trading availability later follows the authoritative market
calendar, not stochastic Agent activity.

```text
market open + zero active Agents       -> market remains open
market open + zero Agent orders        -> market remains open
market open + zero matched executions  -> market remains open
calendar says non-trading day          -> market closed
```

Phase 8 records this status; the participant API gate itself belongs to Phase 13.

## Execution semantics

TwinMarket `transactions_*.csv` contains execution-side rows. A buyer and seller
can therefore produce two execution rows for one economic match.

Phase 8 deliberately reports:

- `transactions.execution_rows`;
- `transactions.execution_quantity_sum`;
- `daily_summary.matched_volume`.

It does **not** rename `execution_rows` to an unqualified `trade_count`.

## Scope

This patch adds only:

```text
marketlens/measurement/
scripts/preflight/run_phase08_measurement.py
tests/marketlens/measurement/
artifacts/preflight/phase08/.gitignore
PHASE8_MEASUREMENT_README.md
```

It must not modify:

```text
Agent.py
simulation.py
trader/
util/
marketlens/agents/
marketlens/market/runtime/
```

## Zero-cost validation

The Phase 8 runner reads an existing Phase 7C artifact. It performs:

```text
0 new LLM calls
0 Agent reasoning calls
0 market executions
0 participant operations
```

Default use:

```bash
python3 scripts/preflight/run_phase08_measurement.py
```

It automatically selects the latest:

```text
artifacts/preflight/phase07/*_phase07_full_chain
```

or an explicit existing run may be supplied:

```bash
python3 scripts/preflight/run_phase08_measurement.py \
  --phase7-run-dir artifacts/preflight/phase07/<RUN>
```

## Exit gate

Phase 8 may be frozen when:

- narrow measurement tests pass;
- existing Phase 7C evidence produces `status: PASS`;
- expected natural N20 observations are recovered (where preserved);
- market-open status agrees with the authoritative calendar;
- participant data is absent;
- no custom market logic is present;
- full regression passes;
- protected diffs are empty;
- working tree is clean after commit.


## v1.1 durable-evidence correction

The first v1.0 measurement run correctly recovered population, activation,
graph, news, market-calendar state and inherited Agent orders, but exposed two
artifact-shape mismatches:

1. frozen Phase 7C stores reasoning under `agent_reasoning`, not `reasoning`;
2. Phase 7C intentionally used/deleted an isolated temporary runtime and did
   not preserve `simulation_results` as durable evidence, while its
   `summary.json` preserved validated market hashes and day-state postconditions.

v1.1 therefore reads those **already-preserved Phase 7C summary fields**.
It does not rerun TwinMarket and does not synthesize missing matched-volume data.

Raw `daily_summary` / `transactions` remain `not_observed` when they were not
preserved. The durable `market_outputs.phase7_summary` reports the validated
Phase 7C market postconditions instead.
