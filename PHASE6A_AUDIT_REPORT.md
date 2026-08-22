# MarketLens Phase 6A Audit Report v1.0

**Phase:** 6A — Social Graph and Dynamic Prominence  
**Date:** 22 August 2026  
**Status:** **AUDIT COMPLETE / CONTRACT READY TO FREEZE**  
**Scope:** Source/behaviour audit only. No Phase 6 runtime implementation, no LLM/API execution.

---

## 1. Purpose

Phase 6A determines exactly how MarketLens should preserve TwinMarket's inherited user-relation graph and graph-derived dynamic prominence while maintaining the dissertation's experimental boundaries.

The Phase 6 research contract is:

- `user_type` remains a **stable inherited source-status/persona feature**.
- `is_top_user` remains a **dynamic runtime graph property**.
- prominence must not encode correctness, trustworthiness, strategy, or activation probability.
- participant behaviour must not affect the Agent graph.
- Phase 6 must not silently activate Phase 7 news behaviour or multi-day forum propagation.

---

## 2. Sources audited

### Current MarketLens / inherited baseline snapshot
From `marketlens-dependency-audit.zip`:

- `simulation.py`
- `util/UserDB.py`
- `util/ForumDB.py`
- `trader/trading_agent.py`
- `trader/recommender.py`
- `marketlens/agents/population/*`
- `marketlens/agents/activation/*`
- `marketlens/agents/runtime/*`

### Uploaded newer TwinMarket archive
All four uploaded archives were checked:

- `TwinMarket.zip`
- `TwinMarket(1).zip`
- `TwinMarket(2).zip`
- `TwinMarket(3).zip`

All four have the same SHA256:

`4f7ee534326a3c2fd40f1cada86615b0fa63bd2d50129945c19b03fe6ace922f`

Therefore only one archive needs to be treated as the comparison source.

Relevant newer/legacy files reviewed include:

- `TwinMarket/simulation.py`
- `TwinMarket/util/UserDB.py`
- `TwinMarket/trader/trading_agent.py`
- `TwinMarket/trader/recommender.py`
- `scripts/experiments/agent_population_feasibility/run_phase_b_execution.py`
- Phase B activation/config support files

### Important code-equivalence finding

The graph-relevant inherited functions are unchanged between the current MarketLens inherited baseline snapshot and the newer uploaded TwinMarket archive:

- `get_top_n_users_by_degree`
- `build_graph_new`
- `update_graph`
- `get_top_industry_and_category`

The relevant `PersonalizedStockTrader.input_info()` and `_read_news()` methods are also unchanged.

This means the newer archive does **not** provide a better replacement graph algorithm. It is useful mainly as a reference for later integration patterns, not as a codebase to merge.

---

## 3. Inherited graph algorithm trace

The actual TwinMarket runtime path is:

```text
bounded/runtime user database
        ↓
build_graph_new(...)
        ↓
industry-weighted trading histories
        ↓
exponential time weighting
        ↓
weighted Jaccard similarity
        ↓
similarity threshold
        ↓
NetworkX undirected graph
        ↓
get_top_n_users_by_degree(...)
        ↓
dynamic top_user list
```

### 3.1 Node source

`build_graph_new()` obtains graph nodes from:

```sql
SELECT DISTINCT user_id FROM Profiles
```

Therefore, when MarketLens passes the **Phase 3 bounded runtime database**, graph membership is automatically bounded to the selected Agent population.

This is the correct integration boundary.

**Decision: KEEP.**

---

## 4. What the graph represents

The graph is **not** a follower graph, friendship graph, trust graph, or credibility graph.

Edges are derived from historical trading-industry similarity:

1. query each Agent's `TradingDetails` within the supplied date range;
2. accumulate industry counts with exponential time weighting;
3. compute pairwise weighted Jaccard similarity;
4. add an edge when similarity is greater than the configured threshold.

Therefore the most accurate dissertation wording is:

> **an inherited similarity-derived user-relation graph based on historical trading-industry overlap**

Graph-derived `is_top_user` should be described as:

> **dynamic graph prominence**

It must not be described as truthfulness, expertise, reliability, or credibility.

---

## 5. Graph rebuild behaviour

Although `util/UserDB.py` defines `update_graph()`, the inherited `simulation.py` does not use it for the normal daily simulation path.

Instead, TwinMarket rebuilds the graph from historical data on each date using `build_graph_new(...)`.

Therefore MarketLens should preserve the actual runtime mechanism:

```text
allowed history through day t-1
        ↓
rebuild graph
        ↓
derive prominence for day t
```

**Decision: KEEP rebuild behaviour.**  
**Decision: REJECT introducing `update_graph()` in Phase 6.**

---

## 6. Date boundary / future-information control

Inherited `simulation.py` calls `build_graph_new(..., end_date=current_date)`.

