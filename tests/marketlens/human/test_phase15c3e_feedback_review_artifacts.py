from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from marketlens.human.feedback.review_artifacts import (
    ACCEPTED_STATUS,
    CANDIDATE_STATUS,
    REVIEW_ACCEPT,
    REVIEW_REJECT,
    REVIEW_STATUS,
    FeedbackReviewArtifactConflictError,
    FeedbackReviewArtifactError,
    FeedbackReviewArtifactStore,
    build_candidate_record,
    build_review_record,
    verify_candidate_record,
)


GENERATED_AT = "2026-09-02T09:00:00+00:00"
REVIEWED_AT = "2026-09-02T10:00:00+00:00"
ACCEPTED_AT = "2026-09-02T10:01:00+00:00"


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _context() -> dict[str, object]:
    return {
        "context_pack_version": "context-v1",
        "context_policy_version": "policy-v1",
        "feedback_kind": "multi_period_decision_feedback",
        "reflection_stage": "early",
        "window": {
            "start_period": 1,
            "end_period": 4,
            "periods_reviewed": 4,
        },
        "statistics": {
            "window": {
                "start_period": 1,
                "end_period": 4,
                "periods_reviewed": 4,
            },
        },
        "information_environment": {},
        "participant_reflections": [],
        "prior_context": None,
        "context_coverage": {},
    }


def _prompt(context: dict[str, object]) -> dict[str, object]:
    return {
        "prompt_contract_version": "prompt-v1",
        "context_pack_version": "context-v1",
        "context_policy_version": "policy-v1",
        "context_sha256": _sha256_json(context),
        "feedback_kind": "multi_period_decision_feedback",
        "system_prompt": "SYSTEM",
        "user_prompt": "USER",
    }


