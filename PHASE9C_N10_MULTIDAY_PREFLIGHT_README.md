# Phase 9C — N10 Multi-Day Real-Backend Preflight

**Status:** NON-FORMAL ENGINEERING PREFLIGHT ONLY
**Population:** fixed `N=10`
**Calendar horizon:** fixed `2023-06-15` → `2023-06-17`
**Expected authoritative market state:** `OPEN → OPEN → CLOSED`

## Purpose

Phase 9B proved the zero-LLM sequence contract. Phase 9C now validates the same
short horizon against the real inherited Agent pipeline while keeping the run
bounded and isolated.

This is **not** the final Agent-N comparison and **not** formal experiment
evidence.

## One-click behavior

The script intentionally exposes no `--population-size`, `--start-date`, or
`--end-date` option. v1.0 is hard-limited to N10 and exactly three calendar days.

A single invocation generates its own deterministic N10 Phase-3 fixture, checks
the authoritative calendar/news inputs, carries Phase-4 activation state, and
writes a run summary.

### Zero-cost first pass

```bash
python3 scripts/preflight/run_phase09c_n10_multiday_preflight.py
```

This performs no LLM inference, no market execution, and no forum mutation.
It prints the natural N10 activation schedule so the expected number of inherited
Agent pipeline executions is visible before spending API cost.

### Real-backend preflight

```bash
python3 scripts/preflight/run_phase09c_n10_multiday_preflight.py \
  --execute-real-backend \
  --acknowledge-non-formal
```

The real run requires a clean Git tree and a configured ignored
`config/api.yaml`.

## Delegation contract

Phase 9C reuses:

- frozen Phase 3 population builder (`marketlens.agents.population.runtime_cli`);
- frozen Phase 4 activation policy/sampler;
- Phase 6 bounded graph + deterministic prominence;
- inherited `simulation.process_user_input` per active Agent;
- Phase 7 `advance_trading_day` / `advance_non_trading_day` / reset wrappers;
- inherited `ForumDB` post, action, scoring and belief-reading functions.

It does not implement a matching engine, price formation, Agent portfolio update,
TradingDetails writer, participant→Agent-world pathway, or structured LLM
instrumentation.

## Belief adaptation boundary

The inherited full `simulation.init_simulation()` cannot be used safely because
it enumerates the whole UserDB and owns a separate global activation draw. That
would bypass frozen Phase 3/4.

Therefore Phase 9C contains only the minimum day-level belief orchestration that
mirrors inherited behavior:

```text
Day 1 -> initial belief CSV
Day 2+ -> inherited get_all_users_posts_db(...)
          -> initial-belief fallback only when no usable forum belief exists
```

Forum content itself is read and mutated only through inherited `ForumDB`
functions.

## Natural-coverage rule

No seed fishing is used. A complete `PASS` requires the N10 run to naturally
exercise all of:

- at least one Agent post;
- at least one later-day inherited forum-action call;
- at least one later-day Agent belief actually sourced from ForumDB.

If N10 happens not to produce that natural coverage, the runner records:

`INCONCLUSIVE_NATURAL_FORUM_BELIEF_COVERAGE`

rather than pretending the branch was validated. The next engineering decision
can then be to repeat the same contract at a larger candidate N; the seed should
not be changed merely to force a desired result.

## Important market-status rule

`market_open` is derived only from `data/trading_days.csv`.

An open day remains open even if active Agents, orders, or matched trades happen
to be zero. Matching-engine holiday-style fallback behavior must never be used as
proof that the authoritative market is closed.
