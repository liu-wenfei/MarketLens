# MarketLens Phase 1.1 — Human Backend Round Progression Refinement

## Scope

Phase 1.1 refines the already-validated Phase 1 human backend so that response persistence is no longer responsible for experiment-step progression.

This is required before the multi-asset portfolio phase because one experimental round may later contain one judgement and zero, one, or multiple portfolio orders. All of those actions must remain attached to the same round until the participant explicitly completes it.

Phase 1.1 still does **not** connect to TwinMarket Agents, portfolio settlement, misinformation/correction stimuli, or the frontend.

## API

- `GET /health`
- `POST /session`
- `GET /session/{session_id}`
- `GET /session/{session_id}/state`
- `POST /session/{session_id}/decision`
- `POST /session/{session_id}/round/complete`

## Step ownership

Before Phase 1.1:

```text
submit decision
    -> persist decision
    -> advance current_step
```

After Phase 1.1:

```text
submit decision
    -> persist decision only

complete round
    -> atomically record round completion
    -> advance current_step exactly once
```

This gives Phase 2 a stable contract for multi-order rounds:

```text
step = 3
  judgement
  order 1
  order 2
  order 3
  complete round
step = 4
```

## Persistence

A new append-only `round_completions` table records:

- `completion_id`
- `session_id`
- `request_id`
- `step`
- `next_step`
- `completed_at`

`request_id` makes round completion idempotent. Retrying the same completion request does not advance the participant twice.

Existing Phase 1 SQLite databases remain compatible because Phase 1.1 only adds a new table; it does not rewrite the existing `sessions` or `decisions` tables.

## Run tests

```bash
python3 -m pytest tests/marketlens/human -q
```

## Run backend

```bash
uvicorn marketlens.main:app --reload
```

Then open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## Experimental boundaries preserved

- Human participant data is stored separately from inherited TwinMarket Agent state.
- Participant sessions remain isolated.
- Participant decisions do not mutate TwinMarket.
- Round completion affects only the current human session.
- Participant-visible state does not expose future experiment information.
- Runtime SQLite files remain ignored by Git.

## Temporary Phase 1 conventions

The existing Phase 1 decision schema still validates `BUY`, `HOLD`, or `SELL` and confidence `0–100`. These remain technical placeholders, not the final experimental instrument. Phase 2 portfolio orders will be a separate concept from the Phase 1 judgement record.
