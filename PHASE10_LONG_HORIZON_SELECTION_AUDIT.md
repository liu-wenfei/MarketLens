# Phase 10 — Long-Horizon Methodological Selection Audit

**Evidence class:** NON-FORMAL / ZERO-LLM DESIGN-SELECTION RECORD / NOT FORMAL EXPERIMENT EVIDENCE
**Protocol status:** methodological selection completed; incorporated by the subsequent Protocol v1.1 amendment after N30 real-backend PASS.

## Frozen methodological selection made before paid N30 validation

The long-horizon comparison was outcome-blind and compared `11/13/15/17`
participant decision days. No participant behaviour and no LLM-generated market
content was used to select a candidate.

The selected long-horizon candidate is:

```text
participant decision days = 15
OPEN transitions per phase = 7
intermediate behavioural-only points per phase = 6
formal judgement events = 5
formal judgement dates = 3
T_init = 2023-06-15
T_visible = 2023-06-19
J0/J1 = 2023-06-19
J2/J3 = 2023-06-30
J4 = 2023-07-11
misinformation -> correction = 11 simulated calendar days
correction -> later J4 = 11 simulated calendar days
visible simulated span = 23 calendar days inclusive
canonical Agent-world horizon = 27 calendar ticks
```

The 15-decision design is selected because it gives a symmetric `11 / 11`
simulated-calendar-day structure around the correction checkpoint, preserves
`7 / 7` OPEN-state transitions, and provides six intermediate behavioural
observations per phase. The 17-decision design adds only one intermediate point
per phase while losing calendar-span symmetry (`14 / 10` days) and increasing
participant/simulation burden.

This does **not** imply 15 decisions will create a larger misinformation or
correction effect. The selection is structural and methodological only.

## Population implication

The existing Phase 10 activation-adequacy gates remain unchanged:

```text
trajectories with any zero-active participant-critical date <= 5/100
minimum mean active on every participant-critical date >= 3.0
```

For the selected 15-decision / 27-tick horizon:

```text
N20: 9/100 critical-any-zero, minimum mean active 3.88 -> FAIL
N30: 0/100 critical-any-zero, minimum mean active 6.26 -> PASS (zero-LLM)
```

Therefore N20 is not retained by changing the gate. N30 becomes the candidate
formal population size and must receive a bounded real-backend feasibility
validation before the Phase 10 v1.1 protocol amendment is frozen.

## Paid-validation boundary

The N30 real-backend validation must **not** execute the full 27-tick formal
horizon. It is a bounded engineering gate only:

```text
population = fixed same-seed N30 candidate
population seed = marketlens-dev-population-01
activation reference seed = marketlens-phase09b-activation-01
calendar = 2023-06-15 .. 2023-06-17
market states = OPEN / OPEN / CLOSED
expected active Agents = 10 / 7 / 3
expected Agent pipeline executions = 20
```

No seed-fishing, membership substitution, forced activation, participant data,
custom matching, custom price formation, or alternative forum/belief logic is
permitted.

A non-PASS result is evidence to diagnose, not permission to retry with a more
convenient seed.

## Completed N30 validation

The single bounded N30 real-backend validation was subsequently executed once on clean commit `8b4704b` and returned `PASS`. The fixed activation sequence remained `10 / 7 / 3` across `OPEN / OPEN / CLOSED`; natural coverage included 20 posts, 25 Agents observed through ForumDB belief sourcing, and 10 later-day forum-action calls. Runtime/forum continuity and bounded N30 graph checks PASSed.

The selection therefore proceeds to Protocol v1.1 with `15` decision days and formal `N30`; no further paid N30 feasibility run is required.
