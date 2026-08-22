# Phase 7D-2 — Forced Dynamic Top-User News-Routing Coverage Gate

**Status:** NON-FORMAL ENGINEERING BRANCH COVERAGE
**Natural Phase 4 activation evidence:** NO
**Formal experiment evidence:** NO
**Real LLM backend:** YES — exactly one forced Agent
**Market advance:** NO

## Purpose

Phase 7C validated the natural one-day chain, but its three naturally activated
Agents did not include either dynamic top user. Therefore TwinMarket's inherited
top-user-only `_read_news()` branch was not exercised.

Phase 7D-2 fills only that branch-coverage gap.

## Selection rule

The gate rebuilds the Phase 6 graph from history through `2023-06-14`, derives
the deterministic prominence ranking, and forces the first dynamic top-user ID
active for one reasoning call.

This is deliberately **not** a Phase 4 activation result and must never be
reported as natural activation evidence.

## Evidence of inherited news routing

The complete `2023-06-15` TwinMarket daily-news list is passed unchanged to the
Phase 7C inherited reasoning path.

The gate then reads TwinMarket's saved conversation record and reconstructs the
news prompt with inherited `TradingPrompt.get_news_analysis_prompt(...)`.

PASS requires the exact inherited news prompt to be present once and to be
immediately followed by a non-empty assistant response.

No market matching is executed and no TwinMarket core file is modified.
