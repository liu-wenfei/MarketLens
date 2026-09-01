from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import ast
import json
from pathlib import Path

import pytest

from marketlens.human.feedback import FrozenFeedbackPrompt
from marketlens.human.feedback.review_artifacts import (
    FeedbackReviewArtifactStore,
    build_candidate_record,
    build_review_record,
)
from marketlens.human.feedback.reviewed_runtime import (
    ReviewedAcceptedFeedbackGenerator,
    ReviewedAcceptedFeedbackRuntimeError,
)
import marketlens.participant_server as participant_server


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_json(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _prompt(context_sha256: str) -> FrozenFeedbackPrompt:
    return FrozenFeedbackPrompt(
        prompt_contract_version="prompt-v1",
        context_pack_version="context-v1",
        context_policy_version="policy-v1",
        context_sha256=context_sha256,
        feedback_kind="multi_period_decision_feedback",
        system_prompt="SYSTEM",
        user_prompt="USER",
    )


@dataclass(frozen=True)
class _Validated:
    payload: dict[str, object]
    output_contract_version: str
    output_sha256: str
    word_count: int


def _accepted_generator(tmp_path):
    store = FeedbackReviewArtifactStore(tmp_path / "artifacts")
    context = {"context_pack_version": "context-v1", "value": "safe"}
    prompt = _prompt(_sha256_json(context))
    output = {
        "feedback_kind": "multi_period_decision_feedback",
        "reflection": "A deliberately compact reviewed test reflection.",
    }
    output_sha256 = _sha256_json(output)
    candidate = build_candidate_record(
        context_pack=context,
        prompt=prompt.to_dict(),
        generator_id="offline-provider-generator-v1",
        generation_metadata={"provider": "test", "attempt_count": 1},
        raw_output=output,
        validated_output=output,
        output_contract_version="output-v1",
        output_sha256=output_sha256,
        word_count=6,
        generated_at="2026-09-01T10:00:00+00:00",
    )
    store.write_candidate(candidate)
    review = build_review_record(
        candidate=candidate,
        decision="ACCEPT",
        reviewer_id="reviewer-001",
        review_notes="Neutrality and contract checked.",
        reviewed_at="2026-09-01T11:00:00+00:00",
    )
    store.write_review(review)
    store.promote_accepted(
        prompt_sha256=str(candidate["prompt_sha256"]),
        candidate_sha256=str(candidate["candidate_sha256"]),
        accepted_at="2026-09-01T12:00:00+00:00",
    )
    return (
        ReviewedAcceptedFeedbackGenerator(store=store),
        prompt,
        output,
        output_sha256,
        candidate,
        review,
    )


def test_runtime_loads_only_exact_accepted_artifact(tmp_path):
    generator, prompt, output, output_hash, candidate, review = (
        _accepted_generator(tmp_path)
    )
    validator_calls = []

    def validator(value):
        validator_calls.append(value)
        return _Validated(
            payload=output,
            output_contract_version="output-v1",
            output_sha256=output_hash,
            word_count=6,
        )

    result, validated = generator.generate_validated(
        prompt,
        validator=validator,
        validation_error_types=(ValueError,),
    )

    assert validator_calls == [_canonical_json(output)]
    assert validated.payload == output
    assert json.loads(result.output) == output
    assert result.metadata["runtime_provider_requests"] == 0
    assert result.metadata["runtime_credential_reads"] == 0
    assert result.metadata["accepted_candidate_sha256"] == (
        candidate["candidate_sha256"]
    )
    assert result.metadata["accepted_review_sha256"] == (
        review["review_sha256"]
    )
    assert result.metadata["accepted_original_generator_id"] == (
        "offline-provider-generator-v1"
    )


def test_runtime_missing_accept_fails_before_validation(tmp_path):
    generator = ReviewedAcceptedFeedbackGenerator(
        store=FeedbackReviewArtifactStore(tmp_path / "empty")
    )
    context = {"context_pack_version": "context-v1"}
    prompt = _prompt(_sha256_json(context))
    validator_called = False

    def validator(value):
        nonlocal validator_called
        validator_called = True
        return value

    with pytest.raises(
        ReviewedAcceptedFeedbackRuntimeError,
        match="no exact verified ACCEPT",
    ):
        generator.generate_validated(
            prompt,
            validator=validator,
            validation_error_types=(ValueError,),
        )

    assert validator_called is False


def test_runtime_rejects_different_prompt(tmp_path):
    generator, prompt, *_ = _accepted_generator(tmp_path)
    changed = FrozenFeedbackPrompt(
        **{
            **prompt.to_dict(),
            "user_prompt": "DIFFERENT USER PROMPT",
        }
    )

    with pytest.raises(
        ReviewedAcceptedFeedbackRuntimeError,
        match="no exact verified ACCEPT",
    ):
        generator.generate_validated(
            changed,
            validator=lambda value: value,
            validation_error_types=(ValueError,),
        )


def test_runtime_rejects_validator_provenance_mismatch(tmp_path):
    generator, prompt, output, output_hash, *_ = _accepted_generator(
        tmp_path
    )

    with pytest.raises(
        ReviewedAcceptedFeedbackRuntimeError,
        match="word_count does not match",
    ):
        generator.generate_validated(
            prompt,
            validator=lambda value: _Validated(
                payload=output,
                output_contract_version="output-v1",
                output_sha256=output_hash,
                word_count=7,
            ),
            validation_error_types=(ValueError,),
        )


def test_participant_server_has_no_formal_provider_import():
    source_path = Path(participant_server.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
    }

    assert "marketlens.human.formal_feedback_generator" not in (
        imported_modules
    )
