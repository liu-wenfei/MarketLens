from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from marketlens.human.orchestration import (
    ExperimentOrchestrationContract,
    ExperimentOrchestrationError,
    ParticipantStage,
)
from marketlens.human.services.orchestration_service import (
    ExperimentOrchestrationService,
    ParticipantExperimentState,
)
from marketlens.human.stores.feedback_store import (
    FeedbackStore,
    StoreFeedbackConflictError,
    StoreFeedbackNotFoundError,
)


MID_FEEDBACK_KIND = "multi_period_decision_feedback"
FINAL_FEEDBACK_KIND = "final_session_summary"


class ParticipantFeedbackError(ValueError):
    pass


class ParticipantFeedbackStateError(ParticipantFeedbackError):
    pass


class ParticipantFeedbackNotPreparedError(ParticipantFeedbackError):
    pass


class ParticipantFeedbackConflictError(ParticipantFeedbackError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedFeedbackArtifact:
    """Already-generated, already-validated internal feedback artifact.

    Persistence + Delivery v1 deliberately performs no LLM generation.
    A later bounded generator may call persist_once() only after all
    deterministic inputs and the constrained output have been sealed.
    """

    participant_id: str
    statistics: Mapping[str, Any]
    context_pack: Mapping[str, Any]
    prompt_version: str
    prompt_text: str
    generation_status: str
    generator_id: str
    generation_metadata: Mapping[str, Any]
    raw_output: str
    validated_output: Mapping[str, Any]
    generated_at: str


@dataclass(frozen=True, slots=True)
class ParticipantFeedbackView:
    feedback_kind: str
    statistics: dict[str, Any]
    reflection: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _nonempty(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ParticipantFeedbackConflictError(
            f"{name} must be a non-empty string"
        )
    return value.strip()


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
        raise ParticipantFeedbackConflictError(
            "feedback artifact contains non-canonical JSON data"
        ) from exc


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ParticipantFeedbackConflictError(
            f"{name} must be a mapping"
        )
    return value


def _window_from_statistics(
    statistics: Mapping[str, Any],
) -> tuple[int, int]:
    window = _mapping(
        "statistics.window",
        statistics.get("window"),
    )

    start = window.get("start_period")
    end = window.get("end_period")

    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or start < 1
        or end < start
    ):
        raise ParticipantFeedbackConflictError(
            "statistics window is invalid"
        )

    return start, end


class ParticipantFeedbackDeliveryService:
    """Persist and expose one server-owned feedback artifact per checkpoint.

    This service does not generate language-model output. It controls only:
      prepared artifact -> immutable persistence -> one-time exposure ->
      retry-safe server-owned continuation.
    """

    def __init__(
        self,
        *,
        store: FeedbackStore,
        orchestration: ExperimentOrchestrationService,
        contract: ExperimentOrchestrationContract | None = None,
    ):
        self.store = store
        self.orchestration = orchestration
        self.contract = contract or orchestration.contract

    def _feedback_state(
        self,
        session_id: str,
    ) -> ParticipantExperimentState:
        state = self.orchestration.get(session_id)

        if (
            state.completed
            or state.agent_world_date is None
            or state.current_stage
            != ParticipantStage.FEEDBACK_REQUIRED.value
        ):
            raise ParticipantFeedbackStateError(
                "session is not waiting at a feedback checkpoint"
            )

        try:
            self.contract.validate_checkpoint(
                state.experiment_step,
                state.agent_world_date,
            )
            required = self.contract.feedback_required_after_round(
                state.experiment_step
            )
        except ExperimentOrchestrationError as exc:
            raise ParticipantFeedbackStateError(str(exc)) from exc

        if not required:
            raise ParticipantFeedbackStateError(
                "current checkpoint is not a feedback checkpoint"
            )

        return state

    def _feedback_kind(self, experiment_step: int) -> str:
        try:
            next_checkpoint = self.contract.next_checkpoint(
                experiment_step
            )
        except ExperimentOrchestrationError as exc:
            raise ParticipantFeedbackStateError(str(exc)) from exc

        if next_checkpoint is None:
            return FINAL_FEEDBACK_KIND
        return MID_FEEDBACK_KIND

    @staticmethod
    def _expected_window_start(experiment_step: int) -> int:
        frozen = {
            3: 1,   # P4 feedback: P1-P4
            10: 5,  # P11 feedback: P5-P11
            14: 1,  # Final: P1-P15
        }
        try:
            return frozen[int(experiment_step)]
        except KeyError as exc:
            raise ParticipantFeedbackStateError(
                "unsupported feedback checkpoint"
            ) from exc

    def _require_row_matches_state(
        self,
        row: Mapping[str, Any],
        state: ParticipantExperimentState,
    ) -> None:
        if row["session_id"] != state.session_id:
            raise ParticipantFeedbackConflictError(
                "persisted feedback session does not match server state"
            )
        if row["participant_id"] != state.participant_id:
            raise ParticipantFeedbackConflictError(
                "persisted feedback participant does not match server state"
            )
        if int(row["experiment_step"]) != int(state.experiment_step):
            raise ParticipantFeedbackConflictError(
                "persisted feedback checkpoint does not match server state"
            )
        if row["agent_world_date"] != state.agent_world_date:
            raise ParticipantFeedbackConflictError(
                "persisted feedback date does not match server state"
            )

        expected_kind = self._feedback_kind(state.experiment_step)
        if row["feedback_kind"] != expected_kind:
            raise ParticipantFeedbackConflictError(
                "persisted feedback kind does not match server-owned timing"
            )

    def persist_once(
        self,
        session_id: str,
        artifact: PreparedFeedbackArtifact,
    ) -> ParticipantFeedbackView:
        """Internal persistence hook for an already-prepared artifact.

        No public route calls this method.
        No LLM call occurs here.
        """

        state = self._feedback_state(session_id)

        participant_id = _nonempty(
            "participant_id",
            artifact.participant_id,
        )
        if participant_id != state.participant_id:
            raise ParticipantFeedbackConflictError(
                "prepared feedback participant does not match session"
            )

        statistics = _mapping(
            "statistics",
            artifact.statistics,
        )
        context_pack = _mapping(
            "context_pack",
            artifact.context_pack,
        )
        validated_output = _mapping(
            "validated_output",
            artifact.validated_output,
        )

        statistics_version = _nonempty(
            "statistics_version",
            statistics.get("statistics_version"),
        )
        context_pack_version = _nonempty(
            "context_pack_version",
            context_pack.get("context_pack_version"),
        )
        prompt_version = _nonempty(
            "prompt_version",
            artifact.prompt_version,
        )
        prompt_text = _nonempty(
            "prompt_text",
            artifact.prompt_text,
        )
        generation_status = _nonempty(
            "generation_status",
            artifact.generation_status,
        )
        generator_id = _nonempty(
            "generator_id",
            artifact.generator_id,
        )
        generated_at = _nonempty(
            "generated_at",
            artifact.generated_at,
        )

        start_period, end_period = _window_from_statistics(
            statistics
        )

        expected_end = int(state.experiment_step) + 1
        expected_start = self._expected_window_start(
            state.experiment_step
        )
        if (
            start_period != expected_start
            or end_period != expected_end
        ):
            raise ParticipantFeedbackConflictError(
                "statistics window does not match the frozen "
                "feedback checkpoint"
            )

        context_statistics = context_pack.get("statistics")
        if context_statistics is not None:
            if _canonical_json(context_statistics) != _canonical_json(
                statistics
            ):
                raise ParticipantFeedbackConflictError(
                    "context pack statistics disagree with the "
                    "authoritative feedback statistics"
                )

        expected_kind = self._feedback_kind(
            state.experiment_step
        )

        if set(validated_output) != {
            "feedback_kind",
            "reflection",
        }:
            raise ParticipantFeedbackConflictError(
                "validated feedback output must contain exactly "
                "feedback_kind and reflection"
            )

        if validated_output["feedback_kind"] != expected_kind:
            raise ParticipantFeedbackConflictError(
                "validated feedback kind disagrees with "
                "server-owned checkpoint timing"
            )

        reflection = _nonempty(
            "reflection",
            validated_output["reflection"],
        )

        raw_output = artifact.raw_output
        if not isinstance(raw_output, str):
            raise ParticipantFeedbackConflictError(
                "raw_output must be a string"
            )

        statistics_json = _canonical_json(statistics)
        context_pack_json = _canonical_json(context_pack)
        generation_metadata_json = _canonical_json(
            artifact.generation_metadata
        )
        validated_output_json = _canonical_json(
            validated_output
        )

        feedback_id = str(
            uuid5(
                NAMESPACE_URL,
                "marketlens:participant-feedback:"
                f"{state.session_id}:{state.experiment_step}",
            )
        )

        try:
            row = self.store.create_once(
                feedback_id=feedback_id,
                session_id=state.session_id,
                participant_id=state.participant_id,
                experiment_step=state.experiment_step,
                agent_world_date=state.agent_world_date,
                feedback_kind=expected_kind,
                window_start_period=start_period,
                window_end_period=end_period,
                statistics_version=statistics_version,
                statistics_sha256=_sha256_text(
                    statistics_json
                ),
                statistics_json=statistics_json,
                context_pack_version=context_pack_version,
                context_pack_sha256=_sha256_text(
                    context_pack_json
                ),
                context_pack_json=context_pack_json,
                prompt_version=prompt_version,
                prompt_sha256=_sha256_text(prompt_text),
                generation_status=generation_status,
                generator_id=generator_id,
                generation_metadata_json=(
                    generation_metadata_json
                ),
                raw_output=raw_output,
                validated_output_json=(
                    validated_output_json
                ),
                output_sha256=_sha256_text(
                    validated_output_json
                ),
                generated_at=generated_at,
                shown_at=None,
                continue_request_id=None,
                continued_at=None,
            )
        except StoreFeedbackConflictError as exc:
            raise ParticipantFeedbackConflictError(
                str(exc)
            ) from exc

        return self._row_to_view(row)

    def get_current(
        self,
        session_id: str,
    ) -> ParticipantFeedbackView:
        state = self._feedback_state(session_id)
        row = self.store.get_for_step(
            state.session_id,
            state.experiment_step,
        )

        if row is None:
            raise ParticipantFeedbackNotPreparedError(
                "feedback for the current checkpoint has not "
                "been prepared"
            )

        self._require_row_matches_state(row, state)

        try:
            row = self.store.mark_shown_once(
                session_id=state.session_id,
                experiment_step=state.experiment_step,
                shown_at=_utc_now(),
            )
        except (
            StoreFeedbackConflictError,
            StoreFeedbackNotFoundError,
        ) as exc:
            raise ParticipantFeedbackConflictError(
                str(exc)
            ) from exc

        return self._row_to_view(row)

    def continue_current(
        self,
        session_id: str,
        request_id: str,
    ) -> bool:
        request_id = _nonempty(
            "request_id",
            request_id,
        )

        # Retry path is checked before FEEDBACK_REQUIRED because the
        # first successful request may already have advanced state.
        existing_request = self.store.get_by_continue_request(
            session_id,
            request_id,
        )
        if existing_request is not None:
            return self._resume_reserved_continue(
                existing_request,
                request_id,
            )

        state = self._feedback_state(session_id)
        row = self.store.get_for_step(
            session_id,
            state.experiment_step,
        )
        if row is None:
            raise ParticipantFeedbackNotPreparedError(
                "feedback for the current checkpoint has not "
                "been prepared"
            )

        self._require_row_matches_state(row, state)

        if row["shown_at"] is None:
            raise ParticipantFeedbackStateError(
                "feedback must be exposed before continuation"
            )

        try:
            reserved = self.store.reserve_continue(
                session_id=session_id,
                experiment_step=state.experiment_step,
                request_id=request_id,
            )
        except (
            StoreFeedbackConflictError,
            StoreFeedbackNotFoundError,
        ) as exc:
            raise ParticipantFeedbackConflictError(
                str(exc)
            ) from exc

        return self._resume_reserved_continue(
            reserved,
            request_id,
        )

    def _resume_reserved_continue(
        self,
        row: Mapping[str, Any],
        request_id: str,
    ) -> bool:
        if row["continue_request_id"] != request_id:
            raise ParticipantFeedbackConflictError(
                "feedback continuation reservation mismatch"
            )

        session_id = str(row["session_id"])
        feedback_step = int(row["experiment_step"])

        current = self.orchestration.get(session_id)

        if current.participant_id != row["participant_id"]:
            raise ParticipantFeedbackConflictError(
                "feedback continuation participant mismatch"
            )

        if (
            current.current_stage
            == ParticipantStage.FEEDBACK_REQUIRED.value
            and int(current.experiment_step) == feedback_step
        ):
            self._require_row_matches_state(row, current)
            self.orchestration.continue_after_feedback(
                session_id
            )
            current = self.orchestration.get(session_id)

        if not self._is_expected_post_feedback_state(
            row,
            current,
        ):
            raise ParticipantFeedbackConflictError(
                "server state is not the expected state after "
                "this feedback continuation"
            )

        if row["continued_at"] is None:
            try:
                self.store.mark_continued_once(
                    session_id=session_id,
                    experiment_step=feedback_step,
                    request_id=request_id,
                    continued_at=_utc_now(),
                )
            except (
                StoreFeedbackConflictError,
                StoreFeedbackNotFoundError,
            ) as exc:
                raise ParticipantFeedbackConflictError(
                    str(exc)
                ) from exc

        return True

    def _is_expected_post_feedback_state(
        self,
        row: Mapping[str, Any],
        current: ParticipantExperimentState,
    ) -> bool:
        step = int(row["experiment_step"])
        next_checkpoint = self.contract.next_checkpoint(step)

        if next_checkpoint is None:
            return (
                not current.completed
                and int(current.experiment_step) == step
                and current.agent_world_date
                == row["agent_world_date"]
                and current.current_stage
                == ParticipantStage.DEBRIEF_REQUIRED.value
            )

        next_step, next_date = next_checkpoint
        return (
            not current.completed
            and int(current.experiment_step) == int(next_step)
            and current.agent_world_date == next_date
            and current.current_stage
            == ParticipantStage.BACKGROUND_REQUIRED.value
        )

    @staticmethod
    def _row_to_view(
        row: Mapping[str, Any],
    ) -> ParticipantFeedbackView:
        try:
            statistics = json.loads(
                row["statistics_json"]
            )
            output = json.loads(
                row["validated_output_json"]
            )
        except (TypeError, json.JSONDecodeError) as exc:
            raise ParticipantFeedbackConflictError(
                "persisted feedback JSON is invalid"
            ) from exc

        if not isinstance(statistics, dict):
            raise ParticipantFeedbackConflictError(
                "persisted feedback statistics are invalid"
            )
        if (
            not isinstance(output, dict)
            or set(output)
            != {"feedback_kind", "reflection"}
            or output.get("feedback_kind")
            != row["feedback_kind"]
            or not isinstance(output.get("reflection"), str)
            or not output["reflection"].strip()
        ):
            raise ParticipantFeedbackConflictError(
                "persisted validated feedback output is invalid"
            )

        return ParticipantFeedbackView(
            feedback_kind=str(row["feedback_kind"]),
            statistics=statistics,
            reflection=output["reflection"],
        )