MarketLens should make the contract more explicit:

> Graph construction for experiment day `t` may use only trading history permitted before day `t`.

For the current development Day 1:

```text
experiment date:   2023-06-15
history cutoff:    2023-06-14
```

The reconstructed N=20 runtime database contains:

- 896 selected-Agent `TradingDetails` rows
- minimum date: `2023-01-03`
- maximum date: `2023-06-14`
- all 896 `date_time` values are date-only strings of length 10

Thus the current Day-1 graph contains no 2023-06-15 or future trade records.

**Decision: ADAPT interface semantics to require an explicit `history_cutoff`.**  
This is a MarketLens safety boundary, not a change to the similarity algorithm.

---

## 7. Development graph parameters

There is an inherited inconsistency:

### `init_simulation()` defaults
- `similarity_threshold = 0.1`
- `time_decay_factor = 0.05`
- `top_n_user = 0.1`

### CLI parser defaults
- `similarity_threshold = 0.2`
- `time_decay_factor = 0.5`
- `top_n_user = 0.1`

The uploaded Phase B runner explicitly uses:

- `similarity_threshold = 0.1`
- `time_decay_factor = 0.05`
- `top_n_user = 0.1`

For Phase 6 development, MarketLens should use the values matching the inherited `init_simulation()` path:

```text
graph_start_date      = 2023-01-01
similarity_threshold  = 0.1
time_decay_factor     = 0.05
top_fraction          = 0.10
```

These are **development/inherited defaults**, not yet formal experiment parameters.

**Decision: KEEP as development defaults; DEFER formal freeze.**

---

## 8. Dynamic prominence metric

Inherited `get_top_n_users_by_degree()` uses:

```python
degrees = dict(G.degree())
```

No edge weight is supplied to `degree()`. Therefore inherited prominence is based on:

> **unweighted graph degree**

not weighted degree / strength / PageRank.

**Decision: KEEP unweighted degree.**

---

## 9. `top_n` derivation problem

Inherited `simulation.py` uses:

```python
top_n = int(node * top_n_user)
```

This allows an independent CLI `node` value to disagree with the actual bounded graph size.

MarketLens already has a single authoritative population source: the bounded runtime database / manifest.

Therefore Phase 6 must derive:

```python
actual_n = graph.number_of_nodes()
top_n = int(actual_n * top_fraction)
```

For current candidate-sized populations this preserves inherited floor behaviour:

- N20 → 2
- N25 → 2
- N30 → 3
- N35 → 3

**Decision: ADAPT.**  
Do not use an independent `node` argument for prominence count.

---

## 10. Deterministic tie handling — required adaptation

Inherited `get_top_n_users_by_degree()` sorts only by degree. Python's stable sorting then implicitly preserves graph-node insertion order for ties.

This is not a sufficient reproducibility rule.

### Current N20 Day-1 audit

Using the reconstructed Phase 3 N20 population:

- population size: 20
- selected-ID SHA256:  
  `aef5f41ef8c2ef7883ae5167dee697766fe020c4d6f180ae086ada911329d740`
- history cutoff: 2023-06-14
- graph nodes: 20
- graph edges: 46
- isolated nodes: 0
- `top_n`: 2

Three Agents tie at the cutoff with degree 7:

```text
25901251490
72429318063
84223796359
```

Inherited current node order returns:

```text
25901251490
72429318063
```

But rebuilding the same graph with reversed node insertion order produces:

```text
84223796359
72429318063
```

while all node degrees remain identical.

Therefore the inherited function has a genuine reproducibility ambiguity.

### Frozen MarketLens rule

Rank by:

```text
1. degree descending
2. normalized user_id ascending
```

This preserves the current N20 outcome while making the rule explicit and reproducible.

**Decision: ADAPT — mandatory.**

---

## 11. Isolated-node repair — inherited limitation

After constructing natural similarity edges, `build_graph_new()` identifies isolated nodes and connects consecutive isolates using the minimum observed edge weight (or the threshold if no natural edges exist).

This is not a similarity-derived relationship.

It also does not fully guarantee connectivity: if exactly one isolate exists, no repair edge is added.

### Reconstructed N20 audit

| History cutoff | Natural edges | Natural isolates | Synthetic repair edges | Result isolates |
|---|---:|---:|---:|---:|
| 2023-01-05 | 7 | 11 | 10 | 0 |
| 2023-01-10 | 10 | 12 | 11 | 0 |
| 2023-01-20 | 25 | 2 | 1 | 0 |
| 2023-05-15 | 45 | 1 | 0 | 1 |
| 2023-06-14 | 46 | 0 | 0 | 0 |
| 2023-06-15 | 46 | 0 | 0 | 0 |

The current development Day-1 graph is unaffected because it has no isolates.

Changing this mechanism now would alter inherited graph semantics unnecessarily.

