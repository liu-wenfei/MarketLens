from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.measurement.models import ParticipantEvent, ParticipantEventType
from marketlens.human.orchestration import ParticipantStage
from marketlens.human.schemas import ParticipantBackgroundRead
from marketlens.human.services.background_service import ParticipantBackgroundService
from marketlens.human.services.orchestration_service import ExperimentOrchestrationService
from marketlens.human.services.trusted_context_service import (
    TrustedParticipantContext,
    TrustedParticipantContextResolver,
)
from marketlens.source_cues.adapter import (
    SourceCueError,
    assert_formal_source_cue_freeze,
    decorate_controlled_stimulus_payload,
)
from marketlens.stimulus.engine import StimulusEngine, StimulusVisibilityError, VisibilityMoment
from marketlens.stimulus.manifest import sha256_json
from marketlens.stimulus.schema import FormalUseStatus, StimulusItem


class ParticipantExposureUnavailableError(ValueError):
    pass


class ParticipantExposureInvariantError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParticipantControlledStimulusDelivery:
    session_id: str
    current_date: str
    stimulus_id: str
    kind: str
    headline: str
    body: str
    corrects_stimulus_id: str | None
    source_label: str
    source_descriptor: str

    def participant_payload(self) -> dict[str, str | None]:
        return asdict(self)


def _event_id(session_id: str, request_id: str, event_type: ParticipantEventType) -> str:
    identity = f"marketlens:participant-event:{session_id}:{request_id}:{event_type.value}"
    return str(uuid5(NAMESPACE_URL, identity))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_request_id(request_id: str) -> str:
    if not isinstance(request_id, str) or not request_id.strip():
        raise ParticipantExposureUnavailableError("request_id must be non-empty")
    return request_id.strip()


