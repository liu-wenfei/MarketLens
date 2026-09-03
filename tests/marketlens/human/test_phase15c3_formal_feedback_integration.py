from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import openai
import pytest

from marketlens.human.feedback import (
    FORMAL_CONTEXT_LIMITS,
    FrozenFeedbackPrompt,
)
from marketlens.human.formal_feedback_generator import (
    FORMAL_GENERATION_STATUS,
    FORMAL_GENERATOR_ID,
    FormalFeedbackGenerationError,
    OpenAIResponsesFormalFeedbackGenerator,
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

    first_request = client.responses.calls[0]
    second_request = client.responses.calls[1]

    assert {
        key: value
        for key, value in first_request.items()
        if key != "input"
    } == {
        key: value
        for key, value in second_request.items()
        if key != "input"
    }

    assert second_request["input"].startswith(
        first_request["input"]
    )
    assert "CORRECTION REQUIRED" in second_request["input"]
    assert "<validation_reason>" in second_request["input"]
    assert result.output == "ACCEPT"
    assert validated == {"accepted": "ACCEPT"}
    assert result.metadata["attempt_count"] == 2

    history = result.metadata["attempt_history"]
    assert len(history) == 2
    assert history[0]["outcome"] == "validation_rejected"
    assert history[1]["outcome"] == "validated"
    assert "output_sha256" in history[0]


def test_two_validation_rejections_fallback_without_third_request():
    client = _FakeClient(
        [
            _response("REJECT", "first"),
            _response("REJECT", "second"),
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
    assert result.metadata["fallback_used"] is True
    assert result.metadata["fallback_trigger"] == (
        "output_validation_exhausted"
    )
    assert validated == {"accepted": result.output}
    assert len(result.metadata["attempt_history"]) == 2


def test_transient_and_rejection_share_budget_then_fallback():
    client = _FakeClient(
        [
            _timeout_error(),
            _response("REJECT", "second"),
        ]
    )
    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=client
    )

    result, _ = generator.generate_validated(
        _prompt(),
        validator=_validator,
        validation_error_types=(_RejectedOutput,),
    )

    assert len(client.responses.calls) == 2
    assert result.metadata["fallback_trigger"] == (
        "output_validation_exhausted"
    )
    assert [
        item["outcome"]
        for item in result.metadata["attempt_history"]
    ] == ["transient_provider_error", "validation_rejected"]


def test_failed_local_fallback_validation_retains_attempt_history():
    client = _FakeClient(
        [
            _response("REJECT", "first"),
            _response("REJECT", "second"),
        ]
    )
    generator = OpenAIResponsesFormalFeedbackGenerator(client=client)

    def reject_everything(_output):
        raise _RejectedOutput("reject provider and fallback")

    with pytest.raises(FormalFeedbackGenerationError) as captured:
        generator.generate_validated(
            _prompt(),
            validator=reject_everything,
            validation_error_types=(_RejectedOutput,),
        )

    assert len(captured.value.attempt_history) == 2
    assert captured.value.fallback_trigger == (
        "output_validation_exhausted"
    )
    assert len(client.responses.calls) == 2


def test_formal_factory_rejects_nonformal_smoke_generator(
    tmp_path,
):
    with pytest.raises(
        FormalParticipantServerConfigurationError,
        match="frozen live formal provider generator",
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


def test_formal_factory_accepts_live_provider_generator_at_runtime(
    tmp_path,
):
    client = _FakeClient(
        [_response("NOT CALLED", "unused")]
    )
    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=client
    )
    app = create_formal_participant_app(
        repo_root=ROOT,
        db_path=tmp_path / "formal-human.db",
        participant_event_db_path=(
            tmp_path / "formal-events.db"
        ),
        feedback_generator=generator,
    )

    try:
        preparation = app.state.feedback_preparation_service
        assert preparation.generator is generator
        assert preparation.generator_id == FORMAL_GENERATOR_ID
        assert preparation.generation_status == FORMAL_GENERATION_STATUS
        assert preparation.limits == FORMAL_CONTEXT_LIMITS
        assert app.state.formal_feedback_runtime_policy[
            "policy_version"
        ] == "marketlens-formal-live-adaptive-feedback-v1"
        assert client.responses.calls == []
    finally:
        app.state.formal_participant_event_store.dispose()
        app.state.db.dispose()


def test_formal_factory_rejects_review_artifacts_at_live_runtime(
    tmp_path,
):
    artifact_root = tmp_path / "review-artifacts"
    artifact_root.mkdir()

    with pytest.raises(
        FormalParticipantServerConfigurationError,
        match="offline review-tool input",
    ):
        create_formal_participant_app(
            repo_root=ROOT,
            db_path=tmp_path / "reviewed-human.db",
            participant_event_db_path=(
                tmp_path / "reviewed-events.db"
            ),
            accepted_feedback_root=artifact_root,
        )


def test_formal_factory_rejects_manual_metadata_override(
    tmp_path,
):
    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=_FakeClient([_response("NOT CALLED", "unused")])
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
            feedback_context_limits=FORMAL_CONTEXT_LIMITS,
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


def test_corrective_retry_uses_validator_reason_without_rejected_output():
    rejected_output = "RAW_REJECTED_OUTPUT_SENTINEL"

    client = _FakeClient(
        [
            _response(rejected_output, "first"),
            _response("ACCEPT", "second"),
        ]
    )

    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=client
    )

    def validator(output):
        if output == rejected_output:
            raise _RejectedOutput(
                "backend-owned validator reason"
            )
        return {"accepted": output}

    result, validated = generator.generate_validated(
        _prompt(),
        validator=validator,
        validation_error_types=(_RejectedOutput,),
    )

    assert len(client.responses.calls) == 2

    first_input = client.responses.calls[0]["input"]
    second_input = client.responses.calls[1]["input"]

    assert second_input.startswith(first_input)
    assert "CORRECTION REQUIRED" in second_input
    assert (
        "backend-owned validator reason"
        in second_input
    )

    assert (
        "The original word-count requirement remains mandatory."
        in second_input
    )
    assert (
        "For this feedback checkpoint, the reflection MUST contain "
        "110-170 English words."
        in second_input
    )

    assert (
        "Do not shorten the reflection in order to repair the "
        "rejected language."
        in second_input
    )

    assert (
        "the exact word-count range stated in the original request."
        in second_input
    )

    assert rejected_output not in second_input

    history = result.metadata["attempt_history"]

    assert history[0]["request_mode"] == "base"
    assert (
        history[1]["request_mode"]
        == "corrective_retry"
    )
    assert (
        history[1]["corrective_retry_reason"]
        == "backend-owned validator reason"
    )

    assert result.metadata["corrective_retry_used"] is True
    assert result.metadata["fallback_used"] is False
    assert validated == {"accepted": "ACCEPT"}