**Decision: KEEP inherited behaviour for Phase 6 development, but record as a known limitation.**  
**Decision: RE-EVALUATE before formal population/timeline freeze if candidate runs trigger repair edges in the formal window.**

Do not modify `util/UserDB.py` in Phase 6 solely for this issue.

---

## 12. Dynamic status is real

The N20 graph audit confirms that graph-derived prominence can change as the permitted history changes.

Examples from the same bounded population show different top-ranked Agents on different dates.

Therefore the Master Plan requirement that `is_top_user` can change dynamically is supported by the inherited mechanism.

**Decision: KEEP dynamic recalculation.**

---

## 13. `user_type` separation

The graph construction and degree ranking do not use `user_type`.

Therefore:

```text
user_type
≠
is_top_user
```

remains technically enforceable.

A stable `普通股民` Agent can become graph-prominent; a stable `大V` Agent is not automatically graph-prominent.

**Decision: KEEP and test explicitly.**

Forbidden Phase 6 logic:

```python
if user_type == "大V":
    is_top_user = True
```

---

## 14. Phase 4 activation separation

The current MarketLens Phase 4 contract intentionally excludes both `user_type` and `is_top_user` from the activation formula.

Phase 6 must not change that.

`is_top_user` is a graph state, not an activation probability.

**Decision: KEEP Phase 4 unchanged.**

---

## 15. Critical coupling: `is_top_user` changes inherited reasoning

In inherited `PersonalizedStockTrader.input_info()`:

```python
if self.is_top_user:
    self._read_news()
```

This occurs for activated Agents.

Even when `import_news=[]`, `_read_news()` appends a no-important-news message to the conversation history.

Therefore these two conditions are not reasoning-equivalent:

```text
is_top_user = False
```

and

```text
is_top_user = True, import_news = []
```

Passing graph-derived top-user status directly into the paid reasoning pipeline during Phase 6 would silently activate part of Phase 7's role-dependent news-processing behaviour.

**Decision: DEFER `is_top_user` → real Agent reasoning integration until Phase 7.**

Phase 6 should construct and audit prominence state only.

No real backend/API call is required for Phase 6.

---

## 16. Multi-day forum coupling

For `day_1st=False`, inherited `input_info()` calls `recommend_post_graph(...)`.

That function:

- retrieves posts only from graph neighbours;
- uses forum reactions;
- ranks posts with a recency/hotness score;
- uses `pd.Timestamp.now()` in the hotness calculation.

Therefore enabling the graph inside multi-day Agent reasoning would also introduce forum propagation and a separate time-reproducibility issue.

**Decision: DEFER multi-day forum propagation.**

It is not part of the Phase 6 graph/prominence acceptance gate.

---

## 17. `datetime.now()` inside graph weighting

`build_graph_new()` uses `datetime.now()` when computing exponential trade-history weights.

For the current source data, all selected `TradingDetails.date_time` values are date-only. Advancing wall-clock date shifts all historical day differences by the same amount, multiplying all trade weights by a common factor. That common factor cancels in the weighted Jaccard ratio.

Therefore this implementation detail is not currently the primary reproducibility risk.

The observed reproducibility issue is the degree-tie ordering described above.

**Decision: do not rewrite the inherited weighting algorithm in Phase 6.**  
Add deterministic graph-output tests and a date-format/source-range validator instead.

---

## 18. Node attribute date scope

`build_graph_new()` adds node attributes using `get_top_industry_and_category()`, which queries all `TradingDetails` for the Agent and does not accept the graph history cutoff.

For the current development source this does not leak future data because the maximum selected trade date is 2023-06-14.

Also, these node attributes are not used by inherited degree-based prominence.

**Decision: KEEP inherited attributes but do not use/expose them as experimental prominence or participant credibility cues.**  
Validate source date range before formal freeze.

---

## 19. Uploaded Phase B runner comparison

The uploaded Phase B runner contains useful integration ideas:

### Keep as reference
- call `simulation.build_graph_new(...)`
- use the candidate/bounded database
- `save=False`
- development graph parameters `0.1 / 0.05`
- top fraction `0.1`
- normalize top-user IDs to strings
- explicitly record:
  - `derived_from_user_type = False`
  - `stable_user_type_kept_separate = True`

### Reject for Phase 6 architecture
The runner mixes:
- graph
- top-user state
- market movement
- news
- activation
- portfolio exposure
- social signal
- real Agent reasoning
- instrumentation

MarketLens deliberately separated these layers in Phases 3–5.

**Decision: selective reuse of behaviour/invariants only; no wholesale port of Phase B architecture.**

---

## 20. Phase 6A KEEP / ADAPT / REJECT / DEFER table

