from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from marketlens.episode.contract_v2 import (
    EPISODE_IDS,
    EPISODE_POOL_ID,
)
from marketlens.participant_server import (
    create_formal_participant_app,
)


ROOT = Path(__file__).resolve().parents[3]


def test_formal_v2_participant_server_bootstrap(
    tmp_path: Path,
) -> None:
    app = create_formal_participant_app(
        repo_root=ROOT,
        db_path=tmp_path / "human.db",
        participant_event_db_path=(
            tmp_path / "participant_events.db"
        ),
    )

    events = (
        app.state.formal_participant_event_store
    )

    try:
        runtime = app.state.participant_runtime

        assert runtime is not None

        assert (
            runtime.episode_pool_id
            == EPISODE_POOL_ID
        )

        assert set(runtime.episode_ids) == set(
            EPISODE_IDS
        )

        assert set(
            runtime.expected_episode_ids
        ) == set(EPISODE_IDS)

        with TestClient(app) as client:
            health = client.get("/health")
            assert health.status_code == 200

            created = client.post(
                "/participant-session",
                json={
                    "participant_id": "P-SMOKE-001",
                    "request_id": "formal-v2-smoke",
                },
            )

            assert created.status_code == 201, (
                created.text
            )

            body = created.json()

            assert "episode_id" not in body

            session_id = body["session_id"]

            assignment = (
                runtime.assignments.get(session_id)
            )

            assert assignment is not None

            assert (
                assignment.episode_pool_id
                == EPISODE_POOL_ID
            )

            assert assignment.episode_id in (
                EPISODE_IDS
            )

            view = client.get(
                f"/session/{session_id}/view"
            )

            assert view.status_code == 200, (
                view.text
            )

            payload = view.json()

            assert payload["required_action"] == (
                "LOAD_MARKET_INFORMATION"
            )

            assert "episode_id" not in payload

    finally:
        events.dispose()
        app.state.db.dispose()


def test_formal_server_cors_allows_vite_origin(
    tmp_path: Path,
) -> None:
    app = create_formal_participant_app(
        repo_root=ROOT,
        db_path=tmp_path / "human.db",
        participant_event_db_path=(
            tmp_path / "participant_events.db"
        ),
    )

    events = (
        app.state.formal_participant_event_store
    )

    try:
        with TestClient(app) as client:
            response = client.options(
                "/participant-session",
                headers={
                    "Origin": (
                        "http://localhost:5173"
                    ),
                    "Access-Control-Request-Method": (
                        "POST"
                    ),
                },
            )

            assert response.status_code == 200

            assert (
                response.headers[
                    "access-control-allow-origin"
                ]
                == "http://localhost:5173"
            )

    finally:
        events.dispose()
        app.state.db.dispose()
