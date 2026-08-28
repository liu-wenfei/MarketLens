from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from marketlens.experiment.protocol import load_protocol, validate_protocol


class ExperimentOrchestrationError(ValueError):
    pass


class ParticipantStage(str, Enum):
    BACKGROUND_REQUIRED = "BACKGROUND_REQUIRED"
    J0_REQUIRED = "J0_REQUIRED"
    MISINFORMATION_DELIVERY_REQUIRED = "MISINFORMATION_DELIVERY_REQUIRED"
    J1_REQUIRED = "J1_REQUIRED"
    J2_REQUIRED = "J2_REQUIRED"
    CORRECTION_DELIVERY_REQUIRED = "CORRECTION_DELIVERY_REQUIRED"
    J3_REQUIRED = "J3_REQUIRED"
    J4_REQUIRED = "J4_REQUIRED"
    ROUND_ACTIVE = "ROUND_ACTIVE"
    FEEDBACK_REQUIRED = "FEEDBACK_REQUIRED"
    DEBRIEF_REQUIRED = "DEBRIEF_REQUIRED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True, slots=True)
class JudgementSpec:
    judgement_event: str
    experiment_step: int
    agent_world_date: str
    required_stage: ParticipantStage
    next_stage: ParticipantStage


_JUDGEMENT_STAGE = {
    "J0": ParticipantStage.J0_REQUIRED,
    "J1": ParticipantStage.J1_REQUIRED,
    "J2": ParticipantStage.J2_REQUIRED,
    "J3": ParticipantStage.J3_REQUIRED,
    "J4": ParticipantStage.J4_REQUIRED,
}

_JUDGEMENT_NEXT_STAGE = {
    "J0": ParticipantStage.MISINFORMATION_DELIVERY_REQUIRED,
    "J1": ParticipantStage.ROUND_ACTIVE,
    "J2": ParticipantStage.CORRECTION_DELIVERY_REQUIRED,
    "J3": ParticipantStage.ROUND_ACTIVE,
    "J4": ParticipantStage.ROUND_ACTIVE,
}


_FEEDBACK_REQUIRED_AFTER_ROUND_STEPS = frozenset({3, 10, 14})


class ExperimentOrchestrationContract:
    """Server-owned execution contract for the frozen participant timeline.

    This layer does not change Phase 10 timing. It translates the already-frozen
    checkpoint/judgement schedule into runtime stages so a client never chooses
    J0..J4, experiment_step, agent_world_date, or pre/post stimulus moments.
    """

    def __init__(self, protocol: Mapping[str, Any] | None = None):
        self.protocol = validate_protocol(protocol) if protocol is not None else load_protocol()
        checkpoints = [
            row for row in self.protocol["timeline"]
            if row.get("experiment_step") is not None
        ]
        self._checkpoint_by_step = {
            int(row["experiment_step"]): row for row in checkpoints
        }
        if tuple(sorted(self._checkpoint_by_step)) != tuple(range(len(checkpoints))):
            raise ExperimentOrchestrationError(
                "participant checkpoint steps must be contiguous from zero"
            )

        event_rows: dict[str, dict[str, Any]] = {}
        for row in checkpoints:
            for event in row.get("formal_judgement_events", []):
                if event in event_rows:
                    raise ExperimentOrchestrationError(
                        f"duplicate formal judgement event in protocol: {event}"
                    )
                event_rows[event] = row
        if set(event_rows) != set(_JUDGEMENT_STAGE):
            raise ExperimentOrchestrationError(
                "formal judgement event set must be exactly J0..J4"
            )
        if event_rows["J0"]["experiment_step"] != event_rows["J1"]["experiment_step"]:
            raise ExperimentOrchestrationError("J0/J1 must share one checkpoint")
        if event_rows["J2"]["experiment_step"] != event_rows["J3"]["experiment_step"]:
            raise ExperimentOrchestrationError("J2/J3 must share one checkpoint")
        self._event_rows = event_rows

    @property
    def initial_step(self) -> int:
        return 0

    @property
    def initial_date(self) -> str:
        return self.checkpoint_date(self.initial_step)

    @property
    def initial_stage(self) -> ParticipantStage:
        return ParticipantStage.BACKGROUND_REQUIRED

    def checkpoint_date(self, experiment_step: int) -> str:
        try:
            return str(self._checkpoint_by_step[int(experiment_step)]["agent_world_date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ExperimentOrchestrationError(
                f"unknown participant experiment_step: {experiment_step!r}"
            ) from exc

    def validate_checkpoint(self, experiment_step: int, agent_world_date: str) -> None:
        expected = self.checkpoint_date(experiment_step)
        if agent_world_date != expected:
            raise ExperimentOrchestrationError(
                "session date disagrees with frozen protocol checkpoint"
            )

    def after_background_stage(self, experiment_step: int) -> ParticipantStage:
        row = self._checkpoint_by_step[int(experiment_step)]
        events = tuple(row.get("formal_judgement_events", []))
        if not events:
            return ParticipantStage.ROUND_ACTIVE
        first = str(events[0])
        try:
            return _JUDGEMENT_STAGE[first]
        except KeyError as exc:
            raise ExperimentOrchestrationError(
                f"unsupported formal judgement event: {first}"
            ) from exc

    def expected_judgement_for_stage(self, stage: str | ParticipantStage) -> str:
        try:
            resolved = ParticipantStage(stage)
        except ValueError as exc:
            raise ExperimentOrchestrationError(f"unknown participant stage: {stage!r}") from exc
        for event, required in _JUDGEMENT_STAGE.items():
            if resolved is required:
                return event
        raise ExperimentOrchestrationError(
            f"participant stage {resolved.value} does not accept a judgement"
        )

    def judgement_spec(self, judgement_event: str) -> JudgementSpec:
        try:
            row = self._event_rows[judgement_event]
            required = _JUDGEMENT_STAGE[judgement_event]
            next_stage = _JUDGEMENT_NEXT_STAGE[judgement_event]
        except KeyError as exc:
            raise ExperimentOrchestrationError(
                f"unknown formal judgement event: {judgement_event!r}"
            ) from exc
        return JudgementSpec(
            judgement_event=judgement_event,
            experiment_step=int(row["experiment_step"]),
            agent_world_date=str(row["agent_world_date"]),
            required_stage=required,
            next_stage=next_stage,
        )

    def after_stimulus_stage(self, stage: str | ParticipantStage) -> ParticipantStage:
        resolved = ParticipantStage(stage)
        if resolved is ParticipantStage.MISINFORMATION_DELIVERY_REQUIRED:
            return ParticipantStage.J1_REQUIRED
        if resolved is ParticipantStage.CORRECTION_DELIVERY_REQUIRED:
            return ParticipantStage.J3_REQUIRED
        raise ExperimentOrchestrationError(
            f"participant stage {resolved.value} does not accept controlled-stimulus delivery"
        )

    def feedback_required_after_round(self, experiment_step: int) -> bool:
        """Return whether the completed participant period must enter feedback."""
        step = int(experiment_step)
        self.checkpoint_date(step)
        return step in _FEEDBACK_REQUIRED_AFTER_ROUND_STEPS

    def next_checkpoint(self, experiment_step: int) -> tuple[int, str] | None:
        step = int(experiment_step)
        self.checkpoint_date(step)
        next_step = step + 1
        if next_step not in self._checkpoint_by_step:
            return None
        return next_step, self.checkpoint_date(next_step)
