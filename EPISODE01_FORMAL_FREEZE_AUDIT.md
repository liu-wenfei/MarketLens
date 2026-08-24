# MarketLens Episode 01 — Formal Freeze Record Audit

## Purpose

This tracked record preserves the accepted identity of the first formal canonical episode without committing the generated SQLite assets themselves. The raw formal databases and attempt evidence remain under the Phase 13D gitignored formal-asset directories.

This is **not** a new episode generation step and makes **zero LLM calls**.

## Accepted formal episode

- Episode pool: `marketlens-canonical-episode-pool-v1`
- Episode: `marketlens-canonical-episode-v1-e01`
- Slot: `1`
- Accepted attempt: `1`
- Acceptance status: `formal_frozen_technically_valid`
- Acceptance basis: predeclared technical gates only

## Producer provenance

- Producing Git commit: `96c2a0b33587293b76eee9ba01978ef75d902abb`
- Branch: `dissertation`
- Phase 13C execution-plan SHA-256: `a907079281f7deca590bd7ec741b56fab614f05b0cdd869c5f2c345fb048a8bc`
- Phase 13D producer-contract SHA-256: `14db0ae7a525ef464975f7ba4da69d98eb8ffd4058d491555a32ee25f92a9126`
- Backend model: `gpt-5.4-mini`
- Backend base URL: `https://zhi-api.com/v1`
- API key recorded: `false`

## Frozen outputs

- `agent_world.db` SHA-256: `f9999c8e6774eb5dd2ffade5f5503ac0f863aae9e458636e92fb427198ce1741`
- `forum.db` SHA-256: `3be8a5682049e011b5f2c74d40e9bc42e265364f3bb30f82f85cb4d54d064dca`

## Execution evidence

- Formal world ticks: `27`
- Expected Agent pipeline executions: `193`
- Completed Agent pipeline executions: `193`
- Failed Agent pipeline executions: `0`
- State chain complete: `true`
- Exact frozen activation plan: `true`
- Exact calendar actions: `true`
- Protected sources unchanged: `true`
- Participant exact-price coverage: `150/150`
- Participant-visible non-repost forum posts checked for same-day source-profile join: `193`
- Missing same-day source-profile joins: `0`

## Non-outcome-conditioned acceptance

The accepted episode must not be rerun, excluded, or replaced because of natural price direction, trade count, sentiment, participant profitability, or similarity/dissimilarity to later episode slots.

The accepted attempt records:

- seed substitution used: `false`
- partial resume used: `false`
- outcome review used for acceptance: `false`
- episode-similarity review used for acceptance: `false`
- participant data used: `false`
- controlled participant stimulus injected into Agent world: `false`

## Storage rule

The tracked record is:

`marketlens/episode/freeze_records/marketlens-canonical-episode-v1-e01.json`

The tracked record has its own exact SHA-256 guard. It does **not** replace the raw formal assets. When those local assets are present, the preflight additionally cross-checks both database hashes and the Episode/attempt manifests. When raw assets are absent on another clone, static freeze-record validation remains possible.
