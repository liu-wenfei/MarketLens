# Phase 10 — Long-Horizon Interval Comparison Patch

## Purpose

This patch adds a **zero-LLM, non-formal design-impact comparison** for longer participant behavioural trajectories:

- 11 decision days → 5 OPEN transitions per phase → 4 intermediate behavioural points per phase
- 13 decision days → 6 OPEN transitions per phase → 5 intermediate behavioural points per phase
- 15 decision days → 7 OPEN transitions per phase → 6 intermediate behavioural points per phase
- 17 decision days → 8 OPEN transitions per phase → 7 intermediate behavioural points per phase

It does **not** modify `marketlens/experiment/protocol_v1.json`, does not select a final protocol, does not call an LLM, and does not use participant outcomes.

## Dependency

This patch deliberately builds on the already-applied Phase 10 Decision-Day Design Impact patch and imports its deterministic calendar / activation evaluation helpers.

## New files only

- `marketlens/experiment/long_horizon_design.py`
- `scripts/preflight/run_phase10_long_horizon_interval_comparison.py`
- `tests/marketlens/experiment/test_long_horizon_design.py`
- `PHASE10_LONG_HORIZON_INTERVAL_COMPARISON_README.md`

No TwinMarket core file is touched.

## What the experiment records

For each candidate it records:

- exact participant decision dates;
- OPEN transitions per phase;
- intermediate behavioural-only points per phase;
- correction date and later J4 date;
- elapsed simulated calendar days from misinformation to correction;
- elapsed simulated calendar days from correction to J4;
- inclusive participant-visible simulated calendar span;
- CLOSED ticks within each phase;
- total canonical Agent-world ticks from `T_init`;
- 5 formal judgements + behavioural decision submissions as a participant-response burden proxy;
- exact background-news coverage;
- N20/N30 activation adequacy under the existing 100 predeclared seeds;
- expected active-Agent calls per episode as a zero-LLM workload proxy.

`calendar days` here are **simulated** days, not real participant wall-clock delay.

## Run

```bash
python3 -m pytest \
  tests/marketlens/experiment/test_long_horizon_design.py \
  -q

python3 \
  scripts/preflight/run_phase10_long_horizon_interval_comparison.py
```

Artifacts are written under:

```text
artifacts/preflight/phase10/<timestamp>_<commit>_phase10_long_horizon_interval/
├── summary.json
├── report.md
└── long_horizon_comparison.csv
```

## Interpretation boundary

This comparison can reject a candidate for structural or engineering inadequacy (for example incomplete news coverage or failure of the predeclared activation gate). It must **not** choose an interval because it produces a stronger misinformation/correction effect. Human fatigue and actual completion time belong to later participant-flow pilot evidence.
