from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketlens.market.feasibility import (
    Phase09DAuditError,
    activation_metrics,
    build_audit,
    discover_latest_summary,
    graph_continuity_metrics,
    reasoning_runtime_metrics,
    render_markdown,
    validate_expected_evidence,
)


def _dry(n: int, counts: list[int], *, phase: str):
    return {
        "phase": phase,
        "mode": "dry",
        "status": "READY / 0 LLM / NO MARKET OR FORUM MUTATION",
        "population": {"size": n},
        "activation": {
            "days": [
                {"n_active": count}
                for count in counts
            ]
        },
        "horizon": {
            "market_open": [True, True, False],
        },
        "duration_seconds": 1.0,
    }


def _real():
    return {
        "phase": "9C-N20",
        "mode": "real",
        "status": "PASS",
        "population": {"size": 20},
        "activation": {
            "days": [
                {"n_active": 5},
                {"n_active": 3},
                {"n_active": 3},
            ]
        },
        "horizon": {"market_open": [True, True, False]},
        "duration_seconds": 1420.9,
        "integrity": {
            "protected_sources_unchanged": True,
            "verified_n20_fixture_unchanged": True,
            "participant_data_used": False,
            "custom_market_logic_used": False,
            "custom_forum_logic_used": False,
            "custom_belief_logic_used": False,
        },
        "continuity": {
            "activation_state_chain_valid": True,
            "all_graphs_bounded_n20": True,
            "same_working_runtime_across_all_days": True,
            "same_working_forum_across_all_days": True,
            "daily_graph_recomputed_after_prior_day_state": True,
        },
        "natural_multiday_coverage": {
            "posts_created_total": 11,
            "forum_belief_agents_observed": 13,
            "later_day_forum_action_calls": 6,
        },
        "days": [
            {
                "graph": {
                    "n_edges": 46,
                    "graph_sha256": "a",
                    "top_user_ids": ["u1", "u2"],
                },
                "belief": {"forum_with_belief": 0},
                "reasoning": {
                    "duration_seconds": 407.577,
                    "per_agent": [
                        {"duration_seconds": 77.429},
                        {"duration_seconds": 84.477},
                        {"duration_seconds": 88.577},
                        {"duration_seconds": 76.595},
                        {"duration_seconds": 80.499},
                    ],
                },
                "runtime_metrics": {
                    "Profiles": {"total_rows": 40, "rows_for_date": 20},
                    "StockData": {"total_rows": 1090, "rows_for_date": 10},
                    "TradingDetails": {"total_rows": 901},
                },
                "forum_metrics": {"posts": 5, "reactions": 0},
                "market": {"action": "advance_trading_day"},
            },
            {
                "graph": {
                    "n_edges": 43,
                    "graph_sha256": "b",
                    "top_user_ids": ["u3", "u2"],
                },
                "belief": {"forum_with_belief": 5},
                "reasoning": {
                    "duration_seconds": 263.943,
                    "per_agent": [
                        {"duration_seconds": 85.018},
                        {"duration_seconds": 96.062},
                        {"duration_seconds": 82.863},
                    ],
                },
                "runtime_metrics": {
                    "Profiles": {"total_rows": 60, "rows_for_date": 20},
                    "StockData": {"total_rows": 1100, "rows_for_date": 10},
                    "TradingDetails": {"total_rows": 903},
                },
                "forum_metrics": {"posts": 8, "reactions": 3},
                "market": {"action": "advance_trading_day"},
            },
            {
                "graph": {
                    "n_edges": 40,
                    "graph_sha256": "c",
                    "top_user_ids": ["u3", "u4"],
                },
                "belief": {"forum_with_belief": 8},
                "reasoning": {
                    "duration_seconds": 748.49,
                    "per_agent": [
                        {"duration_seconds": 41.731},
                        {"duration_seconds": 664.834},
                        {"duration_seconds": 41.925},
                    ],
                },
                "runtime_metrics": {
                    "Profiles": {"total_rows": 80, "rows_for_date": 20},
                    "StockData": {"total_rows": 1100, "rows_for_date": 0},
                    "TradingDetails": {"total_rows": 903},
                },
                "forum_metrics": {"posts": 11, "reactions": 8},
                "market": {"action": "advance_non_trading_day"},
            },
        ],
    }


