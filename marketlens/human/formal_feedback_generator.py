"""Frozen formal feedback-provider adapter for MarketLens.

This module owns only the provider boundary. It does not build participant
statistics, context, prompts, validate feedback semantics, or persist output.
No client is instantiated and no environment variable is read at import time.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from typing import Any, Callable, Mapping, Protocol

import openai

from marketlens.human.feedback import (
    FeedbackGenerationResult,
    FrozenFeedbackPrompt,
)


FORMAL_GENERATOR_CONTRACT_VERSION = (
    "marketlens-formal-feedback-generator-v2"
)
FORMAL_GENERATOR_ID = (
    "marketlens-openai-responses-gpt-5-nano-v2"
)
FORMAL_GENERATION_STATUS = "formal_provider_validated"
FORMAL_PROVIDER = "openai"
FORMAL_API_SURFACE = "responses"
FORMAL_MODEL = "gpt-5-nano"
FORMAL_REASONING_EFFORT = "minimal"
FORMAL_MAX_OUTPUT_TOKENS = 1024
FORMAL_TIMEOUT_SECONDS = 45.0
FORMAL_SDK_MAX_RETRIES = 0
FORMAL_MAX_PROVIDER_ATTEMPTS = 2
FORMAL_OPENAI_SDK_VERSION = "2.54.0"


class FormalFeedbackConfigurationError(ValueError):
    """Raised before a formal provider request when configuration is unsafe."""


class FormalFeedbackGenerationError(RuntimeError):
    """Raised when bounded formal provider generation fails closed."""


class ResponsesClient(Protocol):
    def create(self, **kwargs: Any) -> object:
        ...


class OpenAIClient(Protocol):
    responses: ResponsesClient


@dataclass(frozen=True, slots=True)
class FormalFeedbackGeneratorConfig:
    """Exact Phase 15C3B v2 configuration; variants require a new version."""

    contract_version: str = FORMAL_GENERATOR_CONTRACT_VERSION
    generator_id: str = FORMAL_GENERATOR_ID
    generation_status: str = FORMAL_GENERATION_STATUS
    provider: str = FORMAL_PROVIDER
    api_surface: str = FORMAL_API_SURFACE
    model: str = FORMAL_MODEL
    reasoning_effort: str = FORMAL_REASONING_EFFORT
    max_output_tokens: int = FORMAL_MAX_OUTPUT_TOKENS
    timeout_seconds: float = FORMAL_TIMEOUT_SECONDS
    sdk_max_retries: int = FORMAL_SDK_MAX_RETRIES
    max_provider_attempts: int = FORMAL_MAX_PROVIDER_ATTEMPTS
    openai_sdk_version: str = FORMAL_OPENAI_SDK_VERSION

    def validate(self) -> None:
        expected = {
            "contract_version": FORMAL_GENERATOR_CONTRACT_VERSION,
            "generator_id": FORMAL_GENERATOR_ID,
            "generation_status": FORMAL_GENERATION_STATUS,
            "provider": FORMAL_PROVIDER,
            "api_surface": FORMAL_API_SURFACE,
            "model": FORMAL_MODEL,
            "reasoning_effort": FORMAL_REASONING_EFFORT,
            "max_output_tokens": FORMAL_MAX_OUTPUT_TOKENS,
            "timeout_seconds": FORMAL_TIMEOUT_SECONDS,
            "sdk_max_retries": FORMAL_SDK_MAX_RETRIES,
            "max_provider_attempts": FORMAL_MAX_PROVIDER_ATTEMPTS,
            "openai_sdk_version": FORMAL_OPENAI_SDK_VERSION,
        }

        for name, required in expected.items():
            if getattr(self, name) != required:
                raise FormalFeedbackConfigurationError(
                    f"formal generator {name} must equal {required!r}"
                )

        installed = str(openai.__version__)
        if installed != self.openai_sdk_version:
            raise FormalFeedbackConfigurationError(
                "formal OpenAI SDK version mismatch: "
                f"expected {self.openai_sdk_version}, got {installed}"
            )

    def static_metadata(self) -> dict[str, object]:
        self.validate()
        return {
            "provider": self.provider,
            "api_surface": self.api_surface,
            "requested_model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "max_output_tokens": self.max_output_tokens,
            "timeout_seconds": self.timeout_seconds,
            "sdk_max_retries": self.sdk_max_retries,
            "formal_max_attempts": self.max_provider_attempts,
            "openai_sdk_version": self.openai_sdk_version,
            "generator_contract_version": self.contract_version,
        }


FormalFeedbackGenerationResult = FeedbackGenerationResult


def _retryable_provider_error(exc: BaseException) -> bool:
    if isinstance(
        exc,
        (
            openai.APIConnectionError,
            openai.APITimeoutError,
        ),
    ):
        return True

    if isinstance(exc, openai.APIStatusError):
        status = int(exc.status_code)
        return status in {408, 409, 429} or status >= 500

    return False


def _usage_metadata(response: object) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}

    result: dict[str, int] = {}
    for name in (
        "input_tokens",
        "output_tokens",
        "total_tokens",
    ):
        value = getattr(usage, name, None)
        if isinstance(value, int) and not isinstance(value, bool):
            result[name] = value
    return result


class OpenAIResponsesFormalFeedbackGenerator:
    """Callable OpenAI Responses adapter with bounded transient retries."""

    def __init__(
        self,
        *,
        client: OpenAIClient,
        config: FormalFeedbackGeneratorConfig | None = None,
    ) -> None:
        resolved = config or FormalFeedbackGeneratorConfig()
        resolved.validate()

        if client is None or not hasattr(client, "responses"):
            raise FormalFeedbackConfigurationError(
                "formal generator requires a Responses-capable client"
            )

        self._client = client
        self.config = resolved

    @property
    def generator_id(self) -> str:
        return self.config.generator_id

    @property
    def generation_status(self) -> str:
        return self.config.generation_status

    @property
    def formal_contract_version(self) -> str:
        return self.config.contract_version

    def _request_once(
        self,
        prompt: FrozenFeedbackPrompt,
    ) -> object:
        return self._client.responses.create(
            model=self.config.model,
            instructions=prompt.system_prompt,
            input=prompt.user_prompt,
            reasoning={
                "effort": self.config.reasoning_effort,
            },
            max_output_tokens=(
                self.config.max_output_tokens
            ),
            store=False,
            stream=False,
            background=False,
            truncation="disabled",
        )

    @staticmethod
    def _response_record(
        *,
        attempt_number: int,
        outcome: str,
        response: object,
        output: str,
    ) -> dict[str, object]:
        return {
            "attempt_number": attempt_number,
            "outcome": outcome,
            "provider_response_id": str(
                getattr(response, "id", "")
            ),
            "provider_request_id": str(
                getattr(response, "_request_id", "")
            ),
            "resolved_model": str(
                getattr(response, "model", "")
            ),
            "output_sha256": sha256(
                output.encode("utf-8")
            ).hexdigest(),
        }

    def generate_validated(
        self,
        prompt: FrozenFeedbackPrompt,
        *,
        validator: Callable[[object], object],
        validation_error_types: tuple[
            type[BaseException], ...
        ],
    ) -> tuple[FeedbackGenerationResult, object]:
        if not isinstance(prompt, FrozenFeedbackPrompt):
            raise FormalFeedbackGenerationError(
                "formal generation requires a FrozenFeedbackPrompt"
            )
        if not callable(validator):
            raise FormalFeedbackGenerationError(
                "formal generation requires a validator"
            )
        if not isinstance(validation_error_types, tuple) or not all(
            isinstance(item, type)
            and issubclass(item, BaseException)
            for item in validation_error_types
        ):
            raise FormalFeedbackGenerationError(
                "validation_error_types must be exception classes"
            )

        attempts = 0
        attempt_history: list[dict[str, object]] = []

        while attempts < self.config.max_provider_attempts:
            attempts += 1
            try:
                response = self._request_once(prompt)
            except Exception as exc:
                retryable = _retryable_provider_error(exc)
                attempt_history.append(
                    {
                        "attempt_number": attempts,
                        "outcome": (
                            "transient_provider_error"
                            if retryable
                            else "nonretryable_provider_error"
                        ),
                        "error_type": type(exc).__name__,
                    }
                )
                if (
                    retryable
                    and attempts
                    < self.config.max_provider_attempts
                ):
                    continue
                category = (
                    "transient provider failure exhausted"
                    if retryable
                    else "non-retryable provider failure"
                )
                raise FormalFeedbackGenerationError(
                    f"formal feedback generation failed: {category}"
                ) from exc

            status = getattr(response, "status", None)
            if status != "completed":
                raise FormalFeedbackGenerationError(
                    "formal provider response was not completed"
                )

            output = getattr(response, "output_text", None)
            if not isinstance(output, str) or not output.strip():
                raise FormalFeedbackGenerationError(
                    "formal provider returned empty output"
                )

            try:
                validated = validator(output)
            except validation_error_types:
                attempt_history.append(
                    self._response_record(
                        attempt_number=attempts,
                        outcome="validation_rejected",
                        response=response,
                        output=output,
                    )
                )
                if attempts < self.config.max_provider_attempts:
                    continue
                raise

            attempt_history.append(
                self._response_record(
                    attempt_number=attempts,
                    outcome="validated",
                    response=response,
                    output=output,
                )
            )

            metadata = self.config.static_metadata()
            metadata.update(
                {
                    "attempt_count": attempts,
                    "attempt_history": attempt_history,
                    "provider_response_id": str(
                        getattr(response, "id", "")
                    ),
                    "provider_request_id": str(
                        getattr(response, "_request_id", "")
                    ),
                    "resolved_model": str(
                        getattr(response, "model", "")
                    ),
                    "provider_response_status": status,
                }
            )
            metadata.update(_usage_metadata(response))

            return (
                FeedbackGenerationResult(
                    output=output,
                    metadata=metadata,
                ),
                validated,
            )

        raise FormalFeedbackGenerationError(
            "formal feedback attempt budget was exhausted"
        )

    def __call__(
        self,
        prompt: FrozenFeedbackPrompt,
    ) -> FeedbackGenerationResult:
        result, _ = self.generate_validated(
            prompt,
            validator=lambda output: output,
            validation_error_types=(),
        )
        return result


def is_formal_feedback_generator(value: object) -> bool:
    if not isinstance(
        value,
        OpenAIResponsesFormalFeedbackGenerator,
    ):
        return False
    try:
        value.config.validate()
    except FormalFeedbackConfigurationError:
        return False
    return (
        value.generator_id == FORMAL_GENERATOR_ID
        and value.generation_status == FORMAL_GENERATION_STATUS
        and value.formal_contract_version
        == FORMAL_GENERATOR_CONTRACT_VERSION
    )


def create_formal_openai_feedback_generator(
    *,
    environ: Mapping[str, str] | None = None,
    client_factory: Callable[..., OpenAIClient] | None = None,
    config: FormalFeedbackGeneratorConfig | None = None,
) -> OpenAIResponsesFormalFeedbackGenerator:
    """Explicit environment/client boundary; never called at import time."""

    source = os.environ if environ is None else environ

    if str(source.get("OPENAI_BASE_URL", "")).strip():
        raise FormalFeedbackConfigurationError(
            "OPENAI_BASE_URL is prohibited in formal mode"
        )

    api_key = str(source.get("OPENAI_API_KEY", "")).strip()
    if not api_key:
        raise FormalFeedbackConfigurationError(
            "OPENAI_API_KEY is required in formal mode"
        )

    resolved = config or FormalFeedbackGeneratorConfig()
    resolved.validate()

    if client_factory is None:
        client_factory = openai.OpenAI

    client = client_factory(
        api_key=api_key,
        max_retries=resolved.sdk_max_retries,
        timeout=resolved.timeout_seconds,
    )

    return OpenAIResponsesFormalFeedbackGenerator(
        client=client,
        config=resolved,
    )
