# MarketLens Phase 6B — Bounded Social Graph and Dynamic Prominence

**Status:** DEVELOPMENT IMPLEMENTATION / NOT FORMAL EXPERIMENT FREEZE

This layer deliberately **wraps rather than rewrites** TwinMarket's inherited graph
construction.

## What is inherited unchanged

MarketLens calls `simulation.build_graph_new(...)`, which resolves to the inherited
TwinMarket graph builder. MarketLens does not copy or reimplement:

- historical `TradingDetails` loading;
- industry aggregation;
- exponential time decay;
- weighted-Jaccard similarity;
- similarity-threshold edge creation;
- inherited node attributes;
- inherited isolated-node repair.

## What MarketLens adds

The wrapper adds only research-control and reproducibility boundaries:

1. the graph is built from the Phase 3 bounded runtime database;
2. an explicit `history_cutoff` is required;
3. inherited graph saving is forced off (`save=False`);
4. graph membership must exactly equal the bounded `Profiles` population;
5. the runtime database SHA256 must be unchanged before/after construction;
6. `top_n` is derived from the actual graph size, not an independent `node` argument;
7. prominence keeps inherited **unweighted degree**;
8. ties are resolved deterministically by normalized `user_id` ascending;
9. a reproducible snapshot records graph/prominence metadata.

## Development defaults

These follow TwinMarket's inherited `init_simulation()` path and are not yet formal
experiment parameters:

- graph start date: `2023-01-01`
- similarity threshold: `0.1`
- time-decay factor: `0.05`
- top fraction: `0.10`

## Explicitly out of scope

Phase 6B does **not**:

- call an LLM/backend;
- pass `is_top_user` into `process_user_input`;
- enable top-user `_read_news()` behaviour;
- enable multi-day forum propagation;
- change Phase 4 activation;
- use `user_type` to derive prominence;
- expose prominence as a participant-facing credibility cue;
- modify inherited TwinMarket core files.

The Phase 6A audit found that passing graph-derived `is_top_user` into the inherited
reasoning pipeline would also activate role-dependent news handling. That integration
is intentionally deferred to Phase 7.

## Core API

```python
from marketlens.agents.social import build_bounded_social_graph, make_prominence_snapshot

built = build_bounded_social_graph(
    runtime_db="artifacts/preflight/phase05b/dev_population_n20/population_runtime.db",
    history_cutoff="2023-06-14",
)

snapshot = make_prominence_snapshot(
    built,
    top_fraction=0.10,
)
```

## N20 development preflight

No API key or real backend is required:

```bash
python3 scripts/preflight/run_phase06_graph_snapshot.py \
  --runtime-db artifacts/preflight/phase05b/dev_population_n20/population_runtime.db \
  --population-manifest artifacts/preflight/phase05b/dev_population_n20/population_manifest.json \
  --history-cutoff 2023-06-14
```

The output is an engineering preflight snapshot under:

```text
artifacts/preflight/phase06/<run_id>/summary.json
```

It is not formal experiment evidence.
