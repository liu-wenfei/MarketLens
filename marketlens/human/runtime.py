from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.measurement.runtime_recorder import ParticipantRuntimeEventRecorder
from marketlens.human.services.episode_assignment_service import EpisodeAssignmentService
from marketlens.human.services.episode_background_service import (
    EpisodeAwareParticipantBackgroundService,
)
from marketlens.human.services.exposure_service import ParticipantExposureService
from marketlens.human.services.judgement_service import JudgementService
from marketlens.human.services.orchestration_service import ExperimentOrchestrationService
from marketlens.human.services.round_service import ParticipantProtocolRoundService
from marketlens.human.services.session_service import SessionService
from marketlens.human.services.trusted_context_service import TrustedParticipantContextResolver
from marketlens.human.services.view_state_service import ParticipantViewStateService
from marketlens.human.stores.episode_assignment_store import EpisodeAssignmentStore
from marketlens.human.stores.judgement_store import JudgementStore
from marketlens.human.stores.orchestration_store import ExperimentOrchestrationStore
from marketlens.human.stores.round_store import RoundStore
from marketlens.human.stores.session_store import SessionStore
from marketlens.information.projection import ParticipantBackgroundProjection
from marketlens.market.status import TradingCalendar
from marketlens.persistence.database import Database
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.schema import FormalUseStatus


class ParticipantRuntimeConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ParticipantRuntime:
    sessions: SessionService
    assignments: EpisodeAssignmentService
    orchestration: ExperimentOrchestrationService
    context: TrustedParticipantContextResolver
    recorder: ParticipantRuntimeEventRecorder
    exposure: ParticipantExposureService
    judgements: JudgementService
    rounds: ParticipantProtocolRoundService
    view_state: ParticipantViewStateService
    target_stock_id: str
    episode_ids: tuple[str, ...]


def build_participant_runtime(
    *,
    db: Database,
    calendar: TradingCalendar,
    events: ParticipantEventStore,
    background_projections: Mapping[str, ParticipantBackgroundProjection],
    stimulus_engine: StimulusEngine,
) -> ParticipantRuntime:
    """Bind the already-frozen Phase 14 services without allocating an episode."""

    projections = dict(background_projections)
    if not projections:
        raise ParticipantRuntimeConfigurationError(
            "participant runtime requires at least one explicitly bound canonical episode projection"
        )

    for episode_id, projection in projections.items():
        bound_episode_id = getattr(getattr(projection, "episode", None), "episode_id", None)
        if bound_episode_id != episode_id:
            raise ParticipantRuntimeConfigurationError(
                f"background projection key {episode_id!r} disagrees with its canonical episode binding {bound_episode_id!r}"
            )

    if stimulus_engine.material.formal_use_status is not FormalUseStatus.FORMAL_FROZEN:
        raise ParticipantRuntimeConfigurationError(
            "participant runtime requires a formal_frozen controlled-stimulus engine"
        )

    sessions = SessionService(SessionStore(db))
    assignments = EpisodeAssignmentService(EpisodeAssignmentStore(db))
    orchestration = ExperimentOrchestrationService(ExperimentOrchestrationStore(db))
    context = TrustedParticipantContextResolver(
        sessions=sessions,
        assignments=assignments,
        calendar=calendar,
    )
    recorder = ParticipantRuntimeEventRecorder(store=events, context=context)
    backgrounds = EpisodeAwareParticipantBackgroundService(
        sessions=sessions,
        assignments=assignments,
        projections=projections,
    )
    exposure = ParticipantExposureService(
        backgrounds=backgrounds,  # type: ignore[arg-type]
        events=events,
        context=context,
        orchestration=orchestration,
        stimulus_engine=stimulus_engine,
    )
    target_stock_id = stimulus_engine.material.target_stock_id
    judgements = JudgementService(
        JudgementStore(db),
        ExperimentOrchestrationStore(db),
        target_stock_id=target_stock_id,
    )
    rounds = ParticipantProtocolRoundService(
        rounds=RoundStore(db),
        orchestration=orchestration,
    )
    view_state = ParticipantViewStateService(
        orchestration=orchestration,
        context=context,
        calendar=calendar,
        target_stock_id=target_stock_id,
    )

    return ParticipantRuntime(
        sessions=sessions,
        assignments=assignments,
        orchestration=orchestration,
        context=context,
        recorder=recorder,
        exposure=exposure,
        judgements=judgements,
        rounds=rounds,
        view_state=view_state,
        target_stock_id=target_stock_id,
        episode_ids=tuple(projections),
    )
