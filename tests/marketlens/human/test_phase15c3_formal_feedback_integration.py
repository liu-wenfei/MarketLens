from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai
import pytest

from marketlens.human.feedback import FrozenFeedbackPrompt
from marketlens.human.formal_feedback_generator import (
    OpenAIResponsesFormalFeedbackGenerator,
)
from marketlens.human.feedback.review_artifacts import (
    FeedbackReviewArtifactStore,
)
from marketlens.human.feedback.reviewed_runtime import (
    REVIEWED_RUNTIME_GENERATION_STATUS,
    REVIEWED_RUNTIME_GENERATOR_ID,
    ReviewedAcceptedFeedbackGenerator,
)
from marketlens.participant_server import (
    NONFORMAL_SMOKE_CONTEXT_LIMITS,
    FormalParticipantServerConfigurationError,
    create_formal_participant_app,
    create_nonformal_smoke_participant_app,
    nonformal_smoke_feedback_generator,
)


ROOT = Path(__file__).resolve().parents[3]


class _RejectedOutput(ValueError):
    pass


class _FakeResponses:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _FakeClient:
    def __init__(self, outcomes):
        self.responses = _FakeResponses(outcomes)


def _prompt() -> FrozenFeedbackPrompt:
    return FrozenFeedbackPrompt(
        prompt_contract_version="prompt-test-v1",
        context_pack_version="context-test-v1",
        context_policy_version="policy-test-v1",
        context_sha256="b" * 64,
        feedback_kind="multi_period_decision_feedback",
        system_prompt="SYSTEM PROMPT",
        user_prompt="USER PROMPT",
    )


def _response(output: str, suffix: str):
    return SimpleNamespace(
        id=f"resp-{suffix}",
        _request_id=f"req-{suffix}",
        model="gpt-5-nano",
        status="completed",
        output_text=output,
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=30,
            total_tokens=130,
        ),
    )


def _timeout_error():
    return openai.APITimeoutError(
        request=httpx.Request(
            "POST",
            "https://api.openai.com/v1/responses",
        )
    )


def _validator(output):
    if output == "REJECT":
        raise _RejectedOutput("deterministic rejection")
    return {"accepted": output}


def test_validation_rejection_uses_same_two_attempt_budget():
    client = _FakeClient(
        [
            _response("REJECT", "first"),
            _response("ACCEPT", "second"),
        ]
    )
    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=client
    )

    result, validated = generator.generate_validated(
        _prompt(),
        validator=_validator,
        validation_error_types=(_RejectedOutput,),
    )

    assert len(client.responses.calls) == 2
    assert (
        client.responses.calls[0]
        == client.responses.calls[1]
    )
    assert result.output == "ACCEPT"
    assert validated == {"accepted": "ACCEPT"}
    assert result.metadata["attempt_count"] == 2

    history = result.metadata["attempt_history"]
    assert len(history) == 2
    assert history[0]["outcome"] == "validation_rejected"
    assert history[1]["outcome"] == "validated"
    assert "output_sha256" in history[0]


def test_two_validation_rejections_fail_without_third_request():
    client = _FakeClient(
        [
            _response("REJECT", "first"),
            _response("REJECT", "second"),
        ]
    )
    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=client
    )

    with pytest.raises(_RejectedOutput):
        generator.generate_validated(
            _prompt(),
            validator=_validator,
            validation_error_types=(_RejectedOutput,),
        )

    assert len(client.responses.calls) == 2


def test_transient_failure_consumes_shared_attempt_budget():
    client = _FakeClient(
        [
            _timeout_error(),
            _response("REJECT", "second"),
        ]
    )
    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=client
    )

    with pytest.raises(_RejectedOutput):
        generator.generate_validated(
            _prompt(),
            validator=_validator,
            validation_error_types=(_RejectedOutput,),
        )

    assert len(client.responses.calls) == 2


