#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from marketlens.episode.contract import EPISODE_IDS
from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.main import create_app
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.material import load_material


ROOT = REPO_ROOT
FORMAL_STIMULUS = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json"


class FakeProjection:
    def __init__(self, episode_id: str):
        self.episode = SimpleNamespace(episode_id=episode_id)

    def project(self, *, current_date: str):
        return {
            "current_date": current_date,
            "natural_news": ["phase15a1-preflight-background"],
            "forum_posts": [],
        }


def main() -> int:
    print("NON-FORMAL / ZERO-LLM / PHASE 15A1 STATE-CONTRACT PREFLIGHT")
    print("formal_participant_evidence=false")
    print("llm_api_calls=0")

    episode_id = EPISODE_IDS[0]
    with TemporaryDirectory(prefix="marketlens-phase15a1-") as tmp:
        tmp_path = Path(tmp)
        events = ParticipantEventStore(tmp_path / "participant_events.db")
        engine = StimulusEngine(load_material(FORMAL_STIMULUS, formal=True))
        app = create_app(
            tmp_path / "human.db",
            participant_runtime_enabled=True,
            participant_event_store=events,
            background_projections={episode_id: FakeProjection(episode_id)},
            stimulus_engine=engine,
        )
        try:
            with TestClient(app) as client:
                session = client.post(
                    "/session",
                    json={"participant_id": "PREFLIGHT", "request_id": "session-create"},
                )
                assert session.status_code == 201, session.text
                sid = session.json()["session_id"]
                app.state.participant_runtime.assignments.bind(
                    sid,
                    episode_id,
                    assignment_method="phase15a1-preflight-fixed",
                    assignment_version="phase15a1-preflight-v1",
                )

                initial = client.get(f"/session/{sid}/view")
                assert initial.status_code == 200, initial.text
                initial_body = initial.json()
                assert initial_body["required_action"] == "LOAD_MARKET_INFORMATION"
                assert initial_body["allowed_actions"]["submit_trade"] is False
                assert "current_stage" not in initial_body

                background = client.post(
                    f"/session/{sid}/exposure/background",
                    json={"request_id": "bg-0"},
                )
                assert background.status_code == 200, background.text

                assessment_view = client.get(f"/session/{sid}/view").json()
                assert assessment_view["required_action"] == "SUBMIT_ASSESSMENT"
                assert assessment_view["assessment_mode"] == "PRE_UPDATE"

                assessment = client.post(
                    f"/session/{sid}/assessment",
                    json={
                        "request_id": "assessment-0",
                        "action": "HOLD",
                        "confidence": 70,
                        "evidence_sources": ["market-information"],
                        "rationale": "preflight",
                    },
                )
                assert assessment.status_code == 201, assessment.text
                assert "judgement_event" not in assessment.json()

                update = client.post(
                    f"/session/{sid}/information-update",
                    json={"request_id": "info-0"},
                )
                assert update.status_code == 200, update.text
                update_body = update.json()
                for forbidden in (
                    "kind",
                    "stimulus_id",
                    "corrects_stimulus_id",
                    "content_sha256",
                ):
                    assert forbidden not in update_body

                openapi_paths = client.get("/openapi.json").json()["paths"]
                assert "/session/{session_id}/view" in openapi_paths
                assert "/session/{session_id}/assessment" in openapi_paths
                assert "/session/{session_id}/information-update" in openapi_paths
                assert "/session/{session_id}/judgement" not in openapi_paths
                assert "/session/{session_id}/exposure/stimulus" not in openapi_paths
        finally:
            events.dispose()

    print("PHASE15A1_PREFLIGHT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
