# MarketLens Canonical Episode Pool — Formal Freeze Audit

**Status:** TRACKED FORMAL POOL FREEZE RECORD  
**Raw pool manifest:** `data/marketlens/canonical_episode/v1/pool_manifest.json`  
**Raw pool manifest SHA-256:** `3f32fa3d67878cb05335af8a89305e0487a4501a834b054d53a16129047ad086`  
**Tracked pool record SHA-256:** `ce6d906436f153102412cd8e17da5bc74ec276c422272284d679e495c64db854`  
**Finalization Git baseline:** `592a1e4658f978f344639ea9233a40fc4938c286` (`dissertation`)

## Frozen pool identity

- Pool: `marketlens-canonical-episode-pool-v1`
- Episode count: 3
- Episode 01 accepted attempt: 1
- Episode 02 accepted attempt: 1
- Episode 03 accepted attempt: 3
- Formal world ticks: 27 per episode
- Agent pipeline executions: 193 per episode; 579 aggregate
- `579` is an aggregate **Agent pipeline execution count**, not an exact backend/API-call claim.

## Pool finalization evidence

The formal pool was finalized through the predeclared zero-LLM `--finalize-pool` path after all three formal episode slots existed and validated.

Frozen finalization semantics:

- `llm_api_calls = 0`
- `outcome_review_used = false`
- `episode_similarity_review_used = false`
- participant assignment mode is `balanced_random_across_episode_pool`
- `assignment_uses_episode_outcomes = false`
- the pool manifest must not be regenerated or overwritten

## Per-episode tracked record hashes

- Episode 01: `a1a1a8bbd8f0600401a8a11b36b1b6b9e5c5718450253df3028a691aad0623c3`
- Episode 02: `b902e8113d20ec10e08e8ae6e2562d7f3c66b6b677ebcb997dfa71d80852d0c5`
- Episode 03: `8a702cb5c714727a84ea5266ab794b4254bfc32e4762f3b63e5c29798ea6746c`

## Formal episode DB hashes after pool finalization

Episode 01:
- `agent_world.db`: `f9999c8e6774eb5dd2ffade5f5503ac0f863aae9e458636e92fb427198ce1741`
- `forum.db`: `3be8a5682049e011b5f2c74d40e9bc42e265364f3bb30f82f85cb4d54d064dca`

Episode 02:
- `agent_world.db`: `577aedbe7f5d07d6fd573e2614275ac99ee804d68d38b303fe9c590c2759efbd`
- `forum.db`: `b4c1fcd260cf8a84bf8860c8de09c1ede30a7d95ffcb92a81edce67eb5b9fb0b`

Episode 03:
- `agent_world.db`: `da8a077875d0011239f0c713e5b2e3556901bc9a828793f05f08c69f1584cb31`
- `forum.db`: `42ab83af3aa2da27b4c29f9f9a8097f98f47e87e03bc3fd4f1a606c1dc248f0f`

These match their accepted pre-pool freeze identities, demonstrating that zero-LLM pool finalization did not alter the six formal episode databases.

## Raw-vs-tracked evidence rule

`data/marketlens/canonical_episode/v1/*` remains gitignored. The tracked pool freeze record does not replace the raw pool manifest or per-episode formal assets. It freezes their identities and supports portable validation when raw formal evidence is not locally present.