def test_formal_factory_rejects_nonformal_smoke_generator(
    tmp_path,
):
    with pytest.raises(
        FormalParticipantServerConfigurationError,
        match="reviewed accepted artifact generator",
    ):
        create_formal_participant_app(
            repo_root=ROOT,
            db_path=tmp_path / "rejected-human.db",
            participant_event_db_path=(
                tmp_path / "rejected-events.db"
            ),
            feedback_generator=(
                nonformal_smoke_feedback_generator
            ),
            feedback_context_limits=(
                NONFORMAL_SMOKE_CONTEXT_LIMITS
            ),
            feedback_generator_id=(
                "marketlens-nonformal-"
                "deterministic-smoke-v1"
            ),
            feedback_generation_status=(
                "nonformal_smoke_validated"
            ),
        )

    assert not (tmp_path / "rejected-human.db").exists()
    assert not (tmp_path / "rejected-events.db").exists()


def test_formal_factory_rejects_provider_generator_at_runtime(
    tmp_path,
):
    client = _FakeClient(
        [_response("NOT CALLED", "unused")]
    )
    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=client
    )
    with pytest.raises(
        FormalParticipantServerConfigurationError,
        match="provider generation is prohibited",
    ):
        create_formal_participant_app(
            repo_root=ROOT,
            db_path=tmp_path / "formal-human.db",
            participant_event_db_path=(
                tmp_path / "formal-events.db"
            ),
            feedback_generator=generator,
            feedback_context_limits=(
                NONFORMAL_SMOKE_CONTEXT_LIMITS
            ),
        )

    assert client.responses.calls == []
    assert not (tmp_path / "formal-human.db").exists()
    assert not (tmp_path / "formal-events.db").exists()


def test_formal_factory_derives_reviewed_runtime_identity(
    tmp_path,
):
    artifact_root = tmp_path / "review-artifacts"
    artifact_root.mkdir()
    limits = replace(
        NONFORMAL_SMOKE_CONTEXT_LIMITS,
        policy_version=(
            "marketlens-formal-feedback-context-test-v1"
        ),
    )

    app = create_formal_participant_app(
        repo_root=ROOT,
        db_path=tmp_path / "reviewed-human.db",
        participant_event_db_path=(
            tmp_path / "reviewed-events.db"
        ),
        accepted_feedback_root=artifact_root,
        feedback_context_limits=limits,
    )

    try:
        preparation = app.state.feedback_preparation_service
        assert preparation is not None
        assert isinstance(
            preparation.generator,
            ReviewedAcceptedFeedbackGenerator,
        )
        assert preparation.generator.store.root == artifact_root
        assert preparation.generator_id == (
            REVIEWED_RUNTIME_GENERATOR_ID
        )
        assert preparation.generation_status == (
            REVIEWED_RUNTIME_GENERATION_STATUS
        )
        assert preparation.generation_metadata == (
            preparation.generator.static_metadata()
        )
    finally:
        app.state.formal_participant_event_store.dispose()
        app.state.db.dispose()


def test_formal_factory_rejects_manual_metadata_override(
    tmp_path,
):
    artifact_root = tmp_path / "metadata-artifacts"
    artifact_root.mkdir()
    generator = ReviewedAcceptedFeedbackGenerator(
        store=FeedbackReviewArtifactStore(artifact_root)
    )

    with pytest.raises(
        FormalParticipantServerConfigurationError,
        match="metadata is derived",
    ):
        create_formal_participant_app(
            repo_root=ROOT,
            db_path=tmp_path / "metadata-human.db",
            participant_event_db_path=(
                tmp_path / "metadata-events.db"
            ),
            feedback_generator=generator,
            feedback_context_limits=(
                NONFORMAL_SMOKE_CONTEXT_LIMITS
            ),
            feedback_generation_metadata={
                "provider": "overridden",
            },
        )

    assert not (tmp_path / "metadata-human.db").exists()
    assert not (tmp_path / "metadata-events.db").exists()


def test_nonformal_smoke_factory_remains_available(
    tmp_path,
):
    app = create_nonformal_smoke_participant_app(
        repo_root=ROOT,
        db_path=tmp_path / "smoke-human.db",
        participant_event_db_path=(
            tmp_path / "smoke-events.db"
        ),
    )

    try:
        preparation = (
            app.state.feedback_preparation_service
        )
        assert preparation is not None
        assert (
            preparation.generator
            is nonformal_smoke_feedback_generator
        )
        assert (
            preparation.generation_status
            == "nonformal_smoke_validated"
        )
    finally:
        app.state.formal_participant_event_store.dispose()
        app.state.db.dispose()
