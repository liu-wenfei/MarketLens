# Phase 13D — Formal Canonical Episode Pool Producer Audit

## Status

**AUDIT + ZERO-LLM PRODUCER CONTRACT ONLY. No formal episode has been executed.**

Phase 13C v1.2 freezes *what* the three canonical episode slots must be: same N30 population, same exact 27-day activation plan, same Phase 10 v1.1 timing/trading/stimulus base, and outcome-blind technical acceptance. Phase 13D freezes *how those slots may actually be generated and sealed*.

## Reuse audit

### Reused from current MarketLens / inherited TwinMarket

The already validated Phase 10 N30 real-backend path is the execution reference. Phase 13D delegates rather than rewrites:

- `simulation.process_user_input(...)` — inherited Agent reasoning pipeline.
- `marketlens.agents.social.graph.build_bounded_social_graph(...)` — bounded N30 graph.
- `marketlens.agents.social.prominence.make_prominence_snapshot(...)` — dynamic prominence.
- `util.ForumDB.get_all_users_posts_db(...)` — inherited cumulative forum/belief source.
- `util.ForumDB.create_post_db(...)` — inherited natural Agent posts.
- `util.ForumDB.execute_forum_actions(...)` and `update_posts_score_by_date_range(...)` — inherited social progression.
- `marketlens.market.runtime.inherited_market.advance_trading_day(...)` — delegates to inherited matching/price/Agent portfolio mutation.
- `marketlens.market.runtime.inherited_market.advance_non_trading_day(...)` — inherited CLOSED-day profile progression.
- Phase 10 `_verify_candidate_fixture(...)` — the already-frozen N30 membership + semantic table guard.
- Phase 10 / Phase 9C audited orchestration helpers for Agent execution, records, post creation, forum actions and technical day metrics.

No custom matching, price formation, Agent portfolio, TradingDetails, forum or belief algorithm is added.

### Not reused as formal producer lifecycle

Phase 10 real validation uses `TemporaryDirectory` and deletes the working Agent/forum DBs after PASS. Its purpose is feasibility evidence, not formal episode persistence. `--preserve-workspace` applies only to a non-PASS debug case. Therefore the Phase 10 workspace lifecycle cannot produce formal assets.

The legacy ZIP `run_history_snapshot.py` demonstrates a useful *concept* — pre-generate an Agent-only world once, keep `user.db/forum.db`, and refuse accidental overwrite — but it is not directly reusable because it uses the abandoned old runner, old population/scenario assumptions, and does not enforce the current Phase 10/13C N30 activation/timing contract. Old rumor/session/settlement paths remain excluded.

## Runtime dependency gap discovered by audit

Phase 13C v1.2 freezes the 27-day execution plan but does not itself freeze the public LLM backend identity or every file consumed at formal-run time. Merely hashing a file before and after one run only proves it did not change *during that run*; it does not prove the run began from the reviewed input version.

Phase 13D therefore adds a separate producer contract rather than changing Phase 13C again. It freezes:

- public backend model: `gpt-5.4-mini`;
- public backend base URL: `https://zhi-api.com/v1`;
- no API key value is ever stored in evidence;
- exact SHA-256 for `sys_1000.db`, trading calendar, natural-news pickle, initial-belief CSV, stock profile, stock-data CSV and Phase 10 protocol;
- exact Phase 13C v1.2 execution-plan SHA;
- Phase 10 N30 semantic/membership guard.

This separates responsibilities cleanly:

- Phase 13C: world/activation/pool protocol;
- Phase 13D: runtime provenance, execution safety, attempt lifecycle and sealing.

## Formal execution controls

Default invocation is dry-run and performs zero LLM calls. There is deliberately no execute-all option.

A paid formal command can execute exactly one explicit predeclared episode ID and requires a second explicit acknowledgement flag. Formal execution requires a clean `dissertation` working tree. A slot that already has any formal output cannot be overwritten.

A new attempt always starts from a fresh copy of the same frozen N30 initial fixture. Partial resume and seed substitution are forbidden. Failed attempts retain their partial DBs/logs/attempt manifest. A technically valid completed slot is immutable and cannot be rerun, excluded or replaced because of market direction, post/trade counts, sentiment, misinformation effect, or cross-episode similarity.

## Sealing lifecycle

A successful attempt does not write directly into a formal slot while it is still executing.

1. Create `artifacts/formal/canonical_episode/{episode_id}/attempt_NNN/`.
2. Create fresh working `agent_world.db` + empty `forum.db` inside the attempt.
3. Execute all 27 calendar ticks using the exact Phase 13C active-Agent IDs and authoritative OPEN/CLOSED actions.
4. Record per-day Agent-world/forum SHA chain and raw execution evidence.
5. Run only predeclared technical validity gates.
6. Move DBs into an attempt-local `seal_staging/` directory and validate manifest semantics before publication.
7. Atomically publish the slot directory under `data/marketlens/canonical_episode/v1/episode_XX/`.
8. Validate file hashes against the formal manifest and make DB/manifest files read-only.
9. If sealing fails, move the apparent formal directory back into failed-attempt evidence; do not leave a partial formal slot.

Pool finalization is a separate zero-LLM operation. `pool_manifest.json` can be created only after all three slot manifests and DB hashes validate.

## Predeclared technical acceptance

Required:

- 27/27 calendar ticks complete;
- exact Phase 13C active-Agent plan used;
- 193/193 active Agent pipelines complete per slot;
- exact OPEN/CLOSED inherited market action each day;
- bounded N30 graph each day;
- daily Agent-world/forum state hashes recorded;
- protected inputs unchanged and still equal their predeclared SHA values;
- candidate N30 fixture unchanged;
- no participant data in Agent world;
- no controlled misinformation/correction in Agent world;
- exact canonical DB close-price coverage for every investable asset on all 15 participant decision dates;
- every participant-visible non-repost Agent post has a same-day Profiles snapshot required by the Phase 12 source-cue join.

Not acceptance gates:

- minimum posts;
- minimum trades;
- price direction;
- sentiment;
- misinformation effect size;
- cross-episode divergence/similarity.

## Cost boundary

`193` is the predeclared number of **Agent pipeline executions per episode**, not a claim about exact API requests. One inherited Agent pipeline can make multiple backend calls. Phase 13D intentionally does not instrument or claim an exact LLM request count. The three-slot pool therefore contains 579 planned Agent pipeline executions, but actual backend request count/cost must not be inferred as 579.

## Formal execution state after this patch

Expected after zero-LLM preflight:

- formal episode DBs: absent;
- pool manifest: absent;
- participant data used: false;
- controlled stimulus injected into Agent world: false;
- LLM calls from preflight: zero.

Do not run `--execute-slot` until this producer contract has passed narrow tests, full regression, protected-source checks, clean-head preflight, commit and push.

## Git/source-control boundary for generated formal assets

Formal DBs and raw paid-run evidence are generated research artefacts, not source code. They are intentionally ignored under dedicated narrow roots:

- `artifacts/formal/canonical_episode/*` except its `.gitignore`;
- `data/marketlens/canonical_episode/v1/*` except its `.gitignore`.

This preserves the strict clean-Git requirement before every paid slot while allowing a failed attempt or already-frozen earlier slot to remain on disk. It does **not** weaken the clean-tree gate for source code, protocol, tests or protected inputs. After the pool is frozen, a later tracked freeze audit records the final manifest/DB SHA-256 values so Git contains immutable provenance without committing large SQLite/log artefacts.
