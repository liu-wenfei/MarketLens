# MarketLens Phase 14B3A — Domain Event Recorder Audit

**Status:** BOUNDED IMPLEMENTATION PATCH
**Evidence class:** NON-FORMAL / ZERO-LLM

## Audit conclusion

The Phase 14B3 runtime-boundary audit found that the current backend has reliable authoritative completion records for formal participant judgements and participant portfolio transactions, but two prerequisites for full automatic runtime exposure wiring are still absent:

1. ordinary participant sessions are not yet automatically allocated to a canonical episode; Phase 14B1 only persists an already-chosen binding;
2. controlled stimuli have a frozen `StimulusEngine` and source-cue adapter, but there is no participant-facing controlled-stimulus delivery service/router to which an exposure event can be attached.

Therefore this patch does **not** modify routers or create a stimulus endpoint. It freezes only the safe domain-event recording contract for already-successful authoritative domain writes.

## Recorded semantics

One authoritative `JudgementRead` produces two provenance events referencing the same `judgement_id`:

- `JUDGEMENT_SUBMITTED`
- `CONFIDENCE_RECORDED`

The ledger does not duplicate action, confidence, rationale, or evidence values. Ordinary per-step `DecisionRead` records are not formal J0..J4 measurements and are not the source for these two event types.

One authoritative settled `PortfolioTransactionRead` produces three provenance events referencing the same `transaction_id`:

- `ORDER_SUBMITTED`
- `TRADE_SETTLED`
- `PORTFOLIO_STATE_RECORDED`

The current portfolio domain commits order acceptance, settlement, and post-trade state in one authoritative transaction record, so the ledger must not invent separate order/trade/portfolio source-of-truth rows.

## Replay policy

Event IDs are deterministic UUID5 values derived from:

`session_id + request_id + event_type`

The authoritative domain timestamp is reused as `occurred_at_utc`. This preserves the existing Phase 14A append-only/idempotency contract during retries without weakening event-store validation.

## Explicit non-goals

This patch adds no:

- HTTP/router wiring;
- background exposure logging;
- controlled-stimulus delivery or exposure logging;
- episode allocator;
- formal participant assignment;
- session or portfolio mutation;
- Agent-world/forum mutation;
- LLM/network call.

Full Phase 14B3 remains incomplete until the participant runtime has both a trustworthy automatic episode assignment path and a participant-visible controlled-stimulus delivery boundary.