def _candidate(
    *,
    suffix: str = "one",
    generation_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    context = _context()
    prompt = _prompt(context)
    reflection = " ".join(
        [f"reflection-{suffix}"] * 120
    )
    validated = {
        "feedback_kind": "multi_period_decision_feedback",
        "reflection": reflection,
    }
    metadata = generation_metadata or {
        "provider": "openai",
        "api_surface": "responses",
        "requested_model": "gpt-5-nano",
        "resolved_model": "gpt-5-nano-snapshot",
        "generator_contract_version": "formal-generator-v2",
        "attempt_count": 1,
        "provider_response_id": f"response-{suffix}",
        "provider_request_id": f"request-{suffix}",
    }
    return build_candidate_record(
        context_pack=context,
        prompt=prompt,
        generator_id="formal-generator-id-v2",
        generation_metadata=metadata,
        raw_output=json.dumps(validated),
        validated_output=validated,
        output_contract_version="output-v1",
        output_sha256=_sha256_json(validated),
        word_count=120,
        generated_at=GENERATED_AT,
    )


def _review(
    candidate: dict[str, object],
    decision: str,
    *,
    reviewer: str = "reviewer-001",
) -> dict[str, object]:
    return build_review_record(
        candidate=candidate,
        decision=decision,
        reviewer_id=reviewer,
        reviewed_at=REVIEWED_AT,
        review_notes="Reviewed against the frozen checklist.",
    )


def test_accept_round_trip_is_immutable_and_self_verifying(
    tmp_path,
):
    store = FeedbackReviewArtifactStore(tmp_path / "artifacts")
    candidate = _candidate()
    review = _review(candidate, REVIEW_ACCEPT)

    candidate_path = store.write_candidate(candidate)
    review_path = store.write_review(review)
    accepted_path = store.promote_accepted(
        prompt_sha256=str(candidate["prompt_sha256"]),
        candidate_sha256=str(candidate["candidate_sha256"]),
        accepted_at=ACCEPTED_AT,
    )

    assert candidate_path.parent.parent.name == "candidates"
    assert review_path.parent.name == "reviews"
    assert accepted_path.parent.name == "accepted"

    accepted = store.load_accepted(
        str(candidate["prompt_sha256"])
    )
    assert candidate["status"] == CANDIDATE_STATUS
    assert review["status"] == REVIEW_STATUS
    assert accepted["status"] == ACCEPTED_STATUS
    assert accepted["candidate_sha256"] == (
        candidate["candidate_sha256"]
    )
    assert accepted["review_sha256"] == review["review_sha256"]
    assert accepted["validated_output"] == (
        candidate["validated_output"]
    )

    assert store.write_candidate(candidate) == candidate_path
    assert store.write_review(review) == review_path


def test_rejected_candidate_cannot_be_promoted(tmp_path):
    store = FeedbackReviewArtifactStore(tmp_path / "artifacts")
    candidate = _candidate()
    store.write_candidate(candidate)
    store.write_review(_review(candidate, REVIEW_REJECT))

    with pytest.raises(
        FeedbackReviewArtifactError,
        match="only an ACCEPT review",
    ):
        store.promote_accepted(
            prompt_sha256=str(candidate["prompt_sha256"]),
            candidate_sha256=str(candidate["candidate_sha256"]),
            accepted_at=ACCEPTED_AT,
        )

    assert not (tmp_path / "artifacts" / "accepted").exists()


def test_same_prompt_supports_multiple_candidate_attempts(tmp_path):
    store = FeedbackReviewArtifactStore(tmp_path / "artifacts")
    first = _candidate(suffix="first")
    second = _candidate(suffix="second")

    assert first["prompt_sha256"] == second["prompt_sha256"]
    assert first["candidate_sha256"] != second["candidate_sha256"]

    store.write_candidate(first)
    store.write_candidate(second)
    store.write_review(_review(first, REVIEW_REJECT))
    store.write_review(_review(second, REVIEW_ACCEPT))
    store.promote_accepted(
        prompt_sha256=str(second["prompt_sha256"]),
        candidate_sha256=str(second["candidate_sha256"]),
        accepted_at=ACCEPTED_AT,
    )

    accepted = store.load_accepted(str(second["prompt_sha256"]))
    assert accepted["candidate_sha256"] == second["candidate_sha256"]


def test_only_one_candidate_can_be_accepted_per_prompt(tmp_path):
    store = FeedbackReviewArtifactStore(tmp_path / "artifacts")
    first = _candidate(suffix="first")
    second = _candidate(suffix="second")

    for candidate in (first, second):
        store.write_candidate(candidate)
        store.write_review(_review(candidate, REVIEW_ACCEPT))

    store.promote_accepted(
        prompt_sha256=str(first["prompt_sha256"]),
        candidate_sha256=str(first["candidate_sha256"]),
        accepted_at=ACCEPTED_AT,
    )

    with pytest.raises(FeedbackReviewArtifactConflictError):
        store.promote_accepted(
            prompt_sha256=str(second["prompt_sha256"]),
            candidate_sha256=str(second["candidate_sha256"]),
            accepted_at="2026-09-02T10:02:00+00:00",
        )


def test_one_candidate_cannot_receive_conflicting_reviews(tmp_path):
    store = FeedbackReviewArtifactStore(tmp_path / "artifacts")
    candidate = _candidate()
    store.write_candidate(candidate)
    store.write_review(_review(candidate, REVIEW_REJECT))

    with pytest.raises(FeedbackReviewArtifactConflictError):
        store.write_review(
            _review(
                candidate,
                REVIEW_ACCEPT,
                reviewer="reviewer-002",
            )
        )


def test_tampered_candidate_fails_hash_verification():
    candidate = _candidate()
    tampered = deepcopy(candidate)
    tampered["word_count"] = 121

    with pytest.raises(
        FeedbackReviewArtifactError,
        match="candidate record hash mismatch",
    ):
        verify_candidate_record(tampered)


def test_generation_metadata_rejects_credentials():
    with pytest.raises(
        FeedbackReviewArtifactError,
        match="secret field is forbidden",
    ):
        _candidate(
            generation_metadata={
                "provider": "openai",
                "api_key": "redacted-but-forbidden",
            }
        )

    with pytest.raises(
        FeedbackReviewArtifactError,
        match="credential-shaped value",
    ):
        _candidate(
            generation_metadata={
                "provider": "openai",
                "opaque": "sk-not-stored",
            }
        )


def test_digest_paths_reject_traversal(tmp_path):
    store = FeedbackReviewArtifactStore(tmp_path / "artifacts")
    with pytest.raises(
        FeedbackReviewArtifactError,
        match="lowercase SHA-256",
    ):
        store.load_accepted("../../config/feedback.yaml")
