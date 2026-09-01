from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace

import httpx
import openai
import pytest

from marketlens.human.feedback import FrozenFeedbackPrompt
from marketlens.human.formal_feedback_generator import (
    FORMAL_GENERATION_STATUS,
    FORMAL_GENERATOR_CONTRACT_VERSION,
    FORMAL_GENERATOR_ID,
    FormalFeedbackConfigurationError,
    FormalFeedbackGenerationError,
    FormalFeedbackGeneratorConfig,
    OpenAIResponsesFormalFeedbackGenerator,
    create_formal_openai_feedback_generator,
    is_formal_feedback_generator,
)


def _prompt() -> FrozenFeedbackPrompt:
    return FrozenFeedbackPrompt(
        prompt_contract_version="prompt-test-v1",
        context_pack_version="context-test-v1",
        context_policy_version="policy-test-v1",
        context_sha256="a" * 64,
        feedback_kind="multi_period_decision_feedback",
        system_prompt="SYSTEM PROMPT",
        user_prompt="USER PROMPT",
    )


def _response(output: str = '{"feedback_kind":"x"}'):
    return SimpleNamespace(
        id="resp-test-001",
        _request_id="req-test-001",
        model="gpt-5.6-terra",
        status="completed",
        output_text=output,
        usage=SimpleNamespace(
            input_tokens=120,
            output_tokens=40,
            total_tokens=160,
        ),
    )


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


def _timeout_error():
    return openai.APITimeoutError(
        request=httpx.Request(
            "POST",
            "https://api.openai.com/v1/responses",
        )
    )


def _authentication_error():
    request = httpx.Request(
        "POST",
        "https://api.openai.com/v1/responses",
    )
    response = httpx.Response(
        401,
        request=request,
    )
    return openai.AuthenticationError(
        "authentication failed",
        response=response,
        body=None,
    )


def test_frozen_configuration_matches_15c3b_contract():
    config = FormalFeedbackGeneratorConfig()
    config.validate()

    assert config.model == "gpt-5.6-terra"
    assert config.reasoning_effort == "none"
    assert config.max_output_tokens == 1024
    assert config.timeout_seconds == 45.0
    assert config.sdk_max_retries == 0
    assert config.max_provider_attempts == 2
    assert config.openai_sdk_version == "2.54.0"
    assert config.generator_id == FORMAL_GENERATOR_ID
    assert config.generation_status == FORMAL_GENERATION_STATUS

    with pytest.raises(FrozenInstanceError):
        config.model = "gpt-5.6"


def test_configuration_variants_require_new_contract():
    config = replace(
        FormalFeedbackGeneratorConfig(),
        model="gpt-5.6",
    )

    with pytest.raises(
        FormalFeedbackConfigurationError,
        match="model",
    ):
        config.validate()


def test_request_uses_exact_frozen_shape():
    client = _FakeClient([_response()])
    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=client
    )

    result = generator(_prompt())

    assert len(client.responses.calls) == 1
    request = client.responses.calls[0]
    assert request == {
        "model": "gpt-5.6-terra",
        "instructions": "SYSTEM PROMPT",
        "input": "USER PROMPT",
        "reasoning": {"effort": "none"},
        "max_output_tokens": 1024,
        "store": False,
        "stream": False,
        "background": False,
        "truncation": "disabled",
    }
    assert "temperature" not in request
    assert "top_p" not in request
    assert "tools" not in request

    assert result.output == '{"feedback_kind":"x"}'
    assert result.metadata["attempt_count"] == 1
    assert result.metadata["provider_response_id"] == (
        "resp-test-001"
    )
    assert result.metadata["provider_request_id"] == (
        "req-test-001"
    )
    assert result.metadata["resolved_model"] == (
        "gpt-5.6-terra"
    )
    assert result.metadata["input_tokens"] == 120
    assert result.metadata["output_tokens"] == 40
    assert result.metadata["total_tokens"] == 160
    assert "api_key" not in result.metadata


def test_transient_failure_retries_exactly_once():
    client = _FakeClient(
        [_timeout_error(), _response()]
    )
    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=client
    )

    result = generator(_prompt())

    assert len(client.responses.calls) == 2
    assert result.metadata["attempt_count"] == 2


def test_transient_failure_exhaustion_fails_closed():
    client = _FakeClient(
        [_timeout_error(), _timeout_error()]
    )
    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=client
    )

    with pytest.raises(
        FormalFeedbackGenerationError,
        match="transient provider failure exhausted",
    ):
        generator(_prompt())

    assert len(client.responses.calls) == 2


def test_nonretryable_failure_is_not_retried():
    client = _FakeClient([_authentication_error()])
    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=client
    )

    with pytest.raises(
        FormalFeedbackGenerationError,
        match="non-retryable provider failure",
    ):
        generator(_prompt())

    assert len(client.responses.calls) == 1


def test_incomplete_or_empty_response_fails_closed():
    incomplete = _response()
    incomplete.status = "incomplete"

    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=_FakeClient([incomplete])
    )
    with pytest.raises(
        FormalFeedbackGenerationError,
        match="not completed",
    ):
        generator(_prompt())

    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=_FakeClient([_response("  ")])
    )
    with pytest.raises(
        FormalFeedbackGenerationError,
        match="empty output",
    ):
        generator(_prompt())


def test_explicit_environment_boundary_rejects_unsafe_config():
    called = []

    def factory(**kwargs):
        called.append(kwargs)
        return _FakeClient([_response()])

    with pytest.raises(
        FormalFeedbackConfigurationError,
        match="OPENAI_API_KEY",
    ):
        create_formal_openai_feedback_generator(
            environ={},
            client_factory=factory,
        )

    with pytest.raises(
        FormalFeedbackConfigurationError,
        match="OPENAI_BASE_URL",
    ):
        create_formal_openai_feedback_generator(
            environ={
                "OPENAI_API_KEY": "not-a-real-key",
                "OPENAI_BASE_URL": "https://example.invalid",
            },
            client_factory=factory,
        )

    assert called == []


def test_explicit_factory_uses_key_without_persisting_it():
    captured = []

    def factory(**kwargs):
        captured.append(kwargs)
        return _FakeClient([_response()])

    generator = create_formal_openai_feedback_generator(
        environ={"OPENAI_API_KEY": "not-a-real-key"},
        client_factory=factory,
    )

    assert captured == [
        {
            "api_key": "not-a-real-key",
            "max_retries": 0,
            "timeout": 45.0,
        }
    ]
    assert "not-a-real-key" not in repr(generator.config)
    assert (
        "not-a-real-key"
        not in repr(generator.config.static_metadata())
    )


def test_identity_guard_accepts_only_frozen_formal_adapter():
    generator = OpenAIResponsesFormalFeedbackGenerator(
        client=_FakeClient([_response()])
    )

    assert is_formal_feedback_generator(generator)
    assert generator.generator_id == FORMAL_GENERATOR_ID
    assert generator.generation_status == FORMAL_GENERATION_STATUS
    assert (
        generator.formal_contract_version
        == FORMAL_GENERATOR_CONTRACT_VERSION
    )

    def nonformal_smoke_generator(prompt):
        return {"feedback_kind": prompt.feedback_kind}

    assert not is_formal_feedback_generator(
        nonformal_smoke_generator
    )
