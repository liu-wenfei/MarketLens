# Phase 9D — Population and Multi-Day Feasibility Audit

**Evidence class:** NON-FORMAL ENGINEERING FEASIBILITY  
**LLM/API calls:** 0  
**Market execution:** NO  
**Forum mutation:** NO

Phase 9D consolidates the evidence already produced by:

- Phase 9C N10 dry-run;
- Phase 9C N20 dry-run;
- Phase 9C N20 real-backend PASS.

It does **not** rerun the Agent world.

## Why this phase exists

The engineering roadmap requires Phase 9 to answer empirically:

- what Agent N is computationally feasible;
- whether N changes activity / graph / market behaviour;
- whether state propagation works across multiple days;
- what runtime / backend-call cost to expect.

The current evidence is enough to audit N10 vs N20 before deciding whether an
N40 paid run is decision-relevant.

## Conservative evidence rules

The audit:

- uses the exact existing summary artifacts and records their SHA256 hashes;
- keeps exact backend/HTTP call count as unknown because it was not instrumented;
- reports Agent pipeline count and runtime instead of guessing request count;
- keeps N20 as a **current leading candidate**, not a frozen formal N;
- does not infer N40 behaviour from N20;
- recommends a zero-LLM / structural N40 sensitivity check before any paid N40 run.

## Run

```bash
python3 scripts/preflight/run_phase09d_feasibility_audit.py
```

By default it discovers the latest valid directories ending in:

```text
_phase09c_n10_dry
_phase09c_n20_dry
_phase09c_n20_real
```

under:

```text
artifacts/preflight/phase09/
```

You can also pin exact summary paths with:

```bash
python3 scripts/preflight/run_phase09d_feasibility_audit.py \
  --n10-dry-summary <path> \
  --n20-dry-summary <path> \
  --n20-real-summary <path>
```

The output directory contains:

```text
summary.json
report.md
```

## Expected current interpretation

The audit should preserve the observed facts rather than change thresholds
after seeing results:

```text
N10 dry:
0 / 2 / 0 active
2 active Agent-days
2 zero-active days

N20 dry / real:
5 / 3 / 3 active
11 active Agent-days
0 zero-active days

N20 real:
PASS
OPEN / OPEN / CLOSED
natural forum/belief propagation observed
dynamic graph/top-user recomputation observed
closed-day inherited path observed
~23.7 min total wall time
large backend-latency variability observed
```

This supports N20 as the current engineering leader, but the final formal N
remains unfrozen until the remaining Phase 9 comparison decision is closed.
