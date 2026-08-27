#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from marketlens.episode.contract import EPISODE_IDS
from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.services.episode_assignment_service import (
    FORMAL_ALLOCATOR_VERSION,
    FORMAL_ASSIGNMENT_METHOD,
)
from marketlens.main import create_app
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.material import load_material


FORMAL_STIMULUS = (
    REPO_ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json"
)


class FakeProjection:
    def __init__(self, episode_id: str):
        self.episode = SimpleNamespace(episode_id=episode_id)

    def project(self, *, current_date: str):
        return {
            "current_date": current_date,
            "natural_news": [f"phase15a2-preflight-{current_date}"],
            "forum_posts": [],
        }


def main() -> int:
    print("NON-FORMAL / ZERO-LLM / PHASE 15A2 PARTICIPANT-BOOTSTRAP PREFLIGHT")
    print("formal_participant_evidence=false")
    print("llm_api_calls=0")

    with TemporaryDirectory(prefix="marketlens-phase15a2-") as temp_dir:
        root = Path(temp_dir)
        events = ParticipantEventStore(root / "participant_events.db")
        app = create_app(
            root / "human.db",
            participant_runtime_enabled=True,
            participant_event_store=events,
            background_projections={
                episode_id: FakeProjection(episode_id) for episode_id in EPISODE_IDS
            },
            stimulus_engine=StimulusEngine(load_material(FORMAL_STIMULUS, formal=True)),
        )
        try:
            with TestClient(app) as client:
                forged = client.post(
                    "/participant-session",
                    json={
                        "participant_id": "PREFLIGHT-FORGED",
                        "request_id": "forged-bootstrap",
                        "episode_id": EPISODE_IDS[0],
                    },
                )
                assert forged.status_code == 422, forged.text

                session_ids: list[str] = []
                for index in range(6):
                    payload = {
                        "participant_id": f"PREFLIGHT-{index}",
                        "request_id": f"bootstrap-{index}",
                    }
                    response = client.post("/participant-session", json=payload)
                    assert response.status_code == 201, response.text
                    body = response.json()
                    assert "episode_id" not in body
                    session_ids.append(body["session_id"])

                replay = client.post(
                    "/participant-session",
                    json={
                        "participant_id": "PREFLIGHT-0",
                        "request_id": "bootstrap-0",
                    },
                )
                assert replay.status_code == 201, replay.text
                assert replay.json()["session_id"] == session_ids[0]

                assignments = [
                    app.state.participant_runtime.assignments.get(session_id)
                    for session_id in session_ids
                ]
                assert all(item is not None for item in assignments)
                counts = Counter(item.episode_id for item in assignments if item is not None)
                assert [counts[episode_id] for episode_id in EPISODE_IDS] == [2, 2, 2]
                assert all(
                    item.assignment_method == FORMAL_ASSIGNMENT_METHOD
                    and item.assignment_version == FORMAL_ALLOCATOR_VERSION
                    for item in assignments
                    if item is not None
                )

                view = client.get(f"/session/{session_ids[0]}/view")
                assert view.status_code == 200, view.text
                assert view.json()["required_action"] == "LOAD_MARKET_INFORMATION"
                assert "episode_id" not in view.json()

                paths = client.get("/openapi.json").json()["paths"]
                assert "/participant-session" in paths
                assert "/session" not in paths
        finally:
            events.dispose()
            app.state.db.dispose()

    print("PHASE15A2_PARTICIPANT_BOOTSTRAP_PREFLIGHT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
