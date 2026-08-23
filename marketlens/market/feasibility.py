"""Phase 9D zero-LLM feasibility audit utilities.

This module only reads existing Phase 9C summary artifacts.  It does not call
an LLM, run Agent reasoning, mutate the market/forum, or select a new
population.  The audit is deliberately conservative: if a quantity was not
preserved in the source summaries (for example exact HTTP/backend-call count),
it remains unknown rather than being reconstructed or guessed.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AUDIT_VERSION = "marketlens_phase09d_feasibility_audit/1.0"


class Phase09DAuditError(RuntimeError):
    """Raised when required Phase 9 evidence is missing or inconsistent."""


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_summary(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise Phase09DAuditError(f"summary not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase09DAuditError(f"invalid JSON summary: {p}") from exc
    if not isinstance(data, dict):
        raise Phase09DAuditError(f"summary root is not an object: {p}")
    return data


def discover_latest_summary(
    artifact_root: str | Path,
    *,
    suffix: str,
) -> Path:
    root = Path(artifact_root)
    candidates = sorted(
        (
            p
            for p in root.glob(f"*{suffix}")
            if p.is_dir() and (p / "summary.json").is_file()
        ),
        key=lambda p: p.name,
    )
    if not candidates:
        raise Phase09DAuditError(
            f"no Phase 9 artifact ending in {suffix!r} under {root}"
        )
    return candidates[-1] / "summary.json"


def active_counts(summary: Mapping[str, Any]) -> tuple[int, ...]:
    activation = summary.get("activation", {})
    days = activation.get("days", ())
    if not isinstance(days, Sequence):
        raise Phase09DAuditError("activation.days is missing")
    counts: list[int] = []
    for day in days:
        if not isinstance(day, Mapping):
            raise Phase09DAuditError("activation day is not an object")
        value = day.get("n_active")
        if not isinstance(value, int):
            raise Phase09DAuditError("activation n_active is missing")
        counts.append(value)
    return tuple(counts)


def horizon_market_open(summary: Mapping[str, Any]) -> tuple[bool, ...]:
    values = summary.get("horizon", {}).get("market_open", ())
    if not isinstance(values, Sequence):
        raise Phase09DAuditError("horizon.market_open is missing")
    return tuple(bool(v) for v in values)


def population_size(summary: Mapping[str, Any]) -> int:
    value = summary.get("population", {}).get("size")
    if not isinstance(value, int) or value <= 0:
        raise Phase09DAuditError("population.size is missing or invalid")
    return value


def activation_metrics(summary: Mapping[str, Any]) -> dict[str, Any]:
    n = population_size(summary)
    counts = active_counts(summary)
    market_open = horizon_market_open(summary)
    if len(counts) != len(market_open):
        raise Phase09DAuditError(
            "activation-day count and market-calendar length differ"
        )
    if not counts:
        raise Phase09DAuditError("activation horizon is empty")

    open_counts = [
        count for count, is_open in zip(counts, market_open) if is_open
    ]
    closed_counts = [
        count for count, is_open in zip(counts, market_open) if not is_open
    ]

    total = sum(counts)
    possible = n * len(counts)
    return {
        "population_size": n,
        "active_counts": list(counts),
        "active_agent_days": total,
        "possible_agent_days": possible,
        "activation_density": total / possible,
        "zero_active_days": sum(1 for count in counts if count == 0),
        "open_day_active_mean": (
            sum(open_counts) / len(open_counts) if open_counts else None
        ),
        "closed_day_active_mean": (
            sum(closed_counts) / len(closed_counts)
            if closed_counts
            else None
        ),
        "all_days_have_active_agent": all(count > 0 for count in counts),
    }


def reasoning_runtime_metrics(real_summary: Mapping[str, Any]) -> dict[str, Any]:
    days = real_summary.get("days", ())
    if not isinstance(days, Sequence) or not days:
        raise Phase09DAuditError("real summary has no daily records")

    per_day: list[float] = []
    per_agent: list[float] = []
    for day in days:
        reasoning = day.get("reasoning", {})
        day_seconds = reasoning.get("duration_seconds")
        if isinstance(day_seconds, (int, float)):
            per_day.append(float(day_seconds))
        for agent in reasoning.get("per_agent", ()):
            seconds = agent.get("duration_seconds")
            if isinstance(seconds, (int, float)):
                per_agent.append(float(seconds))

    if not per_agent:
        raise Phase09DAuditError("real summary has no per-Agent runtimes")

    total_wall = real_summary.get("duration_seconds")
    if not isinstance(total_wall, (int, float)):
        total_wall = None

    return {
        "run_wall_seconds": float(total_wall) if total_wall is not None else None,
        "run_wall_minutes": (
            float(total_wall) / 60 if total_wall is not None else None
        ),
        "reasoning_day_seconds": per_day,
        "per_agent_pipeline_seconds": per_agent,
        "per_agent_pipeline_mean_seconds": statistics.fmean(per_agent),
        "per_agent_pipeline_median_seconds": statistics.median(per_agent),
        "per_agent_pipeline_min_seconds": min(per_agent),
        "per_agent_pipeline_max_seconds": max(per_agent),
        "max_to_median_ratio": (
            max(per_agent) / statistics.median(per_agent)
            if statistics.median(per_agent) > 0
            else None
        ),
        "backend_call_count": None,
        "backend_call_count_status": "not_instrumented_not_inferred",
    }


def graph_continuity_metrics(real_summary: Mapping[str, Any]) -> dict[str, Any]:
    days = real_summary.get("days", ())
    edges: list[int] = []
    top_sets: list[tuple[str, ...]] = []
    hashes: list[str | None] = []
    for day in days:
        graph = day.get("graph", {})
        edge_count = graph.get("n_edges")
        if isinstance(edge_count, int):
            edges.append(edge_count)
        top_ids = tuple(map(str, graph.get("top_user_ids", ())))
        top_sets.append(top_ids)
        hashes.append(graph.get("graph_sha256"))

    transitions = 0
    for left, right in zip(top_sets, top_sets[1:]):
        if left != right:
            transitions += 1

    unique_top_users = sorted({uid for values in top_sets for uid in values})
    return {
        "edge_counts": edges,
        "graph_hashes": hashes,
        "top_user_ids_by_day": [list(values) for values in top_sets],
        "top_user_set_changed_transitions": transitions,
        "top_user_transition_count": max(0, len(top_sets) - 1),
        "unique_top_users_observed": unique_top_users,
    }


def state_continuity_metrics(real_summary: Mapping[str, Any]) -> dict[str, Any]:
    days = real_summary.get("days", ())
    profiles_total: list[int | None] = []
    profiles_date: list[int | None] = []
    stock_total: list[int | None] = []
    stock_date: list[int | None] = []
    trading_total: list[int | None] = []
    forum_posts: list[int | None] = []
    forum_reactions: list[int | None] = []
    belief_observed: list[int | None] = []
    market_actions: list[str | None] = []

    for day in days:
        runtime = day.get("runtime_metrics", {})
        profiles = runtime.get("Profiles", {})
        stock = runtime.get("StockData", {})
        trading = runtime.get("TradingDetails", {})
        forum = day.get("forum_metrics", {})
        belief = day.get("belief", {})

        profiles_total.append(profiles.get("total_rows"))
        profiles_date.append(profiles.get("rows_for_date"))
        stock_total.append(stock.get("total_rows"))
        stock_date.append(stock.get("rows_for_date"))
        trading_total.append(trading.get("total_rows"))
        forum_posts.append(forum.get("posts"))
        forum_reactions.append(forum.get("reactions"))
        belief_observed.append(belief.get("forum_with_belief"))
        market_actions.append(day.get("market", {}).get("action"))

    return {
        "profiles_total_rows_by_day": profiles_total,
        "profiles_rows_for_date_by_day": profiles_date,
        "stockdata_total_rows_by_day": stock_total,
        "stockdata_rows_for_date_by_day": stock_date,
        "tradingdetails_total_rows_by_day": trading_total,
        "forum_posts_cumulative_by_day": forum_posts,
        "forum_reactions_cumulative_by_day": forum_reactions,
        "forum_with_belief_by_day": belief_observed,
        "market_actions_by_day": market_actions,
        "natural_multiday_coverage": dict(
            real_summary.get("natural_multiday_coverage", {})
        ),
        "continuity_flags": dict(real_summary.get("continuity", {})),
    }


def validate_expected_evidence(
    *,
    n10_dry: Mapping[str, Any],
    n20_dry: Mapping[str, Any],
    n20_real: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []

    if n10_dry.get("mode") != "dry" or population_size(n10_dry) != 10:
        failures.append("N10 dry summary identity mismatch")
    if n20_dry.get("mode") != "dry" or population_size(n20_dry) != 20:
        failures.append("N20 dry summary identity mismatch")
    if n20_real.get("mode") != "real" or population_size(n20_real) != 20:
        failures.append("N20 real summary identity mismatch")
    if n20_real.get("status") != "PASS":
        failures.append("N20 real summary is not PASS")

    expected_calendar = (True, True, False)
    for name, summary in (
        ("N10 dry", n10_dry),
        ("N20 dry", n20_dry),
        ("N20 real", n20_real),
    ):
        if horizon_market_open(summary) != expected_calendar:
            failures.append(f"{name} calendar is not OPEN/OPEN/CLOSED")

    if active_counts(n10_dry) != (0, 2, 0):
        failures.append("N10 dry activation no longer matches observed 0/2/0")
    if active_counts(n20_dry) != (5, 3, 3):
        failures.append("N20 dry activation no longer matches observed 5/3/3")
    if active_counts(n20_real) != (5, 3, 3):
        failures.append("N20 real activation no longer matches observed 5/3/3")

    integrity = n20_real.get("integrity", {})
    for field in (
        "protected_sources_unchanged",
        "verified_n20_fixture_unchanged",
    ):
        if integrity.get(field) is not True:
            failures.append(f"N20 real integrity flag is not true: {field}")

    for field in (
        "participant_data_used",
        "custom_market_logic_used",
        "custom_forum_logic_used",
        "custom_belief_logic_used",
    ):
        if integrity.get(field) is not False:
            failures.append(f"N20 real isolation flag is not false: {field}")

    continuity = n20_real.get("continuity", {})
    for field in (
        "activation_state_chain_valid",
        "all_graphs_bounded_n20",
        "same_working_runtime_across_all_days",
        "same_working_forum_across_all_days",
        "daily_graph_recomputed_after_prior_day_state",
    ):
        if continuity.get(field) is not True:
            failures.append(f"N20 real continuity flag is not true: {field}")

    return failures


def build_audit(
    *,
    n10_dry: Mapping[str, Any],
    n20_dry: Mapping[str, Any],
    n20_real: Mapping[str, Any],
    source_paths: Mapping[str, str],
    source_hashes: Mapping[str, str],
) -> dict[str, Any]:
    failures = validate_expected_evidence(
        n10_dry=n10_dry,
        n20_dry=n20_dry,
        n20_real=n20_real,
    )
    n10_activation = activation_metrics(n10_dry)
    n20_activation = activation_metrics(n20_dry)
    runtime = reasoning_runtime_metrics(n20_real)
    graph = graph_continuity_metrics(n20_real)
    state = state_continuity_metrics(n20_real)

    n10_too_sparse_for_short_propagation = (
        n10_activation["zero_active_days"] >= 2
        and not n10_activation["all_days_have_active_agent"]
    )
    n20_full_short_horizon_coverage = (
        n20_activation["all_days_have_active_agent"]
        and n20_real.get("status") == "PASS"
    )

    recommendation = {
        "current_leading_candidate": (
            "N20" if n20_full_short_horizon_coverage else None
        ),
        "final_formal_n_frozen": False,
        "n10_assessment": (
            "computationally cheap but observed three-day trajectory is too "
            "sparse for full natural propagation validation"
            if n10_too_sparse_for_short_propagation
            else "requires further review"
        ),
        "n20_assessment": (
            "demonstrated real-backend multi-day continuity and natural "
            "forum/belief propagation; runtime is feasible for engineering "
            "validation but latency is variable"
            if n20_full_short_horizon_coverage
            else "requires further review"
        ),
        "n40_paid_real_backend_recommended_now": False,
        "n40_next_step": (
            "zero-LLM / structural sensitivity only; run paid N40 only if "
            "that comparison exposes a decision-relevant uncertainty"
        ),
        "backend_call_cost": (
            "exact request count was not instrumented; do not infer it from "
            "Agent pipeline count"
        ),
    }

    return {
        "phase": "9D",
        "audit_version": AUDIT_VERSION,
        "formal_experiment_evidence": False,
        "llm_calls": 0,
        "market_execution": False,
        "forum_mutation": False,
        "participant_data_used": False,
        "source_artifacts": dict(source_paths),
        "source_sha256": dict(source_hashes),
        "evidence_validation_failures": failures,
        "n10_dry": {
            "status": n10_dry.get("status"),
            "activation": n10_activation,
            "duration_seconds": n10_dry.get("duration_seconds"),
        },
        "n20_dry": {
            "status": n20_dry.get("status"),
            "activation": n20_activation,
            "duration_seconds": n20_dry.get("duration_seconds"),
        },
        "n20_real": {
            "status": n20_real.get("status"),
            "activation": activation_metrics(n20_real),
            "runtime": runtime,
            "graph": graph,
            "state_continuity": state,
        },
        "comparison": {
            "activation_density_ratio_n20_to_n10": (
                n20_activation["activation_density"]
                / n10_activation["activation_density"]
                if n10_activation["activation_density"] > 0
                else None
            ),
            "open_day_active_mean_n10": n10_activation["open_day_active_mean"],
            "open_day_active_mean_n20": n20_activation["open_day_active_mean"],
            "zero_active_days_n10": n10_activation["zero_active_days"],
            "zero_active_days_n20": n20_activation["zero_active_days"],
        },
        "recommendation": recommendation,
        "status": "PASS" if not failures else "FAIL",
    }


def render_markdown(audit: Mapping[str, Any]) -> str:
    n10 = audit["n10_dry"]
    n20 = audit["n20_dry"]
    real = audit["n20_real"]
    runtime = real["runtime"]
    graph = real["graph"]
    state = real["state_continuity"]
    rec = audit["recommendation"]

    def f(value: Any, digits: int = 3) -> str:
        if value is None:
            return "not observed"
        if isinstance(value, float):
            return f"{value:.{digits}f}"
        return str(value)

    lines = [
        "# Phase 9D — Population / Multi-Day Feasibility Audit",
        "",
        "**Status:** " + audit["status"],
        "",
        "**Evidence class:** NON-FORMAL ENGINEERING FEASIBILITY",
        "",
        "This report is generated only from existing Phase 9C summary artifacts. "
        "It makes no LLM calls and performs no market/forum mutation.",
        "",
        "## Population comparison",
        "",
        "| Metric | N10 dry | N20 dry / real reference |",
        "| --- | ---: | ---: |",
        f"| Active Agents by day | {n10['activation']['active_counts']} | {n20['activation']['active_counts']} |",
        f"| Active Agent-days | {n10['activation']['active_agent_days']} | {n20['activation']['active_agent_days']} |",
        f"| Activation density | {f(n10['activation']['activation_density'])} | {f(n20['activation']['activation_density'])} |",
        f"| Zero-active days | {n10['activation']['zero_active_days']} | {n20['activation']['zero_active_days']} |",
        f"| Mean active Agents on open days | {f(n10['activation']['open_day_active_mean'])} | {f(n20['activation']['open_day_active_mean'])} |",
        "",
        "## N20 real-backend runtime",
        "",
        f"- Total run wall time: **{f(runtime['run_wall_minutes'], 2)} min** ({f(runtime['run_wall_seconds'], 1)} s).",
        f"- Per-Agent pipeline median: **{f(runtime['per_agent_pipeline_median_seconds'], 1)} s**.",
        f"- Per-Agent pipeline mean: **{f(runtime['per_agent_pipeline_mean_seconds'], 1)} s**.",
        f"- Per-Agent pipeline range: **{f(runtime['per_agent_pipeline_min_seconds'], 1)}–{f(runtime['per_agent_pipeline_max_seconds'], 1)} s**.",
        f"- Max/median latency ratio: **{f(runtime['max_to_median_ratio'], 2)}×**.",
        "- Exact backend/HTTP request count: **not instrumented and not inferred**.",
        "",
        "## Multi-day state evidence",
        "",
        f"- Graph edges by day: **{graph['edge_counts']}**.",
        f"- Dynamic top users by day: **{graph['top_user_ids_by_day']}**.",
        f"- Top-user set changed on **{graph['top_user_set_changed_transitions']} / {graph['top_user_transition_count']}** day transitions.",
        f"- Forum beliefs observed by day: **{state['forum_with_belief_by_day']}**.",
        f"- Forum posts (cumulative): **{state['forum_posts_cumulative_by_day']}**.",
        f"- Forum reactions (cumulative): **{state['forum_reactions_cumulative_by_day']}**.",
        f"- Profiles rows for current date: **{state['profiles_rows_for_date_by_day']}**.",
        f"- StockData rows for current date: **{state['stockdata_rows_for_date_by_day']}**.",
        f"- TradingDetails total rows: **{state['tradingdetails_total_rows_by_day']}**.",
        f"- Market actions: **{state['market_actions_by_day']}**.",
        "",
        "## Recommendation before Phase 9E",
        "",
        f"- Current leading candidate: **{rec['current_leading_candidate']}**.",
        "- Final formal N is **not frozen**.",
        f"- N10: {rec['n10_assessment']}.",
        f"- N20: {rec['n20_assessment']}.",
        "- Do **not** pay for an N40 real-backend run yet.",
        f"- N40 next step: {rec['n40_next_step']}.",
        "",
        "## Known limitations",
        "",
        "- The N10 and N20 evidence comes from one predeclared deterministic activation trajectory each; it is not a statistical estimate of all possible activation paths.",
        "- Exact backend-call cost was not instrumented, so this audit reports Agent pipeline count and runtime rather than inventing an HTTP-call count.",
        "- N20 is still a provisional development population. The formal population size remains a Phase 9E / Phase 10 decision.",
        "- This is engineering evidence, not formal participant-experiment evidence.",
        "",
    ]
    if audit["evidence_validation_failures"]:
        lines.extend(
            [
                "## Evidence validation failures",
                "",
                *[
                    f"- {failure}"
                    for failure in audit["evidence_validation_failures"]
                ],
                "",
            ]
        )
    return "\n".join(lines)
