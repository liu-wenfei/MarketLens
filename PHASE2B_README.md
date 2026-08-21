# MarketLens Phase 2B — Participant Trading Engine

## Scope

Phase 2B completes the participant-only trading layer on top of the verified
Phase 2A market/account foundation.

Implemented here:

- free choice among the inherited 10 sector instruments;
- participant portfolio policy: long-only, no leverage, whole units;
- configurable transaction-cost basis points and optional position cap;
- side-effect-free order preview;
- no silent clamp: an infeasible request is returned as invalid with a maximum
  valid amount rather than silently reduced;
- participant BUY funded only from participant cash;
- participant SELL limited to the participant's existing holding;
- one confirmed order changes only the actively selected asset plus cash;
- deterministic exact-date settlement using the session's already-authorised
  `current_date` and the read-only `stock_data.csv` close-price adapter;
- append-only participant portfolio transactions with requested and executed
  values stored separately;
- atomic account + holding + transaction persistence;
- order idempotency using `request_id`;
- 0/1/N confirmed orders may share the same round/step; only the existing
  `/round/complete` endpoint advances the step;
- APIs for asset definitions, participant portfolio, order preview, and order
  confirmation.

## Participant-facing execution assumption

The participant is a price-taking simulated investor. Participant orders settle
against the controlled MarketLens price and affect only that participant's
portfolio. Orders do **not** enter the inherited TwinMarket Agent order book and
cannot change Agent prices, holdings, beliefs, graph state, or another
participant's account.

## Date-authorisation boundary

The portfolio API does not accept a client-supplied trading date. It uses only
`sessions.current_date`. Phase 2B does not decide that date; a later experiment
state layer will authorise and set it. If `current_date` is absent, trading is
rejected rather than falling forward to another market date.

## Engineering defaults, not formal experiment parameters

- development initial cash remains `10000.00` from Phase 2A;
- transaction cost defaults to `0` bps;
- position cap defaults to `None`;
- accounts are long-only, unlevered, whole-unit accounts.

Formal study parameters remain to be frozen later.

## Explicitly out of scope

Phase 2B does **not** add:

- Agent calls or Agent portfolio mutation;
- TwinMarket matching-engine participation or participant market impact;
- bid/ask spread, slippage, market depth, or partial-fill microstructure;
- experiment timeline, misinformation/correction logic, source cues, or
  condition assignment;
- frontend;
- Azure/PostgreSQL migration;
- Sharpe/Sortino analytics, feedback, SESOI/capacity logic, v4.2 session engine,
  Convex, or the legacy 28-round protocol.
