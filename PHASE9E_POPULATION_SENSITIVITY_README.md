# Phase 9E — N10 / N20 / N30 / N40 Zero-LLM Population Sensitivity

**Evidence class:** NON-FORMAL ENGINEERING FEASIBILITY  
**LLM/API calls:** 0  
**Market execution:** NO  
**Forum mutation:** NO  
**Participant data:** NO  
**Final N frozen:** NO

## Fixed comparison

The population grid is fixed before seeing Phase 9E results:

```text
N10 / N20 / N30 / N40
```

All four use the already-established Phase 3 population seed:

```text
marketlens-dev-population-01
```

N20 is required to reproduce the already-verified Phase 3/5 population and
runtime hashes used by the successful Phase 9C real-backend validation.

## Activation sensitivity

The frozen Phase 4 activation policy is evaluated using **all 100**
predeclared deterministic seeds:

```text
marketlens-phase09e-activation-000
...
marketlens-phase09e-activation-099
```

No result is removed and no "best" seed is selected.

Every seed uses the same three-calendar-day horizon:

```text
2023-06-15 OPEN
2023-06-16 OPEN
2023-06-17 CLOSED
```

The existing Phase 9B activation seed is also evaluated as a reference; N20
must still reproduce `5 / 3 / 3`.

## Structural comparison

Every fixture receives the same Phase 6 baseline graph snapshot:

```text
graph start = 2023-01-01
history cutoff = 2023-06-14
threshold = 0.1
time decay = 0.05
top fraction = 0.10
```

The output compares strategy composition, naturally inherited `user_type`,
membership nesting, graph edges/density/degrees/components, top-user count,
activation density, zero-active risk, closed-day activity and expected
active-Agent workload.

`user_type` is never quota-repaired. Dynamic top-user status remains graph
prominence rather than credibility or correctness.

## Run

After tests pass and the code is committed:

```bash
python3 scripts/preflight/run_phase09e_population_sensitivity.py
```

The runner requires a clean Git tree and creates:

```text
artifacts/preflight/phase09/
<timestamp>_<commit>_phase09e_population_sensitivity/
├── population_fixtures/
│   ├── n10/
│   ├── n20/
│   ├── n30/
│   └── n40/
├── summary.json
└── report.md
```

## Decision boundary

Phase 9E does **not** automatically freeze a final N.

The key review is:

```text
N20 → N30
N30 → N40
```

Are reductions in zero-active risk or gains in graph/source structure large
enough to justify the additional expected active-Agent workload?

Active-Agent-days are a zero-LLM workload proxy only and are not converted
into an invented HTTP/backend-call count.

A paid N30/N40 real-backend run is not required unless this comparison reveals
a decision-relevant uncertainty that existing N20 real-backend evidence cannot
resolve.
