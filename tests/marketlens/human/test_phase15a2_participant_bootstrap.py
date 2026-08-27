from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from marketlens.episode.contract import EPISODE_IDS
from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.schemas import SessionCreate
from marketlens.human.services.episode_assignment_service import (
    FORMAL_ALLOCATOR_VERSION,
    FORMAL_ASSIGNMENT_METHOD,
    EpisodeAssignmentService,
)
from marketlens.human.services.session_service import SessionService
from marketlens.human.stores.episode_assignment_store import EpisodeAssignmentStore
from marketlens.human.stores.session_store import SessionStore
from marketlens.main import create_app
from marketlens.persistence.database import Database
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.material import load_material


ROOT = Path(__file__).resolve().parents[3]
FORMAL_STIMULUS = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json"


class FakeProjection:
    def __init__(self, episode_id: str):
        self.episode = SimpleNamespace(episode_id=episode_id)

    def project(self, *, current_date: str):
        return {
            "current_date": current_date,
            "natural_news": [f"background-{self.episode.episode_id}-{current_date}"],
            "forum_posts": [],
        }


def _runtime_app(tmp_path: Path, *, episode_ids=EPISODE_IDS):
    events = ParticipantEventStore(tmp_path / "participant_events.db")
    engine = StimulusEngine(load_material(FORMAL_STIMULUS, formal=True))
    app = create_app(
        tmp_path / "human.db",
        participant_runtime_enabled=True,
        participant_event_store=events,
        background_projections={episode_id: FakeProjection(episode_id) for episode_id in episode_ids},
        stimulus_engine=engine,
    )
    return app, events


def test_formal_bootstrap_rejects_client_episode_control_and_hides_assignment(tmp_path) -> None:
    app, events = _runtime_app(tmp_path)
    try:
        with TestClient(app) as client:
            forged = client.post(
                "/participant-session",
                json={
                    "participant_id": "P001",
                    "request_id": "bootstrap-001",
                    "episode_id": EPISODE_IDS[0],
                },
            )
            assert forged.status_code == 422

            created = client.post(
                "/participant-session",
                json={"participant_id": "P001", "request_id": "bootstrap-001"},
            )
            assert created.status_code == 201, created.text
            body = created.json()
            assert set(body) == {
                "session_id",
                "participant_id",
                "created_at",
                "current_step",
                "current_date",
                "experiment_status",
                "completed",
            }
            assert "episode_id" not in body
            assert body["current_step"] == 0
            assert body["current_date"] == "2023-06-19"

            assignment = app.state.participant_runtime.assignments.get(body["session_id"])
            assert assignment is not None
            assert assignment.episode_id in EPISODE_IDS
            assert assignment.assignment_method == FORMAL_ASSIGNMENT_METHOD
            assert assignment.assignment_version == FORMAL_ALLOCATOR_VERSION

            view = client.get(f"/session/{body['session_id']}/view")
            assert view.status_code == 200, view.text
            assert view.json()["required_action"] == "LOAD_MARKET_INFORMATION"
            assert "episode_id" not in view.json()
    finally:
        events.dispose()
        app.state.db.dispose()


def test_bootstrap_is_idempotent_and_reuses_one_persisted_assignment(tmp_path) -> None:
    app, events = _runtime_app(tmp_path)
    try:
        with TestClient(app) as client:
            payload = {"participant_id": "P002", "request_id": "bootstrap-retry"}
            first = client.post("/participant-session", json=payload)
            second = client.post("/participant-session", json=payload)
            assert first.status_code == second.status_code == 201
            assert first.json()["session_id"] == second.json()["session_id"]

            sid = first.json()["session_id"]
            first_assignment = app.state.participant_runtime.assignments.get(sid)
            second_assignment = app.state.participant_runtime.assignments.get(sid)
            assert first_assignment is not None and second_assignment is not None
            assert first_assignment.assignment_id == second_assignment.assignment_id
    finally:
        events.dispose()
        app.state.db.dispose()


def test_balanced_random_policy_keeps_three_episode_counts_within_one(tmp_path) -> None:
    app, events = _runtime_app(tmp_path)
    try:
        with TestClient(app) as client:
            session_ids = []
            for index in range(8):
                response = client.post(
                    "/participant-session",
                    json={
                        "participant_id": f"P{index:03d}",
                        "request_id": f"bootstrap-{index:03d}",
                    },
                )
                assert response.status_code == 201, response.text
                session_ids.append(response.json()["session_id"])

            assigned = [
                app.state.participant_runtime.assignments.get(session_id).episode_id
                for session_id in session_ids
            ]
            counts = Counter(assigned)
            values = [counts[episode_id] for episode_id in EPISODE_IDS]
            assert max(values) - min(values) <= 1
            assert sum(values) == 8
    finally:
        events.dispose()
        app.state.db.dispose()


def test_sqlite_allocator_serializes_concurrent_count_choose_insert(tmp_path) -> None:
    db = Database(tmp_path / "allocator.db")
    sessions = SessionService(SessionStore(db))
    assignments = EpisodeAssignmentService(
        EpisodeAssignmentStore(db),
        formal_chooser=lambda candidates: candidates[0],
    )
    session_ids = [
        sessions.create(
            SessionCreate(
                participant_id=f"PC{index:03d}",
                request_id=f"concurrent-session-{index:03d}",
            )
        ).session_id
        for index in range(12)
    ]

    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            allocated = list(pool.map(assignments.allocate_balanced_random, session_ids))
        counts = Counter(row.episode_id for row in allocated)
        assert [counts[episode_id] for episode_id in EPISODE_IDS] == [4, 4, 4]
    finally:
        db.dispose()


def test_formal_bootstrap_requires_complete_pool_and_is_only_public_creation_route(tmp_path) -> None:
    app, events = _runtime_app(tmp_path, episode_ids=(EPISODE_IDS[0],))
    try:
        with TestClient(app) as client:
            response = client.post(
                "/participant-session",
                json={"participant_id": "P003", "request_id": "incomplete-pool"},
            )
            assert response.status_code == 503
            assert "complete frozen canonical episode pool" in response.json()["detail"]

            paths = client.get("/openapi.json").json()["paths"]
            assert "/participant-session" in paths
            assert "/session" not in paths
    finally:
        events.dispose()
        app.state.db.dispose()
