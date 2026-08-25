from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.measurement.models import ParticipantEventType
from marketlens.human.orchestration import ParticipantStage
from marketlens.human.schemas import ParticipantBackgroundRead
from marketlens.human.services.exposure_service import (
    ParticipantExposureService,
    ParticipantExposureUnavailableError,
)
from marketlens.human.services.orchestration_service import ParticipantExperimentState
from marketlens.human.services.trusted_context_service import TrustedParticipantContext
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.material import load_material


class FakeBackgrounds:
    def __init__(self, session_id: str, current_date: str):
        self.value = ParticipantBackgroundRead(
            session_id=session_id,
            current_date=current_date,
            natural_news=["Canonical natural news"],
            forum_posts=[],
        )

    def get_current_background(self, _session_id: str):
        return self.value


class FakeContext:
    def __init__(self, value: TrustedParticipantContext):
        self.value = value

    def resolve(self, _session_id: str):
        return self.value


class FakeOrchestration:
    def __init__(self, state: ParticipantExperimentState):
        self.state = state
        self.background_transitions = 0
        self.stimulus_transitions = 0

    def get(self, _session_id: str):
        return self.state

    def after_background_delivery(self, _session_id: str):
        self.background_transitions += 1
        next_stage = (
            ParticipantStage.J0_REQUIRED.value
            if self.state.experiment_step == 0
            else ParticipantStage.ROUND_ACTIVE.value
        )
        self.state = replace(self.state, current_stage=next_stage)
        return self.state

    def after_stimulus_delivery(self, _session_id: str):
        self.stimulus_transitions += 1
        if self.state.current_stage == ParticipantStage.MISINFORMATION_DELIVERY_REQUIRED.value:
            next_stage = ParticipantStage.J1_REQUIRED.value
        elif self.state.current_stage == ParticipantStage.CORRECTION_DELIVERY_REQUIRED.value:
            next_stage = ParticipantStage.J3_REQUIRED.value
        else:
            raise AssertionError("unexpected stimulus stage")
        self.state = replace(self.state, current_stage=next_stage)
        return self.state


def trusted(*, step: int, date: str) -> TrustedParticipantContext:
    return TrustedParticipantContext(
        session_id="S001",
        participant_id="P001",
        assignment_id="A001",
        episode_pool_id="marketlens-canonical-episode-pool-v1",
        episode_id="marketlens-canonical-episode-v1-e01",
        assignment_method="balanced_random_across_episode_pool",
        assignment_version="phase14b1-v1",
        protocol_version="1.1",
        experiment_step=step,
        agent_world_date=date,
        market_open=True,
        market_status_reason="trading_day",
        current_market_date=date,
        market_state_date=date,
        participant_trading_enabled=True,
    )


def state(*, step: int, date: str, stage: ParticipantStage) -> ParticipantExperimentState:
    return ParticipantExperimentState(
        session_id="S001",
        participant_id="P001",
        experiment_step=step,
        agent_world_date=date,
        current_stage=stage.value,
        experiment_status="active",
        completed=False,
    )


def formal_engine() -> StimulusEngine:
    root = Path(__file__).resolve().parents[3]
    material = load_material(
        root / "data/marketlens/stimuli/stimulus_v1.formal.json",
        formal=True,
    )
    return StimulusEngine(material)


def test_background_delivery_records_then_advances_and_replays(tmp_path) -> None:
    events = ParticipantEventStore(tmp_path / "events.db")
    ctx = trusted(step=0, date="2023-06-19")
    orchestration = FakeOrchestration(
        state(step=0, date="2023-06-19", stage=ParticipantStage.BACKGROUND_REQUIRED)
    )
    service = ParticipantExposureService(
        backgrounds=FakeBackgrounds("S001", "2023-06-19"),
        events=events,
        context=FakeContext(ctx),
        orchestration=orchestration,
    )

    first = service.deliver_background("S001", "background-001")
    second = service.deliver_background("S001", "background-001")

    assert first == second
    assert orchestration.background_transitions == 1
    rows = events.list_for_session("S001")
    assert len(rows) == 1
    assert rows[0]["event_type"] == ParticipantEventType.BACKGROUND_EXPOSED.value
    assert rows[0]["payload_digest"] is not None


def test_background_event_repairs_interrupted_stage_transition(tmp_path) -> None:
    events = ParticipantEventStore(tmp_path / "events.db")
    ctx = trusted(step=0, date="2023-06-19")
    orchestration = FakeOrchestration(
        state(step=0, date="2023-06-19", stage=ParticipantStage.BACKGROUND_REQUIRED)
    )
    service = ParticipantExposureService(
        backgrounds=FakeBackgrounds("S001", "2023-06-19"),
        events=events,
        context=FakeContext(ctx),
        orchestration=orchestration,
    )

    original = orchestration.after_background_delivery
    calls = {"count": 0}

    def fail_once(session_id: str):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("simulated interruption")
        return original(session_id)

    orchestration.after_background_delivery = fail_once
    with pytest.raises(RuntimeError):
        service.deliver_background("S001", "background-recover")
    assert len(events.list_for_session("S001")) == 1
    assert orchestration.state.current_stage == ParticipantStage.BACKGROUND_REQUIRED.value

    service.deliver_background("S001", "background-recover")
    assert orchestration.state.current_stage == ParticipantStage.J0_REQUIRED.value
    assert len(events.list_for_session("S001")) == 1


