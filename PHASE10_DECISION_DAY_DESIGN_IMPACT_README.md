# Phase 10 — Decision-Day Design Impact Experiment

**Evidence class:** NON-FORMAL / ZERO-LLM DESIGN-IMPACT EVIDENCE / NOT FORMAL EXPERIMENT EVIDENCE

## Purpose

Compare behavioural decision-day counts `0 / 2 / 4 / 7 / 9 / 11` without using participant outcomes, LLM content, or outcome-driven protocol selection.

This experiment does **not** modify the frozen Phase 10 protocol. It produces decision-support evidence for a possible later protocol amendment.

## Two comparison views

### A. Fixed-horizon cadence-only comparison

All six decision counts are placed over the same 11-OPEN-day comparison horizon using an endpoint-preserving, approximately-even, outcome-agnostic sampling rule.

This isolates the effect of **behavioural sampling density**:

- number of BUY/SELL/HOLD submissions;
- formal-anchor coverage;
- intermediate behavioural observations per phase;
- largest unobserved OPEN-state gap;
- number of unobserved OPEN states;
- participant response-event burden proxy.

`0` decisions still retains the five formal judgement events. It means **no behavioural BUY/SELL/HOLD observations**, not no participant interaction.

### B. Symmetric dynamic-window family

Only `7 / 9 / 11` are treated as symmetric dynamic-trajectory candidates:

- 7 decisions = 3 OPEN transitions per phase = 2 intermediate behavioural points per phase;
- 9 decisions = 4 OPEN transitions per phase = 3 intermediate behavioural points per phase;
- 11 decisions = 5 OPEN transitions per phase = 4 intermediate behavioural points per phase.

Here the participant makes a behavioural decision on every participant-visible OPEN date, so denser designs also extend the canonical Agent-world horizon.

The experiment reports:

- exact calendar mapping;
- world ticks;
- CLOSED ticks inside the participant-visible interval;
- background-news coverage;
- N20/N30 activation adequacy using the same 100 predeclared Phase 10 seeds;
- expected active-Agent calls per canonical episode as a zero-LLM workload proxy.

## Metrics for dissertation explanation

- `decision_days`: number of OPEN simulated dates requiring BUY/SELL/HOLD.
- `decision_fraction`: share of common OPEN states with a behavioural observation.
- `formal_anchor_coverage`: whether behaviour is observed at J0/J1, J2/J3, and J4 dates.
- `phase1_intermediate_points` / `phase2_intermediate_points`: behavioural-only observations between formal measurement anchors.
- `max_gap_open_transitions`: largest unobserved behavioural gap measured in OPEN-state transitions.
- `unobserved_open_states`: OPEN states without a participant behavioural decision.
- `participant_response_events`: five formal judgement events plus behavioural decision submissions. This is a burden proxy, not measured wall-clock time.
- `world_ticks`: calendar Agent-world generation required by the candidate.
- `expected_active_agent_calls_per_episode`: `overall mean active Agents × world ticks`; a workload proxy, not an API invoice.
- `critical-zero trajectories`: number of the 100 predeclared activation trajectories with at least one zero-active outcome on candidate decision dates.
- `minimum decision-date mean active`: lowest mean active-Agent count across candidate decision dates.

## Interpretation boundary

The comparison can justify statements about:

- information density of the behavioural trajectory;
- structural coverage of formal manipulation anchors;
- participant response burden proxy;
- canonical-world computational workload;
- activation adequacy.

It cannot justify statements that one decision-day count produces a larger misinformation/correction effect, lower fatigue, or better participant experience. Those require methodological judgement and later participant-flow pilot evidence.

## Run

```bash
python3 scripts/preflight/run_phase10_decision_day_design_impact.py
```

Outputs are written under:

```text
artifacts/preflight/phase10/<timestamp>_<commit>_phase10_decision_day_design/
├── summary.json
├── report.md
├── cadence_only_comparison.csv
└── symmetric_dynamic_family.csv
```