| Item | Decision |
|---|---|
| `build_graph_new()` core similarity algorithm | **KEEP** |
| Graph nodes sourced from bounded runtime DB | **KEEP** |
| Daily/full graph rebuild from allowed history | **KEEP** |
| `update_graph()` | **REJECT for Phase 6** |
| Industry weighted-Jaccard edges | **KEEP** |
| Unweighted degree prominence | **KEEP** |
| `similarity_threshold=0.1` | **KEEP as development default** |
| `time_decay_factor=0.05` | **KEEP as development default** |
| `top_fraction=0.10` | **KEEP as development default** |
| Formal parameter freeze | **DEFER** |
| `save=True` graph files | **REJECT** |
| `save=False` | **KEEP** |
| `top_n=int(node*0.1)` | **REJECT** |
| `top_n=int(actual_graph_n*0.1)` | **ADAPT** |
| Degree-only tie ordering | **REJECT** |
| Degree DESC + normalized user_id ASC | **ADAPT** |
| Explicit `history_cutoff` | **ADAPT** |
| `user_type → top_user` | **FORBIDDEN / REJECT** |
| `is_top_user → Phase 4 activation` | **FORBIDDEN / REJECT** |
| Inherited isolated-node repair | **KEEP NOW / KNOWN LIMITATION** |
| Modify inherited `UserDB.py` to remove repair now | **DEFER** |
| `is_top_user → paid reasoning` | **DEFER to Phase 7** |
| Controlled news | **DEFER to Phase 7** |
| Multi-day forum propagation | **DEFER** |
| Participant-visible prominence cue | **DEFER to later UI/source-cue design** |
| Structured Agent measurement | **DEFER to Phase 12** |
| Phase B population comparison | **DEFER to Phase 13** |
| Real LLM/API validation for Phase 6 | **NOT REQUIRED** |
| Modification of TwinMarket core | **NOT REQUIRED** |

---

## 21. Frozen Phase 6 contract

Phase 6 implementation should do only this:

```text
Phase 3 bounded runtime population
        ↓
explicit history cutoff
        ↓
inherited build_graph_new(..., save=False)
        ↓
validate graph membership == bounded population
        ↓
derive actual graph N
        ↓
top_n = floor(actual_N × 0.10)
        ↓
rank by:
degree DESC
user_id ASC
        ↓
dynamic prominence snapshot
        ↓
audit/log only
```

Phase 6 must **not** do this yet:

```text
top_user
→ _read_news()
→ forum propagation
→ paid Agent reasoning
→ participant-visible credibility cue
```

---

## 22. Recommended Phase 6B implementation boundary

Only after this audit contract is accepted, add a MarketLens-owned wrapper such as:

```text
marketlens/
└── agents/
    └── social/
        ├── __init__.py
        ├── models.py
        ├── graph.py
        └── prominence.py

tests/
└── marketlens/
    └── agents/
        ├── test_social_graph.py
        └── test_dynamic_prominence.py

PHASE6_README.md
```

Do **not** modify:

- `simulation.py`
- `util/UserDB.py`
- `trader/trading_agent.py`
- `util/ForumDB.py`
- other inherited TwinMarket core files

---

## 23. Phase 6B acceptance gate

Implementation should not be considered complete until tests prove:

1. graph nodes exactly match the bounded population;
2. no 1000-Agent leakage;
3. graph source/runtime DB remains unchanged;
4. no participant state/database is read;
5. explicit history cutoff is enforced;
6. `save=False` prevents inherited graph artifact writes;
7. graph parameters are recorded;
8. `top_n` derives from actual graph size;
9. prominence uses unweighted degree;
10. degree ties are deterministic;
11. same bounded DB + same cutoff → same prominence snapshot;
12. `user_type` is not a prominence input;
13. `is_top_user` is not an activation input;
14. dynamic top-user IDs are logged;
15. prominence can change when permitted historical data changes;
16. no news processing occurs;
17. no forum propagation occurs;
18. no LLM/API call occurs;
19. no inherited TwinMarket core file is modified;
20. full regression suite still passes.

---

## 24. Phase 6A final status

```text
Phase 5                              FROZEN
Phase 6 source reconnaissance        COMPLETE
Phase 6A formal audit                COMPLETE
Phase 6A contract                    READY TO FREEZE
Phase 6B implementation              NOT STARTED
```

### Final conclusion

The inherited TwinMarket graph is suitable for MarketLens **without replacing its core algorithm**.

The main required MarketLens adaptations are narrowly bounded:

1. explicit pre-day history cutoff;
2. derive `top_n` from actual bounded graph size;
3. deterministic degree-tie handling;
4. audit/log prominence without yet feeding it into the inherited news/forum reasoning paths.

The isolated-node repair is a documented inherited limitation, but it does not affect the current N20 Day-1 graph and does not justify modifying TwinMarket core at this stage.

This is sufficient to proceed safely to Phase 6B.
