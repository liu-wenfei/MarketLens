# Phase 13B — Participant Background Information Projection Audit

## Scope

Phase 13B defines a **read-only participant-safe projection contract** for the dynamic
background information already produced by the canonical TwinMarket world. It does not
create Agent content, alter Agent/forum state, decide controlled-stimulus visibility, or
add participant behavioural parameters.

## Reuse audit

### Natural news — reuse Phase 7

Use `marketlens.market.runtime.news.load_daily_news(...)` for the session-authorised
`current_date`. Do not create a second news loader, summariser, ranking policy, or history
reconstructor.

### Forum — reuse inherited TwinMarket

Use inherited `util.ForumDB.get_all_users_posts_db(end_date=...)`. Its native contract
returns non-repost posts up to an inclusive timestamp. Phase 13B flattens the inherited
user-grouped result into a participant feed and sorts it globally by canonical timestamp;
it does not rewrite the ForumDB query or write to ForumDB.

### Agent source identity — reuse Phase 12 / inherited UserDB

Forum `post.user_id` is resolved through the frozen Phase 12 adapter. The profile lookup
uses the same simulated-day `Profiles` snapshot (`YYYY-MM-DD 00:00:00`). `is_top_user`,
graph degree, and other dynamic prominence values are not used as credibility cues.

## Canonical episode binding gap

The current human backend does **not** yet own a formal canonical Agent-world user DB and
forum DB. Phase 9 real-backend workspaces were validation workspaces and old ZIP/history
snapshots are not formal experiment state.

Therefore Phase 13B adds an explicit `CanonicalEpisodeBinding` contract. The normal app
does not auto-bind any repo sample, old ZIP, or legacy forum. Formal projection requires:

- `status = formal_frozen`;
- a canonical user DB path and forum DB path;
- frozen SHA-256 for both files;
- exact hash verification at runtime.

Until those assets exist, formal mode fails closed.

## Participant forum allow-list

Only:

- `post_id`
- `author_id`
- `source_label`
- `display_text`
- `created_at`

are participant-facing.

Explicitly excluded:

- `belief`
- inherited `type`
- `score`
- raw `user_type`
- prompts / self-description
- graph degree / `is_top_user`
- Agent portfolio/trading state
- reactions/social-proof counts

## Inherited `type1/type2/type3` prefix

Historical TwinMarket forum snapshots show that the internal post classification can also
be embedded mechanically at the start of `content`. In the audited history snapshot, 180
of 190 non-repost posts began with `type1/type2/type3`; observed separators included
Chinese/ASCII colons, whitespace, `｜`, and `，`. Phase 13B removes **only this leading
internal marker plus an observed mechanical separator** before participant text lookup.
The remaining source body is otherwise unchanged by the projection layer, and occurrences
of `type2` later inside genuine prose are not removed.

## Forum temporal semantics

Forum is cumulative through the current sealed simulated date:

`created_at <= current_date 23:59:59`

This retains warm-up history and closed-day Agent social activity. A defensive future-post
check fails closed if an upstream reader ever returns a post after the participant's sealed
current date.

Natural news remains current-day input only and continues to use the Phase 7 loader.

## Controlled stimulus remains separate

Controlled misinformation/correction is **not** included in the generic background API.
Same-day J0/J1 and J2/J3 visibility cannot be inferred safely from `current_date` alone.
Controlled stimulus remains owned by Phase 11 explicit visibility moments and Phase 12
source-cue decoration.

## Translation / participant display text

No live translation is permitted in participant sessions. Phase 13B uses a source-text
SHA-256 keyed `FrozenTextPack`:

- source text is retained internally;
- participant English text must already exist in the pack;
- missing text fails closed rather than calling a translator;
- formal use requires `status = formal_frozen` and an exact manifest hash.

The formal Agent/forum translation pack is intentionally **not created in Phase 13B**;
it can only be produced after the single canonical episode has been generated and sealed.

## API contract

`GET /session/{session_id}/background`

uses only the session-authorised `current_date` and returns:

- `session_id`
- `current_date`
- `natural_news`
- `forum_posts`

The default app has no background projection bound and returns a fail-closed conflict until
an explicit canonical episode projection is injected.

## Non-goals

Phase 13B does not:

- call an LLM;
- translate live;
- mutate Agent/forum/market state;
- inject misinformation into ForumDB;
- restore old matched accounts/social-proof logic;
- expose controlled stimulus through a date-only background endpoint;
- add participant judgement/trading parameters.

`participant_behaviour_parameters_added = 0`.
