"""Protocol-driven participant-only visibility engine for Phase 11."""
from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from marketlens.experiment.protocol import load_protocol, validate_protocol

from .schema import StimulusItem, StimulusMaterial, StimulusValidationError


class StimulusVisibilityError(ValueError):
    """Raised when a caller requests an ambiguous or invalid exposure moment."""


class VisibilityMoment(str, Enum):
    CHECKPOINT = "checkpoint"
    PRE_MISINFORMATION_RELEASE = "pre_misinformation_release"
    POST_MISINFORMATION_RELEASE = "post_misinformation_release"
    PRE_CORRECTION_RELEASE = "pre_correction_release"
    POST_CORRECTION_RELEASE = "post_correction_release"


class StimulusEngine:
    """Resolve controlled information available at a participant checkpoint.

    The engine never writes to TwinMarket state. Dates and checkpoint positions
    come only from the frozen Phase 10 protocol timeline.
    """

    def __init__(
        self,
        material: StimulusMaterial,
        *,
        protocol: Mapping[str, Any] | None = None,
    ) -> None:
        self.material = material
        self.protocol = validate_protocol(protocol) if protocol is not None else load_protocol()
        if material.protocol_version != self.protocol["protocol_version"]:
            raise StimulusValidationError("stimulus material and protocol version mismatch")

        checkpoint_rows = [row for row in self.protocol["timeline"] if row["experiment_step"] is not None]
        self._checkpoint_by_step = {row["experiment_step"]: row for row in checkpoint_rows}
        releases = {
            row["stimulus_release"]: row
            for row in checkpoint_rows
            if row.get("stimulus_release") != "none"
        }
        if set(releases) != {"misinformation", "authoritative_correction"}:
            raise StimulusValidationError("Phase 10 timeline must contain exactly one misinformation and correction release")
        self._misinformation_step = releases["misinformation"]["experiment_step"]
        self._correction_step = releases["authoritative_correction"]["experiment_step"]
        if not self._misinformation_step < self._correction_step:
            raise StimulusValidationError("misinformation release must precede correction release")

    @property
    def misinformation_step(self) -> int:
        return self._misinformation_step

    @property
    def correction_step(self) -> int:
        return self._correction_step

    def checkpoint_date(self, experiment_step: int) -> str:
        row = self._checkpoint_row(experiment_step)
        return row["agent_world_date"]

    def release_dates(self) -> dict[str, str]:
        return {
            "misinformation": self.checkpoint_date(self._misinformation_step),
            "authoritative_correction": self.checkpoint_date(self._correction_step),
        }

    def visible_stimuli(
        self,
        experiment_step: int,
        *,
        moment: VisibilityMoment | str = VisibilityMoment.CHECKPOINT,
    ) -> tuple[StimulusItem, ...]:
        self._checkpoint_row(experiment_step)
        try:
            resolved_moment = VisibilityMoment(moment)
        except ValueError as exc:
            raise StimulusVisibilityError(f"invalid visibility moment: {moment!r}") from exc

        if experiment_step == self._misinformation_step:
            if resolved_moment is VisibilityMoment.PRE_MISINFORMATION_RELEASE:
                return ()
            if resolved_moment is VisibilityMoment.POST_MISINFORMATION_RELEASE:
                return (self.material.misinformation,)
            raise StimulusVisibilityError(
                "misinformation checkpoint is same-state J0/J1; caller must specify pre_misinformation_release or post_misinformation_release"
            )

        if experiment_step == self._correction_step:
            if resolved_moment is VisibilityMoment.PRE_CORRECTION_RELEASE:
                return (self.material.misinformation,)
            if resolved_moment is VisibilityMoment.POST_CORRECTION_RELEASE:
                return (self.material.misinformation, self.material.correction)
            raise StimulusVisibilityError(
                "correction checkpoint is same-state J2/J3; caller must specify pre_correction_release or post_correction_release"
            )

        if resolved_moment is not VisibilityMoment.CHECKPOINT:
            raise StimulusVisibilityError("release-specific visibility moments are only valid at their manipulation checkpoint")

        if experiment_step < self._misinformation_step:
            return ()
        if experiment_step < self._correction_step:
            return (self.material.misinformation,)
        return (self.material.misinformation, self.material.correction)

    def participant_payload(
        self,
        experiment_step: int,
        *,
        moment: VisibilityMoment | str = VisibilityMoment.CHECKPOINT,
    ) -> tuple[dict[str, str | None], ...]:
        """Return an explicit allow-list projection for participant display.

        Hashes, status, protocol metadata and internal manifest fields are not
        included in the participant payload.
        """
        return tuple(
            {
                "stimulus_id": item.stimulus_id,
                "kind": item.kind.value,
                "headline": item.headline,
                "body": item.body,
                "corrects_stimulus_id": item.corrects_stimulus_id,
            }
            for item in self.visible_stimuli(experiment_step, moment=moment)
        )

    def _checkpoint_row(self, experiment_step: int) -> dict[str, Any]:
        if not isinstance(experiment_step, int) or experiment_step < 0:
            raise StimulusVisibilityError("experiment_step must be a non-negative participant checkpoint integer")
        try:
            return self._checkpoint_by_step[experiment_step]
        except KeyError as exc:
            raise StimulusVisibilityError(f"unknown participant experiment_step: {experiment_step}") from exc
