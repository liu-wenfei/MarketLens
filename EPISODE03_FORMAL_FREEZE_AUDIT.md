# MarketLens Episode 03 — Formal Freeze Record Audit

## Purpose

This tracked record preserves the accepted identity and complete attempt provenance of the third formal canonical episode without committing the generated SQLite assets themselves. The raw formal databases and attempt evidence remain under the Phase 13D gitignored formal-asset directories.

This patch does **not** generate, rerun, resume, or mutate an episode and makes **zero LLM calls**. It extends the existing Episode 01/02 freeze-record validator only far enough to support an accepted attempt number other than `1` and to preserve the two failed Episode 03 technical attempts.

## Accepted formal episode

- Episode pool: `marketlens-canonical-episode-pool-v1`
- Episode: `marketlens-canonical-episode-v1-e03`
- Slot: `3`
- Accepted attempt: `3`
- Acceptance status: `formal_frozen_technically_valid`
- Acceptance basis: predeclared technical gates only

## Producer provenance

- Producing Git commit: `f3035ecd334074c52f3c48bd41afdf55bf10d964`
- Branch: `dissertation`
- Phase 13C execution-plan SHA-256: `a907079281f7deca590bd7ec741b56fab614f05b0cdd869c5f2c345fb048a8bc`
- Phase 13D producer-contract SHA-256: `14db0ae7a525ef464975f7ba4da69d98eb8ffd4058d491555a32ee25f92a9126`
- Frozen initial N30 runtime SHA-256: `98a95b5ee631ac4a57648867103c25828bfa1b8af640871640cdf071e2f01a26`
- Backend model: `gpt-5.4-mini`
- Backend base URL: `https://zhi-api.com/v1`
- API key recorded: `false`

## Attempt provenance

### Attempt 001 — retained external interruption

- Raw manifest status: `running`
- Days completed: `12`
- Agent pipeline executions completed: `90`
- Accepted: `false`
- Partial resume used: `false`
- Seed substitution used: `false`
- Outcome review used for acceptance: `false`
- Episode-similarity review used for acceptance: `false`
- Manifest SHA-256: `1ff97c0a9b03120e92ac9742ba34524a5115ba480dbf9f69b64f1b8ac4ed3bb8`
- Workspace `agent_world.db` SHA-256: `dfdff33203d3c7abc9955171d9a0d1beb74d32ce5de81d0941f84cf1c3f509f3`
- Workspace `forum.db` SHA-256: `f2e27b3a701a3969b5fc5d7f6cb74210e5d1748bb9314a43e24c807fd769d715`

The producer process was externally terminated before its exception/failure handler could rewrite the raw manifest. The raw `status: running` state is therefore intentionally preserved as forensic evidence rather than manually edited. This attempt was never resumed or accepted.

### Attempt 002 — retained producer-captured technical invalidation

- Raw manifest status: `TECHNICAL_INVALID`
- Error type: `Phase09CError`
- Error: `inherited Agent reasoning failed for 95757403205: expected string or bytes-like object, got 'NoneType'`
- Days completed: `12`
- Agent pipeline executions completed: `90`
- Accepted: `false`
- Protected sources unchanged at failure capture: `true`
- Workspace preserved: `true`
- Partial resume allowed: `false`
- Restart policy: `new attempt from frozen initial N30 state only`
- Manifest SHA-256: `dfe5718e85ff8ebebecfa2beedd786016daa1c3918ec91c00d15da479d29b502`
- Workspace `agent_world.db` SHA-256: `0fbeac8e4438dc6ebd5f3f0951977c5c7bcaf5bd25a7823dae2ebada5f61cc33`
- Workspace `forum.db` SHA-256: `3a9d5d24a1c797bd53f99cf942420150a8e8012e9b12f2b1ae92e85f1ec08906`

The operator log immediately before failure contained repeated backend timeout messages, but the tracked formal classification remains the producer-captured `Phase09CError`; no stronger causal claim is encoded into the formal record.

### Attempt 003 — accepted formal run

- Raw manifest status: `FORMAL_FROZEN`
- Days completed: `27/27`
- Agent pipeline executions completed: `193/193`
- Failed Agent pipelines: `0`
- Partial resume used: `false`
- Seed substitution used: `false`
- Outcome review used for acceptance: `false`
- Episode-similarity review used for acceptance: `false`
- Accepted: `true`

Attempt 003 was a fresh restart from the frozen initial N30 state, not a continuation from either failed workspace.

## Frozen outputs

- `agent_world.db` SHA-256: `da8a077875d0011239f0c713e5b2e3556901bc9a828793f05f08c69f1584cb31`
- `forum.db` SHA-256: `42ab83af3aa2da27b4c29f9f9a8097f98f47e87e03bc3fd4f1a606c1dc248f0f`

## Producer technical gates

The accepted manifest records:

- formal world ticks: `27/27`
- expected/completed Agent pipeline executions: `193/193`
- failed Agent pipelines: `0`
- exact activation plan: `true`
- exact OPEN/CLOSED calendar actions: `true`
- complete daily state chain: `true`
- protected sources unchanged: `true`
- participant data used: `false`
- controlled stimulus injected into Agent world: `false`
- custom matching/price/forum/belief logic used: `false`
- participant exact-price coverage: `150/150`
- participant-visible non-repost source-profile joins: `193/193`

## Independent direct SQLite audit

A read-only post-run SQLite audit independently confirmed:

- both SQLite databases pass `PRAGMA integrity_check`;
- participant tables are absent;
- `Profiles = 840 = 28 x 30`;
- exact frozen N30 membership;
- `Strategy = 30`;
- `StockProfile = 10`;
- formal `StockData = 170 = 17 OPEN dates x 10 assets`;
- participant price coverage `150/150`;
- formal trades occur only on OPEN dates;
- formal trades are only by frozen N30 Agents;
- all formal `TradingDetails` rows are valid;
- exact `193` original `(date, Agent)` activation/post pairs;
- same-day Profiles source joins are complete;
- exact frozen misinformation/correction text is absent from the Agent forum.

Observed natural counts were:

- formal trades: `80`
- forum posts: `194`
- original active-Agent posts: `193`
- inherited reposts: `1`
- reactions: `243`

These natural stochastic counts are **not acceptance gates** and were not used to accept or reject the episode.

## Non-outcome-conditioned acceptance

Episode 03 is classified as:

`TECHNICALLY VALID / FORMAL_FROZEN / ACCEPTED WITHOUT OUTCOME CONDITIONING`

The episode must not be rerun, excluded, or replaced because of natural price direction, trade count, forum sentiment, participant profitability, or similarity/dissimilarity to Episodes 01 or 02.

The two failed attempts remain retained technical provenance; they do not become formal experimental evidence and do not change the accepted attempt's frozen seed/activation contract.

## Storage rule

The tracked record is:

`marketlens/episode/freeze_records/marketlens-canonical-episode-v1-e03.json`

The record has an exact SHA-256 guard. It does **not** replace raw formal assets. When local formal assets are present, the preflight cross-checks the accepted Episode/attempt manifests and final database hashes. When failed-attempt raw evidence is present, it also cross-checks the exact attempt 001/002 fingerprints. On a portable clone where gitignored raw assets are absent, static tracked-record validation remains possible.
