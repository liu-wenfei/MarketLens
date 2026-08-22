# MarketLens Phase 5B — Isolated One-Day Real-Backend Preflight

**Status:** `NON-FORMAL / REAL-BACKEND PREFLIGHT / NOT FORMAL EXPERIMENT EVIDENCE`

Phase 5B adds no new market, social, participant, or measurement mechanism. It
exists only to prove that the committed Phase 5A adapter can drive the inherited
TwinMarket reasoning pipeline against the configured real backend while keeping
all writable state isolated from frozen inputs.

## Frozen scope

Phase 5B has one runner and two gates:

1. **Gate 5B-1 — one Agent × one day × real backend**
   - the requested Agent must already belong to the Phase 3B bounded population;
   - the runner builds a transparent **forced one-Agent preflight gate**;
   - this is deliberately not described as a stochastic Phase 4 sample.
2. **Gate 5B-2 — Phase 4 active subset × one day × real backend**
   - the same runner uses the committed Phase 4 sampler with one explicit seed;
   - zero activations are recorded as `NO_ACTIVE_AGENTS`;
   - the runner never changes/resamples the seed to manufacture coverage.

Both gates delegate through:

```text
Phase 5B runner
    -> Phase 5A execute_activation_batch(...)
    -> inherited simulation.process_user_input(...)
    -> inherited PersonalizedStockTrader / input_info
    -> configured real backend
```

No parallel execution is introduced here.

## Day-1 context boundary

Engineering preflight only:

- current date: `2023-06-15`
- inherited previous-profile date: `2023-06-14`
- `StockData` passed to TwinMarket is filtered to `<= 2023-06-14`
- `day_1st=True`
- `prob_of_technical=0.0`
- `top_user=[]`
- `import_news=[]`
- graph = all bounded Agent nodes, **zero edges**
- forum = a fresh, empty DB created with inherited `util.ForumDB.init_db_forum`
- initial belief = inherited Day-1 belief CSV, read-only; missing belief for an
  executing Agent fails closed

Therefore Phase 5B does **not** validate dynamic graph/top-user behaviour, news,
forum propagation, belief propagation, or multi-day Agent state.

## Population provenance

Real execution requires both:

- a Phase 3B `population_runtime.db`; and
- its paired `population_manifest.json`.

The runner verifies the runtime SHA-256 and exact Agent membership against the
manifest before any inherited reasoning is allowed. `data/sys_1000.db` is not a
valid direct Phase 5B runtime input.

## Storage boundary

Source inputs are read-only. For each run:

```text
Phase 3B population_runtime.db
    -> temporary runtime.db copy

fresh inherited forum schema
    -> temporary forum.db
```

The temporary writable DBs are deleted after a successful run.

Persistent non-formal artifacts are written below:

```text
artifacts/preflight/phase05b/<run_id>/
├── summary.json
├── agents/
│   └── <user_id>.json
└── inherited_logs/
    └── conversation_records/    # only if TwinMarket produced them
```

`artifacts/preflight/phase05b/.gitignore` ignores generated run directories.
Git tracks the runner/tests/README, not paid model outputs.

By default a failed temporary workspace is also deleted. It can be copied into
that run's `debug_workspace/` only with the explicit
`--preserve-failed-workspace` flag.

### What is intentionally not stored

- participant sessions / decisions / portfolios;
- PostgreSQL human-research data;
- `config/api.yaml` contents or API keys;
- a new MarketLens per-call raw prompt/response logger;
- temporary runtime/forum DBs after success.

TwinMarket's own conversation records may be preserved unchanged as inherited
engineering logs. They are not yet the structured Agent measurements defined for
later phases.

## Safety controls

The CLI refuses paid execution unless **both** flags are supplied:

```text
--execute-real-backend
--acknowledge-non-formal
```

It also requires a clean Git worktree and records `git rev-parse HEAD` in
`summary.json`. Real execution should therefore happen only **after this Phase
5B code is committed**.

The runner never applies returned Agent decisions to market prices, never
executes returned forum actions, and never accesses participant state.

## Local test gate — zero backend calls

Before committing Phase 5B:

```bash
python3 -m pytest tests/marketlens/agents/test_phase05b_preflight.py -q
python3 -m pytest tests/marketlens/agents -q
python3 -m pytest tests/marketlens/human tests/marketlens/market tests/marketlens/agents -q
```

The tests inject a fake `process_user_input` callable. They do not import or
contact a real model backend.

## Deliberately deferred

- Phase 6 dynamic graph / `is_top_user`
- Phase 7 controlled market/news environment
- multi-day forum/belief/state propagation
- Phase 11 formal experiment logging schema
- Phase 12 structured Agent measurement
- Phase 13 population-size/computational feasibility evidence
- formal experiment freeze
