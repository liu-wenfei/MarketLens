# Phase 11 — Controlled Stimulus Engine Audit & Contract

**Status:** IMPLEMENTATION CANDIDATE — DEVELOPMENT MATERIAL ONLY — NOT FORMAL STIMULUS FREEZE
**Evidence class:** PHASE 11 ENGINEERING / ZERO-LLM / NOT FORMAL EXPERIMENT EVIDENCE

## 1. Scope

Phase 11 adds one participant-only controlled-information layer on top of a sealed canonical TwinMarket state. It does not generate or mutate the Agent world.

TwinMarket remains responsible for Agent reasoning, natural news, forum/belief dynamics, graph/prominence, OPEN/CLOSED progression, matching and price formation. Phase 11 does not reimplement or wrap those algorithms.

## 2. Decisions frozen in this contract

1. **No new participant behavioural parameter is introduced.** Phase 10 v1.1 remains the sole source of truth for the 15 BUY/SELL/HOLD decision checkpoints, quantities, portfolio recording, five formal judgements and their timing.
2. Controlled misinformation and correction are **participant-only**. They must never be written to Agent ForumDB, Agent prompts, Profiles, TradingDetails, StockData or matching input.
3. The abandoned legacy `RumorInjector` / forum-post injection architecture is not reused.
4. Phase 11 material does **not duplicate calendar dates**. It declares semantic release events only:
   - misinformation: `after_J0_before_J1`
   - correction: `after_J2_before_J3`
   Exact dates are resolved from the frozen Phase 10 v1.1 timeline.
5. Manipulation checkpoints are same-state contrasts. A caller must explicitly request pre- or post-release visibility on experiment step 0 and step 7; an ambiguous default request fails closed.
6. Misinformation is released once, remains available throughout the persistence phase, and remains as a historical item after correction.
7. Correction is added at the J2/J3 checkpoint, explicitly links to the misinformation item, and remains available through J4.
8. Participant payloads use an allow-list. Internal hashes, material status and manifest metadata are not rendered to participants.
9. Source identity, authority badges, verification visuals and other source cues are **out of Phase 11 scope** and reserved for Phase 12.
10. Formal stimulus content is not generated live. Runtime material is immutable and hash-verified. Formal mode fails closed unless material is marked `formal_frozen` and hashes validate.
11. `formal_frozen` is an engineering material-freeze state, not a claim of ethics approval or expert validation.

## 3. New Phase 11 parameters

These are stimulus/material parameters only, not participant-behaviour parameters:

- `stimulus_set_id`
- `material_version`
- `protocol_version`
- `target_stock_id`
- `formal_use_status`
- per-item `stimulus_id`
- per-item `kind`
- per-item `headline`
- per-item `body`
- per-item semantic `release_event`
- correction `corrects_stimulus_id`
- per-item `content_sha256`
- `manifest_sha256`

No `release_date`, Agent ID, forum poster, account count, social-proof variable or source-cue presentation field is permitted in Phase 11 material.

## 4. Visibility contract under Phase 10 v1.1

| Experiment step | Date from Phase 10 | Moment | Controlled material visible |
|---:|---|---|---|
| 0 | 2023-06-19 | before misinformation | none |
| 0 | 2023-06-19 | after misinformation | misinformation |
| 1–6 | Phase 10 dates | checkpoint | misinformation |
| 7 | 2023-06-30 | before correction | misinformation |
| 7 | 2023-06-30 | after correction | misinformation + correction |
| 8–14 | Phase 10 dates through J4 | checkpoint | misinformation + correction |

No additional participant response is created by stimulus exposure itself.

## 5. New code

- `marketlens/stimulus/schema.py` — immutable schema and forbidden-field guards.
- `marketlens/stimulus/manifest.py` — canonical content/manifest hashing.
- `marketlens/stimulus/material.py` — hash verification, protocol binding and formal-mode fail-closed loading.
- `marketlens/stimulus/engine.py` — Phase-10-driven visibility state machine and participant allow-list payload.
- `data/marketlens/stimuli/stimulus_v1.development.json` — synthetic development-only fixture; explicitly not formal participant material.
- `scripts/preflight/run_phase11_stimulus_contract_preflight.py` — zero-LLM truth-table/isolation preflight.
- `tests/marketlens/stimulus/*` — schema, hash, visibility and dependency-isolation tests.

## 6. Explicitly not implemented in Phase 11

- formal misinformation/correction wording selection or expert review;
- source-cue presentation (Phase 12);
- participant-visible canonical-state assembly and market gating (Phase 13);
- exposure/measurement logging (Phase 14);
- frontend rendering (Phase 15);
- any Agent-world mutation or controlled-stimulus feedback into TwinMarket.

## 7. Current freeze boundary

This patch freezes the **engine contract**, not the final formal stimulus content. The development JSON must remain rejected by `formal=True`. A later bounded material-freeze step can replace/add a reviewed formal material file without changing the Phase 11 engine semantics.