def test_n10_activation_metrics_capture_sparsity():
    metrics = activation_metrics(_dry(10, [0, 2, 0], phase="9C"))
    assert metrics["active_agent_days"] == 2
    assert metrics["zero_active_days"] == 2
    assert metrics["open_day_active_mean"] == 1.0
    assert metrics["activation_density"] == pytest.approx(2 / 30)


def test_n20_activation_metrics_capture_full_three_day_activity():
    metrics = activation_metrics(
        _dry(20, [5, 3, 3], phase="9C-N20")
    )
    assert metrics["active_agent_days"] == 11
    assert metrics["zero_active_days"] == 0
    assert metrics["open_day_active_mean"] == 4.0
    assert metrics["closed_day_active_mean"] == 3.0


def test_runtime_keeps_backend_call_count_unknown():
    metrics = reasoning_runtime_metrics(_real())
    assert metrics["backend_call_count"] is None
    assert metrics["backend_call_count_status"] == (
        "not_instrumented_not_inferred"
    )
    assert metrics["per_agent_pipeline_median_seconds"] == pytest.approx(
        82.863
    )
    assert metrics["per_agent_pipeline_max_seconds"] == pytest.approx(
        664.834
    )


def test_graph_metrics_capture_dynamic_top_user_changes():
    metrics = graph_continuity_metrics(_real())
    assert metrics["edge_counts"] == [46, 43, 40]
    assert metrics["top_user_set_changed_transitions"] == 2
    assert metrics["unique_top_users_observed"] == ["u1", "u2", "u3", "u4"]


def test_expected_evidence_passes_current_reference():
    failures = validate_expected_evidence(
        n10_dry=_dry(10, [0, 2, 0], phase="9C"),
        n20_dry=_dry(20, [5, 3, 3], phase="9C-N20"),
        n20_real=_real(),
    )
    assert failures == []


def test_audit_recommends_n20_as_leading_not_final():
    audit = build_audit(
        n10_dry=_dry(10, [0, 2, 0], phase="9C"),
        n20_dry=_dry(20, [5, 3, 3], phase="9C-N20"),
        n20_real=_real(),
        source_paths={"a": "a", "b": "b", "c": "c"},
        source_hashes={"a": "1", "b": "2", "c": "3"},
    )
    assert audit["status"] == "PASS"
    assert audit["recommendation"]["current_leading_candidate"] == "N20"
    assert audit["recommendation"]["final_formal_n_frozen"] is False
    assert (
        audit["recommendation"]["n40_paid_real_backend_recommended_now"]
        is False
    )


def test_markdown_does_not_invent_backend_call_count():
    audit = build_audit(
        n10_dry=_dry(10, [0, 2, 0], phase="9C"),
        n20_dry=_dry(20, [5, 3, 3], phase="9C-N20"),
        n20_real=_real(),
        source_paths={"a": "a", "b": "b", "c": "c"},
        source_hashes={"a": "1", "b": "2", "c": "3"},
    )
    report = render_markdown(audit)
    assert "not instrumented and not inferred" in report
    assert "Final formal N is **not frozen**" in report


def test_discovery_chooses_latest_matching_run(tmp_path: Path):
    for name in (
        "20260822T230000Z_old_phase09c_n20_real",
        "20260823T000421Z_new_phase09c_n20_real",
    ):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "summary.json").write_text(
            "{}\n", encoding="utf-8"
        )

    result = discover_latest_summary(
        tmp_path,
        suffix="_phase09c_n20_real",
    )
    assert result.parent.name.startswith("20260823T000421Z")
