# MarketLens Phase 4 — Sparse Heterogeneous Agent Activation

## Status

Phase 4 implements the activation layer only. It does **not** execute inherited
TwinMarket Agent reasoning. The layer consumes a Phase 3B bounded runtime
population and returns the Agent IDs that are allowed to enter the later
reasoning pipeline.

## Lineage

This design combines two audited sources without copying either execution stack:

1. **Inherited TwinMarket baseline** — retains the original idea that activation
   is an independent stochastic Bernoulli decision per Agent.
2. **Uploaded newer TwinMarket work** — reuses the defensible ideas of
   Agent-specific activity propensity, log-odds adjustment, probability bounds,
   reproducible sampling and no-LLM smoke testing.

MarketLens deliberately removes the later-phase features from that newer policy.
Phase 4 has no market/news/social/participant/LLM inputs.

## Phase 4 activation inputs

Only:

- `user_id`
- inherited `trade_count_category` (`低`, `中`, `高`)
- `steps_since_last_activation`
- explicit engineering configuration
- `seed` and `step` for reproducible independent draws

`trade_count_category` is interpreted only as a historical activity propensity.
It is not a correctness, credibility, source-status or strategy signal.

The default baseline probabilities are derived from the inherited 1,000-Agent
source audit. Median observed TradingDetails counts were:

- `低`: 16 trades (332 Agents)
- `中`: 36 trades (371 Agents)
- `高`: 80 trades (297 Agents)

Those medians are scaled to a source-population weighted mean baseline activation
probability of `0.20`, producing explicit development defaults in `policy.py`.
They are **engineering defaults, not frozen formal experimental parameters**.

## Formula

For Agent `i` at step `t`:

```text
p_base(i) = baseline[trade_count_category(i)]
recency   = min(steps_since_last_activation / reference_steps, 1)
score     = logit(p_base) + recency_weight * recency
p_active  = clamp(sigmoid(score), p_min, p_max)
active    = seeded_agent_step_draw < p_active
```

The draw is keyed by `seed | step | user_id`, so it is reproducible and does not
depend on iteration order.

## Explicit exclusions

Phase 4 does not use or implement:

- `user_type`
- `is_top_user`
- source-status quotas / exposure floors
- strategy-specific call quotas
- profit / return / performance-based selection
- participant decisions or trades
- market price movement
- news events
- social triggers / graph state / forum state
- beliefs
- LLM inference
- inherited `simulation.process_user_input(...)`

Contextual market/news/social modifiers may be added in later phases only after
those environments exist and are validated.

## Phase boundary

```text
Phase 3 bounded runtime population
        ↓
Phase 4 activation layer
        ↓
active_agent_ids
        ↓
Phase 5 inherited TwinMarket reasoning integration
```

An inactive Agent remains a member of the frozen population and is eligible for
activation again on the next step. In Phase 5, inactive Agents should not enter
the LLM reasoning path at all.
