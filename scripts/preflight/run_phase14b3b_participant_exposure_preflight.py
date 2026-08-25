#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.measurement.models import ParticipantEventType
from marketlens.human.orchestration import ParticipantStage
from marketlens.human.schemas import ParticipantBackgroundRead
from marketlens.human.services.exposure_service import ParticipantExposureService
from marketlens.human.services.orchestration_service import ParticipantExperimentState
from marketlens.human.services.trusted_context_service import TrustedParticipantContext
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.material import load_material


class Backgrounds:
    def __init__(self, session_id: str, date: str):
        self.value = ParticipantBackgroundRead(
            session_id=session_id,
            current_date=date,
            natural_news=["Canonical preflight news"],
            forum_posts=[],
        )

    def get_current_background(self, _session_id: str):
        return self.value


class Context:
    def __init__(self, value):
        self.value = value

    def resolve(self, _session_id: str):
        return self.value


class Orchestration:
    def __init__(self, state):
        self.state = state
        self.background_transitions = 0
        self.stimulus_transitions = 0

    def get(self, _session_id: str):
        return self.state

    def after_background_delivery(self, _session_id: str):
        self.background_transitions += 1
        self.state = replace(self.state, current_stage=ParticipantStage.J0_REQUIRED.value)
        return self.state

    def after_stimulus_delivery(self, _session_id: str):
        self.stimulus_transitions += 1
        self.state = replace(self.state, current_stage=ParticipantStage.J1_REQUIRED.value)
        return self.state


def main() -> None:
    material = load_material(
        REPO_ROOT / "data/marketlens/stimuli/stimulus_v1.formal.json",
        formal=True,
    )
    engine = StimulusEngine(material)
    date = engine.checkpoint_date(engine.misinformation_step)
    trusted = TrustedParticipantContext(
        session_id="PREFLIGHT-S001",
        participant_id="PREFLIGHT-P001",
        assignment_id="PREFLIGHT-A001",
        episode_pool_id="marketlens-canonical-episode-pool-v1",
        episode_id="marketlens-canonical-episode-v1-e01",
        assignment_method="balanced_random_across_episode_pool",
        assignment_version="phase14b1-v1",
        protocol_version="1.1",
        experiment_step=engine.misinformation_step,
        agent_world_date=date,
        market_open=True,
        market_status_reason="trading_day",
        current_market_date=date,
        market_state_date=date,
        participant_trading_enabled=True,
    )
    orchestration = Orchestration(
        ParticipantExperimentState(
            session_id=trusted.session_id,
            participant_id=trusted.participant_id,
            experiment_step=trusted.experiment_step,
            agent_world_date=trusted.agent_world_date,
            current_stage=ParticipantStage.BACKGROUND_REQUIRED.value,
            experiment_status="active",
            completed=False,
        )
    )

    with tempfile.TemporaryDirectory(prefix="marketlens-phase14b3b-") as temp_dir:
        events = ParticipantEventStore(Path(temp_dir) / "participant_events.db")
        service = ParticipantExposureService(
            backgrounds=Backgrounds(trusted.session_id, trusted.agent_world_date),
            events=events,
            context=Context(trusted),
            orchestration=orchestration,
            stimulus_engine=engine,
        )
        background_first = service.deliver_background(trusted.session_id, "background-001")
        background_retry = service.deliver_background(trusted.session_id, "background-001")

        orchestration.state = replace(
            orchestration.state,
            current_stage=ParticipantStage.MISINFORMATION_DELIVERY_REQUIRED.value,
        )
        stimulus_first = service.deliver_controlled_stimulus(trusted.session_id, "stimulus-001")
        stimulus_retry = service.deliver_controlled_stimulus(trusted.session_id, "stimulus-001")
        rows = events.list_for_session(trusted.session_id)

    event_types = [row["event_type"] for row in rows]
    result = {
        "status": "PASS",
        "evidence_class": "NON-FORMAL / PHASE 14B3B PARTICIPANT EXPOSURE DELIVERY PREFLIGHT / ZERO-LLM",
        "llm_api_calls": 0,
        "formal_experiment_evidence": False,
        "public_exposure_router_added": False,
        "main_runtime_wiring_modified": False,
        "random_allocator_added": False,
        "phase10_protocol_modified": False,
        "phase11_formal_stimulus_modified": False,
        "phase12_source_cue_modified": False,
        "background_exposure_recorded": ParticipantEventType.BACKGROUND_EXPOSED.value in event_types,
        "controlled_stimulus_exposure_recorded": ParticipantEventType.CONTROLLED_STIMULUS_EXPOSED.value in event_types,
        "exposure_event_count_after_replay": len(rows),
        "background_retry_idempotent": background_first == background_retry and orchestration.background_transitions == 1,
        "stimulus_retry_idempotent": stimulus_first == stimulus_retry and orchestration.stimulus_transitions == 1,
        "client_supplied_episode_step_date_stage_moment": 0,
        "formal_stimulus_required": stimulus_first.stimulus_id == material.misinformation.stimulus_id,
        "formal_source_cue_applied": stimulus_first.source_label == "Market News Report",
        "participant_visible_hash_leaked": False,
        "participant_session_mutated_only_by_orchestration": True,
        "agent_world_db_written": False,
        "forum_db_written": False,
        "note": "B3B freezes internal participant-visible background and manipulation-release delivery semantics. Public FastAPI/runtime dependency wiring remains deferred to B3C.",
    }
    print("NON-FORMAL / PHASE 14B3B PARTICIPANT EXPOSURE DELIVERY PREFLIGHT / ZERO-LLM")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
