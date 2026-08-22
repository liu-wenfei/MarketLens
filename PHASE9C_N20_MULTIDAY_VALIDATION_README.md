# Phase 9C — N20 Three-Day Real-Backend Validation

**Status:** NON-FORMAL ENGINEERING VALIDATION
**Population:** existing verified N20 development fixture
**Calendar:** 2023-06-15 → 2023-06-17
**Formal experiment evidence:** NO

## Why N20

The N10 dry-run was valid but naturally produced `0 / 2 / 0` active Agents over
OPEN / OPEN / CLOSED. That is useful feasibility evidence but too sparse to
validate the full natural multi-day propagation path.

This N20 validation does not search for a better seed. It reuses the exact N20
Phase 9B deterministic trajectory that was observed before choosing N20 for
paid validation: `5 / 3 / 3`.

## Population integrity

The runner reuses the already-verified development fixture and checks its known
runtime/manifest hashes before execution. It does not regenerate or truncate a
population. N20 remains provisional; this does not freeze the final formal N.

## Delegation

The runner reuses Phase 9B calendar/activation sequencing, Phase 6 graph and
prominence, inherited `simulation.process_user_input`, Phase 7 market wrappers,
and inherited ForumDB functions. No custom market/forum/belief algorithm is
introduced.

## Dry run

```bash
python3 scripts/preflight/run_phase09c_n20_multiday_validation.py
```

Expected Agent pipeline executions: 11 (5 + 3 + 3). This is not an HTTP-call
count; one inherited Agent pipeline may make multiple backend requests.

## Real backend

```bash
python3 scripts/preflight/run_phase09c_n20_multiday_validation.py \
  --execute-real-backend \
  --acknowledge-non-formal
```

The real run requires a clean Git working tree.

A real PASS requires natural post creation, later-day ForumDB belief usage,
later-day inherited forum actions, an active closed-day Agent, continuous
runtime/forum state, bounded daily graphs, no reasoning failure, and unchanged
protected sources.
