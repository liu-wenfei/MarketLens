"""Provider-free participant runtime for reviewed ACCEPT artifacts only."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
import json
from pathlib import Path

from .generation import FeedbackGenerationResult
from .prompt import FrozenFeedbackPrompt
from .review_artifacts import (
    REVIEW_ARTIFACT_CONTRACT_VERSION,
    FeedbackReviewArtifactError,
    FeedbackReviewArtifactStore,
)


REVIEWED_RUNTIME_CONTRACT_VERSION = (
    "marketlens-formal-feedback-reviewed-runtime-v1"
)
REVIEWED_RUNTIME_GENERATOR_ID = (
    "marketlens-reviewed-accepted-feedback-runtime-v1"
)
REVIEWED_RUNTIME_GENERATION_STATUS = "formal_reviewed_accepted"


class ReviewedAcceptedFeedbackRuntimeError(ValueError):
    """Raised when runtime cannot load exact accepted feedback."""


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ReviewedAcceptedFeedbackRuntimeError(
            "reviewed runtime value is not canonical JSON"
        ) from exc


def _detached(value: object) -> object:
    return json.loads(_canonical_json(value))


def _sha256_json(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class ReviewedAcceptedFeedbackGenerator:
    """Load and revalidate one exact immutable accepted artifact."""

    def __init__(
        self,
        *,
        store: FeedbackReviewArtifactStore,
    ) -> None:
        if not isinstance(store, FeedbackReviewArtifactStore):
            raise ReviewedAcceptedFeedbackRuntimeError(
                "reviewed runtime requires a FeedbackReviewArtifactStore"
            )
        self.store = store

    @property
    def generator_id(self) -> str:
        return REVIEWED_RUNTIME_GENERATOR_ID

    @property
    def generation_status(self) -> str:
        return REVIEWED_RUNTIME_GENERATION_STATUS

    @property
    def formal_contract_version(self) -> str:
        return REVIEWED_RUNTIME_CONTRACT_VERSION

    def static_metadata(self) -> dict[str, object]:
        return {
            "runtime_feedback_source": "reviewed_accepted_artifact",
            "review_artifact_contract_version": (
                REVIEW_ARTIFACT_CONTRACT_VERSION
            ),
            "reviewed_runtime_contract_version": (
                REVIEWED_RUNTIME_CONTRACT_VERSION
            ),
            "runtime_provider_requests": 0,
            "runtime_credential_reads": 0,
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
            raise ReviewedAcceptedFeedbackRuntimeError(
                "reviewed runtime requires a FrozenFeedbackPrompt"
            )
        if not callable(validator):
            raise ReviewedAcceptedFeedbackRuntimeError(
                "reviewed runtime requires a validator"
            )
        if not isinstance(validation_error_types, tuple) or not all(
            isinstance(item, type)
            and issubclass(item, BaseException)
            for item in validation_error_types
        ):
            raise ReviewedAcceptedFeedbackRuntimeError(
                "validation_error_types must be exception classes"
            )

        prompt_payload = prompt.to_dict()
        prompt_sha256 = _sha256_json(prompt_payload)

        try:
            accepted = self.store.load_accepted(prompt_sha256)
            candidate = self.store.load_candidate(
                prompt_sha256,
                str(accepted["candidate_sha256"]),
            )
        except FeedbackReviewArtifactError as exc:
            raise ReviewedAcceptedFeedbackRuntimeError(
                "no exact verified ACCEPT artifact exists for prompt"
            ) from exc

        if candidate["prompt"] != prompt_payload:
            raise ReviewedAcceptedFeedbackRuntimeError(
                "accepted artifact prompt payload does not match runtime prompt"
            )

        raw_output = str(accepted["raw_output"])
        validated = validator(raw_output)
        validated_payload = getattr(validated, "payload", None)
        if not isinstance(validated_payload, Mapping):
            raise ReviewedAcceptedFeedbackRuntimeError(
                "runtime validator returned an invalid payload"
            )
        if _detached(dict(validated_payload)) != accepted["validated_output"]:
            raise ReviewedAcceptedFeedbackRuntimeError(
                "runtime validation does not match accepted output"
            )

        expected_validation = {
            "output_contract_version": accepted[
                "output_contract_version"
            ],
            "output_sha256": accepted["output_sha256"],
            "word_count": accepted["word_count"],
        }
        for field, expected in expected_validation.items():
            if getattr(validated, field, None) != expected:
                raise ReviewedAcceptedFeedbackRuntimeError(
                    f"runtime validated {field} does not match accepted artifact"
                )

        metadata = self.static_metadata()
        metadata.update(
            {
                "accepted_prompt_sha256": accepted["prompt_sha256"],
                "accepted_artifact_sha256": accepted["accepted_sha256"],
                "accepted_candidate_sha256": accepted["candidate_sha256"],
                "accepted_review_sha256": accepted["review_sha256"],
                "accepted_reviewer_id": accepted["reviewer_id"],
                "accepted_original_generator_id": accepted["generator_id"],
                "accepted_original_generation_metadata": accepted[
                    "generation_metadata"
                ],
                "accepted_generated_at": accepted["generated_at"],
                "accepted_reviewed_at": accepted["reviewed_at"],
                "accepted_at": accepted["accepted_at"],
            }
        )

        return (
            FeedbackGenerationResult(
                output=raw_output,
                metadata=metadata,
            ),
            validated,
        )


def is_reviewed_accepted_feedback_generator(value: object) -> bool:
    return (
        isinstance(value, ReviewedAcceptedFeedbackGenerator)
        and value.generator_id == REVIEWED_RUNTIME_GENERATOR_ID
        and value.generation_status
        == REVIEWED_RUNTIME_GENERATION_STATUS
        and value.formal_contract_version
        == REVIEWED_RUNTIME_CONTRACT_VERSION
    )


def create_reviewed_accepted_feedback_generator(
    root: str | Path,
) -> ReviewedAcceptedFeedbackGenerator:
    """Create the formal runtime adapter without env or credential access."""

    resolved = Path(root)
    if not resolved.is_dir():
        raise ReviewedAcceptedFeedbackRuntimeError(
            f"reviewed feedback artifact root not found: {resolved}"
        )
    return ReviewedAcceptedFeedbackGenerator(
        store=FeedbackReviewArtifactStore(resolved)
    )
