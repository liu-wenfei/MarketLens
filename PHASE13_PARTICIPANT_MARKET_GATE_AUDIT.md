# Phase 13A — Participant-Visible Market Status and Trading Gate Audit

## Status

Candidate engineering contract. This is not formal experiment evidence and is not yet a frozen Phase 13 tag.

## Audit scope

Phase 13 was audited against:

1. frozen original TwinMarket baseline `de5f2446fcba0d0aba533a6adaede034160e29b4`;
2. the legacy extended TwinMarket ZIP / Bridge implementation;
3. current MarketLens human backend and Phase 9/10 contracts.

## Reuse findings

### Reuse directly

- TwinMarket protected `data/trading_days.csv` remains the only market-calendar source.
- Trading-day semantics remain the inherited / frozen `pretrade_date` semantics.
- Phase 9 already contains `marketlens.market.runtime.news.load_trading_day_set`, but importing that helper from the human API currently executes the eager `marketlens.market.runtime.__init__`, which imports the inherited matching runtime. Pulling that dependency chain into the participant API would violate the desired isolation and would require reopening frozen Phase 7 packaging. Phase 13A therefore uses a tiny read-only adapter over the same protected file/column semantics rather than a second calendar dataset or a Phase 7 refactor.
- Phase 9 already froze the rule that participant trading availability depends on calendar status only, not Agent activation, order count, or matched trades.
- Existing MarketLens participant portfolio preview/settlement/persistence remains participant-only and is reused unchanged except for the new calendar authorization gate.
- Existing exact-date `CsvClosePriceProvider` remains the execution-price provider.

### Reference only; do not restore

Legacy `bridge/state_reader.py` is useful evidence for a read-only participant state path, but it mixes old translation and old rumour-era filtering and must not be restored wholesale.

Legacy `bridge/settlement_engine.py::get_next_trading_day` demonstrates the same `pretrade_date` semantics, but the old Path-B runtime jumps from one trading day to the next and treats closed days as profile-fill intervals. That conflicts with the frozen MarketLens world-tick contract, where closed calendar days remain real Agent-world ticks. It is therefore reference-only.

Legacy `run_with_human.py` monkeypatches inherited Agent runtime and makes the human a simulated Agent. That violates the current price-taking participant boundary and is not reusable.

### Original TwinMarket baseline

The original baseline has no Bridge / participant API layer. It does provide the authoritative calendar and the inherited open-vs-closed market branch:

- OPEN -> inherited matching path;
- CLOSED -> inherited holiday profile-update path.

Phase 13 must expose that state to participants without modifying those inherited branches.

## Gap in current MarketLens

Before Phase 13A:

- `/session/{id}/state` exposes step/date/status only;
- participant preview/order fails on some closed dates only indirectly because no exact-date price exists;
- there is no explicit authoritative market-status reason, closure interval, or next trading date;
- closed-day portfolio review with non-empty holdings fails because the current calendar date has no close-price row.

Indirect "no price" rejection is not an acceptable market-closure gate.

## Phase 13A contract

Expose from the session state:

- `market_open`;
- `market_status_reason`;
- `current_market_date`;
- `next_trading_date` when closed;
- `closure_start_date` / `closure_end_date` when closed;
- `participant_trading_enabled`;
- `market_state_date` (last sealed OPEN state used only for passive display on a closed day).

### Market-status reason

The inherited CSV can identify whether a date is in the trading calendar, but it does not reliably encode a participant-safe causal classification such as "weekend" versus "public holiday" for this API contract.

Therefore the candidate reason is deliberately generic:

- OPEN: `scheduled_trading_day`
- CLOSED: `scheduled_non_trading_day`
- no authorised date yet: `market_date_unavailable`

Do not claim a specific holiday cause unless a separate authoritative source is frozen later.

## Trading gate

For a new participant preview/order:

```text
session.current_date
    -> protected TwinMarket calendar
    -> participant_trading_enabled
```

If false:

- preview is rejected;
- order is rejected;
- no participant transaction is created;
- participant cash is unchanged;
- participant holdings are unchanged;
- no Agent matching function is invoked;
- Agent state is untouched.

The gate has no Agent-activity input.

## Closed-day portfolio review

Closed-day passive review and execution pricing are intentionally separate.

- Execution: exact current OPEN date only; no forward-fill, nearest-date, or previous-date fallback.
- Passive portfolio display on CLOSED day: value holdings using the previous sealed OPEN market-state date, while exposing that date explicitly as `price_date` / `market_state_date`.

This does not authorize an order on the closed date.

## Phase 13B deliberately not included here

Participant-visible Agent/forum/background-information projection remains a separate Phase 13B audit/patch because the legacy Bridge mixed:

- translation;
- old rumour injection markers;
- old scenario logic;
- raw ForumDB fields such as belief/type/score.

Phase 13B must first freeze a participant-safe allow-list and the language/translation policy for inherited Agent posts. It should directly reuse inherited ForumDB reads, Phase 12 `user_type` source cues, Phase 11 controlled stimulus visibility, and Phase 12 controlled source cues rather than restoring the old Bridge.

## Permanent invariants

- Participant trades remain shadow-only.
- Participant orders never enter TwinMarket matching.
- OPEN remains OPEN even with zero active Agents / zero Agent orders / zero matched trades.
- Phase 10 timing is unchanged.
- Phase 11 stimulus text is unchanged.
- Phase 12 source cues are unchanged.
- No new participant behavioural parameter is introduced.
