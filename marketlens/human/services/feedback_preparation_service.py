"""Server-owned preparation of already-frozen participant feedback.

This service seals authoritative statistics and participant-safe context,
calls an injected generator exactly at a feedback checkpoint, validates
the result, and hands the prepared artifact to the existing immutable
delivery service.

The generator is injected. This module contains no provider/API client.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from threading import Lock

from marketlens.human.feedback import (
    ContextLimits,
    FeedbackContextBuilder,
    FeedbackKind,
    FeedbackStatisticsSourceAdapter,
    FrozenFeedbackPrompt,
    build_feedback_prompt,
    validate_feedback_output,
)
from marketlens.human.orchestration import ParticipantStage
from marketlens.human.services.feedback_delivery_service import (
    ParticipantFeedbackDeliveryService,
    PreparedFeedbackArtifact,
)


FeedbackGenerator = Callable[
    [FrozenFeedbackPrompt],
    str | Mapping[str, object],
]


class ParticipantFeedbackPreparationError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ParticipantFeedbackPreparationError(
            "generated feedback is not canonical JSON"
        ) from exc


def _feedback_kind_for_step(
    experiment_step: int,
) -> FeedbackKind:
    frozen = {
        3: FeedbackKind.F1,
        10: FeedbackKind.F2,
        14: FeedbackKind.FINAL,
    }

    try:
        return frozen[int(experiment_step)]
    except KeyError as exc:
        raise ParticipantFeedbackPreparationError(
            "unsupported feedback checkpoint"
        ) from exc


class ParticipantFeedbackPreparationService:
    """Prepare at most one feedback artifact per session/checkpoint.

    The process-local lock prevents duplicate generation within one
    participant-server process. Immutable DB persistence remains the
    authoritative duplicate/conflict guard.

    No real-provider concurrency policy is implied by this development
    wiring.
    """

    def __init__(
        self,
        *,
        assignments: object,
        projections: Mapping[str, object],
        judgements: object,
        portfolios: object,
        rounds: object,
        events: object,
        price_providers: Mapping[str, object],
        calendar: object,
        contract: object,
        stimulus_engine: object,
        target_stock_id: str,
        limits: ContextLimits,
        delivery: ParticipantFeedbackDeliveryService,
        generator: FeedbackGenerator,
        generator_id: str,
        generation_status: str,
        generation_metadata: (
            Mapping[str, object] | None
        ) = None,
    ) -> None:
        self.assignments = assignments
        self.projections = dict(projections)
        self.judgements = judgements
        self.portfolios = portfolios
        self.rounds = rounds
        self.events = events
        self.price_providers = dict(
            price_providers
        )
        self.calendar = calendar
        self.contract = contract
        self.stimulus_engine = stimulus_engine
        self.target_stock_id = target_stock_id
        self.limits = limits
        self.delivery = delivery
        self.generator = generator
        self.generator_id = generator_id
        self.generation_status = generation_status
        self.generation_metadata = dict(
            generation_metadata or {}
        )
        self._lock = Lock()

        if set(self.projections) != set(
            self.price_providers
        ):
            raise ParticipantFeedbackPreparationError(
                "feedback projection and canonical "
                "price-provider episode keys must match"
            )

    def prepare(
        self,
        session_id: str,
        experiment_step: int,
    ) -> bool:
        """Prepare once; return False when already persisted."""

        step = int(experiment_step)

        with self._lock:
            existing = (
                self.delivery.store.get_for_step(
                    session_id,
                    step,
                )
            )
            if existing is not None:
                return False

            state = self.delivery.orchestration.get(
                session_id
            )

            if (
                state.completed
                or state.agent_world_date is None
                or int(state.experiment_step) != step
                or state.current_stage
                != ParticipantStage.FEEDBACK_REQUIRED.value
            ):
                raise ParticipantFeedbackPreparationError(
                    "feedback preparation requires the "
                    "server-owned FEEDBACK_REQUIRED checkpoint"
                )

            try:
                required = (
                    self.contract
                    .feedback_required_after_round(step)
                )
            except Exception as exc:
                raise ParticipantFeedbackPreparationError(
                    "cannot validate feedback checkpoint"
                ) from exc

            if not required:
                raise ParticipantFeedbackPreparationError(
                    "current checkpoint does not require "
                    "feedback"
                )

            kind = _feedback_kind_for_step(step)

            assignment = self.assignments.get(
                session_id
            )
            if assignment is None:
                raise ParticipantFeedbackPreparationError(
                    "participant session has no canonical "
                    "episode assignment"
                )

            episode_id = assignment.episode_id
            price_provider = (
                self.price_providers.get(
                    episode_id
                )
            )
            if price_provider is None:
                raise ParticipantFeedbackPreparationError(
                    "no canonical feedback price provider "
                    "is bound for the assigned episode"
                )

            statistics_source = (
                FeedbackStatisticsSourceAdapter(
                    assignments=self.assignments,
                    projections=self.projections,
                    judgements=self.judgements,
                    portfolios=self.portfolios,
                    rounds=self.rounds,
                    events=self.events,
                    price_provider=price_provider,
                    calendar=self.calendar,
                    contract=self.contract,
                    target_stock_id=(
                        self.target_stock_id
                    ),
                )
            )

            context_builder = FeedbackContextBuilder(
                statistics_source=statistics_source,
                judgements=self.judgements,
                events=self.events,
                assignments=self.assignments,
                projections=self.projections,
                contract=self.contract,
                stimulus_engine=(
                    self.stimulus_engine
                ),
                target_stock_id=(
                    self.target_stock_id
                ),
                limits=self.limits,
            )

            context_pack = context_builder.build(
                session_id,
                kind,
            )

            statistics = dict(
                context_pack.statistics
            )

            prompt = build_feedback_prompt(
                context_pack
            )

            generated = self.generator(prompt)

            validated = validate_feedback_output(
                generated,
                context_pack=context_pack,
            )

            validated_payload = dict(
                validated.payload
            )

            if set(validated_payload) != {
                "feedback_kind",
                "reflection",
            }:
                raise ParticipantFeedbackPreparationError(
                    "validated feedback must use the "
                    "reflection-only output contract"
                )

            if isinstance(generated, str):
                raw_output = generated
            else:
                raw_output = _canonical_json(
                    generated
                )

            metadata = dict(
                self.generation_metadata
            )
            metadata.update(
                {
                    "output_contract_version": (
                        validated
                        .output_contract_version
                    ),
                    "output_sha256": (
                        validated.output_sha256
                    ),
                    "word_count": (
                        validated.word_count
                    ),
                    "context_sha256": (
                        prompt.context_sha256
                    ),
                }
            )

            artifact = PreparedFeedbackArtifact(
                participant_id=(
                    state.participant_id
                ),
                statistics=(
                    statistics
                ),
                context_pack=(
                    context_pack.to_dict()
                ),
                prompt_version=(
                    prompt.prompt_contract_version
                ),
                prompt_text=(
                    prompt.system_prompt
                    + "\n\n"
                    + prompt.user_prompt
                ),
                generation_status=(
                    self.generation_status
                ),
                generator_id=(
                    self.generator_id
                ),
                generation_metadata=metadata,
                raw_output=raw_output,
                validated_output=(
                    validated_payload
                ),
                generated_at=_utc_now(),
            )

            self.delivery.persist_once(
                session_id,
                artifact,
            )

            return True