class ParticipantExposureService:
    """Prepare participant-visible exposure, record provenance, then advance stage.

    The participant supplies only ``session_id`` and an idempotency ``request_id``.
    Episode/date/step/market state and controlled-stimulus timing are derived from
    backend sources. Exposure events are written before the orchestration stage is
    advanced so a retry can repair an interrupted cross-database transition.

    An exposure event means that the backend prepared and authorised the exact
    participant-visible payload for delivery. It is not mouse/scroll/dwell or
    proof that a human read the payload.
    """

    def __init__(
        self,
        *,
        backgrounds: ParticipantBackgroundService,
        events: ParticipantEventStore,
        context: TrustedParticipantContextResolver,
        orchestration: ExperimentOrchestrationService,
        stimulus_engine: StimulusEngine | None = None,
    ):
        self.backgrounds = backgrounds
        self.events = events
        self.context = context
        self.orchestration = orchestration
        self.stimulus_engine = stimulus_engine

    @staticmethod
    def _validate_state_context(state, trusted: TrustedParticipantContext) -> None:
        if state.session_id != trusted.session_id:
            raise ParticipantExposureInvariantError(
                "orchestration session disagrees with trusted participant context"
            )
        if state.participant_id != trusted.participant_id:
            raise ParticipantExposureInvariantError(
                "orchestration participant disagrees with trusted participant context"
            )
        if state.experiment_step != trusted.experiment_step:
            raise ParticipantExposureInvariantError(
                "orchestration step disagrees with trusted participant context"
            )
        if state.agent_world_date != trusted.agent_world_date:
            raise ParticipantExposureInvariantError(
                "orchestration date disagrees with trusted participant context"
            )

    @staticmethod
    def _validate_existing_event(existing, trusted: TrustedParticipantContext) -> None:
        expected = {
            "session_id": trusted.session_id,
            "participant_id": trusted.participant_id,
            "episode_id": trusted.episode_id,
            "experiment_step": trusted.experiment_step,
            "agent_world_date": trusted.agent_world_date,
            "market_open": trusted.market_open,
            "participant_trading_enabled": trusted.participant_trading_enabled,
        }
        for field, value in expected.items():
            if existing[field] != value:
                raise ParticipantExposureInvariantError(
                    f"existing exposure event {field} disagrees with trusted participant context"
                )

    @staticmethod
    def _validate_background(background: ParticipantBackgroundRead, trusted: TrustedParticipantContext) -> str:
        if background.session_id != trusted.session_id:
            raise ParticipantExposureInvariantError(
                "background session disagrees with trusted participant context"
            )
        if background.current_date != trusted.agent_world_date:
            raise ParticipantExposureInvariantError(
                "background date disagrees with trusted participant context"
            )
        return sha256_json(background.model_dump(mode="json"))

    def deliver_background(self, session_id: str, request_id: str) -> ParticipantBackgroundRead:
        request_id = _require_request_id(request_id)
        trusted = self.context.resolve(session_id)
        state = self.orchestration.get(session_id)
        self._validate_state_context(state, trusted)

        background = self.backgrounds.get_current_background(session_id)
        payload_digest = self._validate_background(background, trusted)
        existing = self.events.get_by_request_event(
            session_id,
            request_id,
            ParticipantEventType.BACKGROUND_EXPOSED,
        )
        if existing is not None:
            self._validate_existing_event(existing, trusted)
            if existing["payload_digest"] != payload_digest:
                raise ParticipantExposureInvariantError(
                    "replayed background payload disagrees with the append-only exposure event"
                )
            if state.current_stage == ParticipantStage.BACKGROUND_REQUIRED.value:
                self.orchestration.after_background_delivery(session_id)
            return background

        if state.current_stage != ParticipantStage.BACKGROUND_REQUIRED.value:
            raise ParticipantExposureUnavailableError(
                "background delivery is not authorised by the current server-owned stage"
            )

        self.events.append_idempotent(
            ParticipantEvent(
                event_id=_event_id(
                    trusted.session_id,
                    request_id,
                    ParticipantEventType.BACKGROUND_EXPOSED,
                ),
                request_id=request_id,
                session_id=trusted.session_id,
                participant_id=trusted.participant_id,
                episode_id=trusted.episode_id,
                experiment_step=trusted.experiment_step,
                agent_world_date=trusted.agent_world_date,
                event_type=ParticipantEventType.BACKGROUND_EXPOSED,
                market_open=trusted.market_open,
                participant_trading_enabled=trusted.participant_trading_enabled,
                payload_digest=payload_digest,
                occurred_at_utc=_utc_now_iso(),
            )
        )
        self.orchestration.after_background_delivery(session_id)
        return background

    def _formal_engine(self) -> StimulusEngine:
        engine = self.stimulus_engine
        if engine is None:
            raise ParticipantExposureUnavailableError(
                "formal controlled-stimulus engine is not bound"
            )
        if engine.material.formal_use_status is not FormalUseStatus.FORMAL_FROZEN:
            raise ParticipantExposureUnavailableError(
                "participant-facing controlled stimulus requires formal_frozen material"
            )
        try:
            assert_formal_source_cue_freeze()
        except SourceCueError as exc:
            raise ParticipantExposureUnavailableError(str(exc)) from exc
        return engine

    @staticmethod
    def _release_identity(engine: StimulusEngine, stage: str) -> tuple[StimulusItem, int, VisibilityMoment]:
        if stage == ParticipantStage.MISINFORMATION_DELIVERY_REQUIRED.value:
            return (
                engine.material.misinformation,
                engine.misinformation_step,
                VisibilityMoment.POST_MISINFORMATION_RELEASE,
            )
        if stage == ParticipantStage.CORRECTION_DELIVERY_REQUIRED.value:
            return (
                engine.material.correction,
                engine.correction_step,
                VisibilityMoment.POST_CORRECTION_RELEASE,
            )
        raise ParticipantExposureUnavailableError(
            "controlled-stimulus delivery is not authorised by the current server-owned stage"
        )

    @staticmethod
    def _delivery_for_item(
        engine: StimulusEngine,
        *,
        session_id: str,
        current_date: str,
        item: StimulusItem,
        experiment_step: int,
        moment: VisibilityMoment,
    ) -> ParticipantControlledStimulusDelivery:
        try:
            visible = engine.participant_payload(experiment_step, moment=moment)
        except StimulusVisibilityError as exc:
            raise ParticipantExposureUnavailableError(str(exc)) from exc
        try:
            raw = next(payload for payload in visible if payload["stimulus_id"] == item.stimulus_id)
        except StopIteration as exc:
            raise ParticipantExposureInvariantError(
                "formal release item is absent from the StimulusEngine participant payload"
            ) from exc
        try:
            decorated = decorate_controlled_stimulus_payload(raw)
        except SourceCueError as exc:
            raise ParticipantExposureUnavailableError(str(exc)) from exc
        return ParticipantControlledStimulusDelivery(
            session_id=session_id,
            current_date=current_date,
            stimulus_id=str(decorated["stimulus_id"]),
            kind=str(decorated["kind"]),
            headline=str(decorated["headline"]),
            body=str(decorated["body"]),
            corrects_stimulus_id=(
                None
                if decorated["corrects_stimulus_id"] is None
                else str(decorated["corrects_stimulus_id"])
            ),
            source_label=str(decorated["source_label"]),
            source_descriptor=str(decorated["source_descriptor"]),
        )

    def _replay_stimulus(self, trusted: TrustedParticipantContext, state, existing):
        engine = self._formal_engine()
        stimulus_id = existing["stimulus_id"]
        if stimulus_id == engine.material.misinformation.stimulus_id:
            item = engine.material.misinformation
            step = engine.misinformation_step
            moment = VisibilityMoment.POST_MISINFORMATION_RELEASE
            delivery_stage = ParticipantStage.MISINFORMATION_DELIVERY_REQUIRED.value
            later_stages = {
                ParticipantStage.J1_REQUIRED.value,
                ParticipantStage.ROUND_ACTIVE.value,
            }
        elif stimulus_id == engine.material.correction.stimulus_id:
            item = engine.material.correction
            step = engine.correction_step
            moment = VisibilityMoment.POST_CORRECTION_RELEASE
            delivery_stage = ParticipantStage.CORRECTION_DELIVERY_REQUIRED.value
            later_stages = {
                ParticipantStage.J3_REQUIRED.value,
                ParticipantStage.ROUND_ACTIVE.value,
            }
        else:
            raise ParticipantExposureInvariantError(
                "existing controlled-stimulus event has an unknown formal stimulus_id"
            )
        if trusted.experiment_step != step:
            raise ParticipantExposureInvariantError(
                "replayed controlled stimulus disagrees with the current participant checkpoint"
            )
        delivery = self._delivery_for_item(
            engine,
            session_id=trusted.session_id,
            current_date=trusted.agent_world_date,
            item=item,
            experiment_step=step,
            moment=moment,
        )
        payload_digest = sha256_json(delivery.participant_payload())
        expected = {
            "stimulus_version": engine.material.material_version,
            "stimulus_sha256": item.content_sha256,
            "source_cue": delivery.source_label,
            "payload_digest": payload_digest,
        }
        for field, value in expected.items():
            if existing[field] != value:
                raise ParticipantExposureInvariantError(
                    f"replayed controlled-stimulus {field} disagrees with append-only provenance"
                )
        if state.current_stage == delivery_stage:
            self.orchestration.after_stimulus_delivery(trusted.session_id)
        elif state.current_stage not in later_stages:
            raise ParticipantExposureInvariantError(
                "existing controlled-stimulus event is inconsistent with current server-owned stage"
            )
        return delivery

    def deliver_controlled_stimulus(
        self,
        session_id: str,
        request_id: str,
    ) -> ParticipantControlledStimulusDelivery:
        request_id = _require_request_id(request_id)
        trusted = self.context.resolve(session_id)
        state = self.orchestration.get(session_id)
        self._validate_state_context(state, trusted)

        existing = self.events.get_by_request_event(
            session_id,
            request_id,
            ParticipantEventType.CONTROLLED_STIMULUS_EXPOSED,
        )
        if existing is not None:
            self._validate_existing_event(existing, trusted)
            return self._replay_stimulus(trusted, state, existing)

        if state.current_stage is None:
            raise ParticipantExposureUnavailableError(
                "participant experiment orchestration is not initialized"
            )
        engine = self._formal_engine()
        item, release_step, moment = self._release_identity(engine, state.current_stage)
        if trusted.experiment_step != release_step:
            raise ParticipantExposureInvariantError(
                "server-owned stimulus stage disagrees with the frozen release checkpoint"
            )
        delivery = self._delivery_for_item(
            engine,
            session_id=trusted.session_id,
            current_date=trusted.agent_world_date,
            item=item,
            experiment_step=release_step,
            moment=moment,
        )
        payload_digest = sha256_json(delivery.participant_payload())

        self.events.append_idempotent(
            ParticipantEvent(
                event_id=_event_id(
                    trusted.session_id,
                    request_id,
                    ParticipantEventType.CONTROLLED_STIMULUS_EXPOSED,
                ),
                request_id=request_id,
                session_id=trusted.session_id,
                participant_id=trusted.participant_id,
                episode_id=trusted.episode_id,
                experiment_step=trusted.experiment_step,
                agent_world_date=trusted.agent_world_date,
                event_type=ParticipantEventType.CONTROLLED_STIMULUS_EXPOSED,
                stimulus_id=item.stimulus_id,
                stimulus_version=engine.material.material_version,
                stimulus_sha256=item.content_sha256,
                source_cue=delivery.source_label,
                market_open=trusted.market_open,
                participant_trading_enabled=trusted.participant_trading_enabled,
                payload_digest=payload_digest,
                occurred_at_utc=_utc_now_iso(),
            )
        )
        self.orchestration.after_stimulus_delivery(session_id)
        return delivery
