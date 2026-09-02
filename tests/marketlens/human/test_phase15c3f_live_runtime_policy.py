from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from marketlens.human.feedback import (
    CONTEXT_PACK_VERSION,
    FORMAL_CONTEXT_LIMITS,
    FORMAL_FALLBACK_STATUS,
    FORMAL_LIVE_FEEDBACK_POLICY,
    FeedbackContextPack,
    FrozenFeedbackPrompt,
    formal_fallback_output,
    formal_fallback_sha256_by_kind,
    validate_feedback_output,
)
from marketlens.human.stores.feedback_store import FeedbackStore
from marketlens.persistence.database import Database


def _context(kind: str) -> FeedbackContextPack:
    end = 15 if kind == "final_session_summary" else 4
    window = {
        "start_period": 1,
        "end_period": end,
        "periods_reviewed": end,
    }
    return FeedbackContextPack(
        context_pack_version=CONTEXT_PACK_VERSION,
        context_policy_version=FORMAL_CONTEXT_LIMITS.policy_version,
        feedback_kind=kind,
        window=window,
        statistics={"window": window},
        information_environment={
            "available_news": [],
            "available_community_content": [],
            "released_controlled_information": [],
        },
        participant_reflections=(),
        prior_context=None,
        context_coverage={},
    )


def _prompt(kind: str) -> FrozenFeedbackPrompt:
    return FrozenFeedbackPrompt(
        prompt_contract_version="prompt-test-v1",
        context_pack_version=CONTEXT_PACK_VERSION,
        context_policy_version=FORMAL_CONTEXT_LIMITS.policy_version,
        context_sha256="c" * 64,
        feedback_kind=kind,
        system_prompt="SYSTEM",
        user_prompt="USER",
    )


def _claim_values() -> dict[str, object]:
    return {
        "generation_id": "generation-001",
        "session_id": "session-001",
        "participant_id": "participant-001",
        "experiment_step": 3,
        "agent_world_date": "2023-06-22",
        "prompt_sha256": "d" * 64,
        "generator_id": "formal-generator-test-v1",
        "status": "GENERATING",
        "claimed_at": "2026-09-02T10:00:00+00:00",
    }


def test_live_policy_freezes_wait_fallback_and_context_bounds():
    assert FORMAL_LIVE_FEEDBACK_POLICY["fixed_decision_points"] == (
        "F1",
        "F2",
        "FINAL",
    )
    assert FORMAL_LIVE_FEEDBACK_POLICY["provider_attempts"] == 2
    assert FORMAL_LIVE_FEEDBACK_POLICY["intervention_options"] == (
        "formal_live_provider_validated",
        "formal_live_fallback_validated",
    )
    assert "neutral wording and ordering of those patterns" in (
        FORMAL_LIVE_FEEDBACK_POLICY["allowed_personalisation"]
    )
    assert "feedback checkpoints and windows" in (
        FORMAL_LIVE_FEEDBACK_POLICY["locked_across_participants"]
    )
    assert FORMAL_LIVE_FEEDBACK_POLICY["request_timeout_seconds"] == 30.0
    assert FORMAL_LIVE_FEEDBACK_POLICY["total_wait_seconds"] == 45.0
    assert FORMAL_LIVE_FEEDBACK_POLICY[
        "fallback_for_context_or_invariant_failure"
    ] is False
    assert FORMAL_CONTEXT_LIMITS.max_news_items == 70
    assert FORMAL_CONTEXT_LIMITS.max_community_posts == 200
    assert FORMAL_CONTEXT_LIMITS.max_news_chars == 2000
    assert FORMAL_CONTEXT_LIMITS.max_community_chars == 1000


def test_frozen_fallbacks_pass_the_same_output_validator():
    for kind in (
        "multi_period_decision_feedback",
        "final_session_summary",
    ):
        validated = validate_feedback_output(
            formal_fallback_output(_prompt(kind)),
            context_pack=_context(kind),
        )
        assert validated.feedback_kind == kind
        assert len(validated.output_sha256) == 64

    hashes = formal_fallback_sha256_by_kind()
    assert set(hashes) == {
        "multi_period_decision_feedback",
        "final_session_summary",
    }
    assert all(len(value) == 64 for value in hashes.values())


def test_database_claim_allows_only_one_cross_worker_owner(tmp_path):
    path = tmp_path / "claims.db"
    first_db = Database(path)
    second_db = Database(path)
    first_store = FeedbackStore(first_db)
    second_store = FeedbackStore(second_db)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda store: store.claim_generation_once(
                        **_claim_values()
                    )[1],
                    (first_store, second_store),
                )
            )
        assert sorted(results) == [False, True]
    finally:
        first_db.dispose()
        second_db.dispose()


def test_attempt_provenance_survives_completed_fallback(tmp_path):
    db = Database(tmp_path / "provenance.db")
    store = FeedbackStore(db)
    try:
        _, claimed = store.claim_generation_once(**_claim_values())
        assert claimed is True
        provenance = {
            "attempt_count": 2,
            "attempt_history": [
                {"attempt_number": 1, "outcome": "provider_timeout"},
                {"attempt_number": 2, "outcome": "validation_rejected"},
            ],
            "fallback_used": True,
            "fallback_trigger": "output_validation_exhausted",
        }
        row = store.finish_generation(
            session_id="session-001",
            experiment_step=3,
            finished_at="2026-09-02T10:00:45+00:00",
            effective_generation_status=FORMAL_FALLBACK_STATUS,
            attempt_provenance_json=json.dumps(provenance, sort_keys=True),
            output_sha256="e" * 64,
        )
        assert row["status"] == "COMPLETED"
        assert row["effective_generation_status"] == FORMAL_FALLBACK_STATUS
        assert json.loads(row["attempt_provenance_json"]) == provenance
    finally:
        db.dispose()


def test_unrecoverable_generation_failure_is_recorded(tmp_path):
    db = Database(tmp_path / "failed.db")
    store = FeedbackStore(db)
    try:
        store.claim_generation_once(**_claim_values())
        row = store.fail_generation(
            session_id="session-001",
            experiment_step=3,
            finished_at="2026-09-02T10:00:01+00:00",
            failure_type="LocalInvariantError",
            attempt_provenance_json=json.dumps(
                {"attempt_count": 0, "attempt_history": []}
            ),
        )
        assert row["status"] == "FAILED"
        assert row["failure_type"] == "LocalInvariantError"
        assert row["attempt_provenance_json"] is not None
    finally:
        db.dispose()
