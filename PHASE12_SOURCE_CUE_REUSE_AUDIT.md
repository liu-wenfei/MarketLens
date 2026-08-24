# Phase 12 Source-Cue Reuse Audit

## Decision

Phase 12 is a **thin participant-facing adapter**, not a second identity, forum, timing, or manifest subsystem.

## Directly reused inherited TwinMarket logic

1. `ForumDB` posts already carry `user_id`; no source field is added to the forum database.
2. `util.UserDB.get_user_profile(user_id, db_path, created_at)` already returns `Profiles.user_type`.
3. The inherited baseline categories are `普通股民`, `小博主`, and `大V`; Phase 12 only translates them for participant display.
4. Dynamic `is_top_user` / graph degree prominence remains separate from stable `user_type` and is never interpreted as credibility.

The participant-side join is therefore:

`Forum post.user_id -> inherited get_user_profile(...) -> profile['user_type'] -> neutral display label`.

## Directly reused MarketLens logic

Controlled-stimulus visibility and wording remain owned by Phase 11. Phase 12 receives only `StimulusEngine.participant_payload(...)` output and attaches two presentation fields. It has no date, experiment-step, or release logic.

## Minimal new logic

Only the following is new:

- Neutral display mapping:
  - `普通股民 -> Individual Investor`
  - `小博主 -> Market Blogger`
  - `大V -> Influential Market Commentator`
- Candidate controlled-stimulus source presentation:
  - misinformation -> `Market News Report` / `Market media report`
  - correction -> `LONGi Green Energy` / `Official company announcement`
- Explicit participant-field allow-list and fail-closed behavior.

## Explicitly not reused

The old fork's `matched_accounts`, Account A/B/C handles, `poster_user_ids`, repeated-rumour social-proof manipulation, and `RumorInjector` are not reused. Phase 12 does not call `get_top_n_users_by_degree`, does not read `is_top_user`, does not write ForumDB, and does not alter Agent prompts or market state.

## Behavioural boundary

Phase 12 adds **zero participant behavioural parameters**. It adds no judgement, credibility rating, confidence item, comprehension question, trading rule, checkpoint, or decision day.

## Status

This patch establishes the minimal adapter contract only. Display wording remains `1.0-candidate / development` until a later formal source-cue freeze step.
