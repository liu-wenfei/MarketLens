"""Provider-neutral feedback-generation boundary."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping, Protocol, runtime_checkable

from .prompt import FrozenFeedbackPrompt


class FeedbackGenerationContractError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FeedbackGenerationResult:
    """One accepted provider output plus immutable provenance metadata."""

    output: str | Mapping[str, object]
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        output = self.output
        if isinstance(output, str):
            if not output.strip():
                raise FeedbackGenerationContractError(
                    "feedback generation output must not be empty"
                )
        elif isinstance(output, Mapping):
            output = MappingProxyType(dict(output))
        else:
            raise FeedbackGenerationContractError(
                "feedback generation output must be text or a mapping"
            )

        if not isinstance(self.metadata, Mapping):
            raise FeedbackGenerationContractError(
                "feedback generation metadata must be a mapping"
            )

        object.__setattr__(self, "output", output)
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )


@runtime_checkable
class BoundedValidatedFeedbackGenerator(Protocol):
    """Structural seam for one shared provider-attempt budget."""

    def generate_validated(
        self,
        prompt: FrozenFeedbackPrompt,
        *,
        validator: Callable[[object], object],
        validation_error_types: tuple[
            type[BaseException], ...
        ],
    ) -> tuple[FeedbackGenerationResult, object]:
        ...