def test_misinformation_release_is_server_stage_derived_and_retry_safe(tmp_path) -> None:
    engine = formal_engine()
    events = ParticipantEventStore(tmp_path / "events.db")
    ctx = trusted(step=engine.misinformation_step, date=engine.checkpoint_date(engine.misinformation_step))
    orchestration = FakeOrchestration(
        state(
            step=engine.misinformation_step,
            date=ctx.agent_world_date,
            stage=ParticipantStage.MISINFORMATION_DELIVERY_REQUIRED,
        )
    )
    service = ParticipantExposureService(
        backgrounds=FakeBackgrounds("S001", ctx.agent_world_date),
        events=events,
        context=FakeContext(ctx),
        orchestration=orchestration,
        stimulus_engine=engine,
    )

    first = service.deliver_controlled_stimulus("S001", "stimulus-001")
    second = service.deliver_controlled_stimulus("S001", "stimulus-001")

    assert first == second
    assert first.stimulus_id == engine.material.misinformation.stimulus_id
    assert first.source_label == "Market News Report"
    assert orchestration.stimulus_transitions == 1
    rows = events.list_for_session("S001")
    assert len(rows) == 1
    assert rows[0]["event_type"] == ParticipantEventType.CONTROLLED_STIMULUS_EXPOSED.value
    assert rows[0]["stimulus_sha256"] == engine.material.misinformation.content_sha256


def test_correction_release_returns_only_new_correction_item(tmp_path) -> None:
    engine = formal_engine()
    events = ParticipantEventStore(tmp_path / "events.db")
    ctx = trusted(step=engine.correction_step, date=engine.checkpoint_date(engine.correction_step))
    orchestration = FakeOrchestration(
        state(
            step=engine.correction_step,
            date=ctx.agent_world_date,
            stage=ParticipantStage.CORRECTION_DELIVERY_REQUIRED,
        )
    )
    service = ParticipantExposureService(
        backgrounds=FakeBackgrounds("S001", ctx.agent_world_date),
        events=events,
        context=FakeContext(ctx),
        orchestration=orchestration,
        stimulus_engine=engine,
    )

    result = service.deliver_controlled_stimulus("S001", "correction-001")

    assert result.stimulus_id == engine.material.correction.stimulus_id
    assert result.source_label == "LONGi Green Energy"
    assert result.corrects_stimulus_id == engine.material.misinformation.stimulus_id
    assert orchestration.state.current_stage == ParticipantStage.J3_REQUIRED.value


def test_controlled_stimulus_fails_outside_server_delivery_stage(tmp_path) -> None:
    engine = formal_engine()
    events = ParticipantEventStore(tmp_path / "events.db")
    ctx = trusted(step=0, date="2023-06-19")
    orchestration = FakeOrchestration(
        state(step=0, date="2023-06-19", stage=ParticipantStage.J0_REQUIRED)
    )
    service = ParticipantExposureService(
        backgrounds=FakeBackgrounds("S001", "2023-06-19"),
        events=events,
        context=FakeContext(ctx),
        orchestration=orchestration,
        stimulus_engine=engine,
    )

    with pytest.raises(ParticipantExposureUnavailableError):
        service.deliver_controlled_stimulus("S001", "not-authorised")
    assert events.list_for_session("S001") == ()


def test_development_material_is_rejected_for_participant_delivery(tmp_path) -> None:
    root = Path(__file__).resolve().parents[3]
    development = StimulusEngine(
        load_material(root / "data/marketlens/stimuli/stimulus_v1.development.json")
    )
    events = ParticipantEventStore(tmp_path / "events.db")
    ctx = trusted(step=development.misinformation_step, date=development.checkpoint_date(development.misinformation_step))
    orchestration = FakeOrchestration(
        state(
            step=development.misinformation_step,
            date=ctx.agent_world_date,
            stage=ParticipantStage.MISINFORMATION_DELIVERY_REQUIRED,
        )
    )
    service = ParticipantExposureService(
        backgrounds=FakeBackgrounds("S001", ctx.agent_world_date),
        events=events,
        context=FakeContext(ctx),
        orchestration=orchestration,
        stimulus_engine=development,
    )

    with pytest.raises(ParticipantExposureUnavailableError, match="formal_frozen"):
        service.deliver_controlled_stimulus("S001", "development-rejected")
    assert events.list_for_session("S001") == ()
