# MarketLens Phase 5A — Inherited TwinMarket Reasoning Adapter

## Status

**ENGINEERING INTEGRATION ONLY / ZERO REAL-BACKEND EVIDENCE / NOT FORMAL EXPERIMENT EVIDENCE**

Phase 5A connects the already-frozen Phase 4 activation result to TwinMarket's
inherited single-Agent reasoning entry point.  It does **not** run a paid API
preflight and does **not** claim that the real backend has been validated.

## Why this layer exists

Inherited TwinMarket already owns the Agent reasoning pipeline:

`simulation.process_user_input(...) -> PersonalizedStockTrader -> input_info(...)`

MarketLens must reuse that pipeline rather than recreate prompts or strategy
logic.  Phase 5A therefore provides a thin gate:

`Phase 4 ActivationBatch -> active_agent_ids -> inherited process_user_input(...)`

Only activated Agents are delegated.  Inactive Agents never enter the inherited
reasoning call path.

## Frozen Phase 5A controls

Every delegated call forces:

- `day_1st=True`
- `prob_of_technical=0.0`
- `top_user=[]`
- `import_news=[]`

The `prob_of_technical=0.0` constraint disables TwinMarket's random Technical
trader shortcut.  Therefore an activated Fundamental or Technical Agent is kept
on the inherited reasoning path rather than being silently replaced by a random
Technical decision.

Dynamic top-user/social-network semantics are Phase 6.  Controlled market/news
context is Phase 7.  Phase 5A accepts only a minimal `graph_scaffold` required by
the inherited function signature and does not calculate prominence.

## Important ID-normalisation compatibility rule

In the audited inherited database, `Profiles.user_id` is stored as TEXT while
`Strategy.user_id` is stored as INTEGER.  TwinMarket's own `init_simulation`
normalises `df_strategy["user_id"]` to string before calling
`process_user_input`.  Phase 5A reproduces that behavior on a **copy** of the
provided strategy DataFrame.  It does not modify either inherited database.

## What Phase 5A records

One `AgentReasoningExecution` is recorded per activated Agent pipeline.  It
captures whether the inherited 4-tuple returned successfully and whether a
decision/post payload was present.  It does not interpret or repair the
financial output.  Structured decision measurement belongs to a later phase.

One activated Agent means one independently executed TwinMarket Agent pipeline;
it does **not** mean one LLM API call.  The inherited pipeline may make multiple
model calls internally.

## Isolation boundary

The context names its DB paths `working_user_db` and `working_forum_db` on
purpose.  Phase 5B real-backend execution must copy frozen runtime/forum inputs
to a temporary working directory before invoking this adapter.  Phase 5A itself
does not create or mutate those copies because it makes zero real-backend calls.

## Explicitly excluded from Phase 5A

- real OpenAI/LLM/API calls
- backend credentials or API-key handling
- multi-day execution
- forum propagation
- belief propagation/evolution
- dynamic graph construction
- `is_top_user` / source prominence
- live or experimental news
- market-event activation modifiers
- applying Agent decisions to the canonical market trajectory
- participant state or participant trades
- concurrency / throughput optimisation
- structured final-decision schema or repair logic
- formal computational-feasibility evidence

## Tests

The Phase 5A unit tests use an injected fake `process_user_input` callable.  They
verify that:

1. only Phase 4 active IDs are delegated;
2. inactive Agents make zero inherited-pipeline calls;
3. the complete activation mapping is passed for inherited compatibility;
4. Day-1 / no-news / no-top-user / no-random-Technical controls are forced;
5. inherited Strategy IDs are normalised exactly as TwinMarket does;
6. malformed strategy membership fails before delegation;
7. inherited error tuples are recorded without hidden repair/retry calls;
8. an empty active subset produces zero calls;
9. inconsistent activation batches are rejected;
10. the inherited resolver is lazy and performs no execution on import/resolve.

Phase 5B is the next gate: one Agent, one day, isolated working DB copies, real
backend, explicitly labelled **NON-FORMAL / REAL-BACKEND PREFLIGHT**.
