from conftest import create_session


def test_session_can_be_created_and_retrieved(client):
    session = create_session(client)

    response = client.get(f"/session/{session['session_id']}")
    assert response.status_code == 200
    assert response.json()["participant_id"] == "P001"
    assert response.json()["current_step"] == 0
    assert response.json()["completed"] is False


def test_session_creation_is_idempotent(client):
    first = create_session(client, request_id="same-create-request")
    second = create_session(client, request_id="same-create-request")
    assert second["session_id"] == first["session_id"]


def test_session_request_id_cannot_be_reused_for_another_participant(client):
    create_session(client, participant_id="P001", request_id="shared-request")
    response = client.post(
        "/session",
        json={"participant_id": "P002", "request_id": "shared-request"},
    )
    assert response.status_code == 409


def test_unknown_session_is_rejected(client):
    assert client.get("/session/not-real").status_code == 404
    assert client.get("/session/not-real/state").status_code == 404


def test_state_exposes_only_current_human_session_state(client):
    session = create_session(client)
    response = client.get(f"/session/{session['session_id']}/state")
    assert response.status_code == 200

    state = response.json()
    assert set(state) == {
        "session_id",
        "current_step",
        "current_date",
        "experiment_status",
        "completed",
    }
    assert state["current_step"] == 0

    forbidden = {
        "future_prices",
        "future_stimuli",
        "future_correction",
        "condition",
        "ground_truth",
        "future_agent_activity",
    }
    assert forbidden.isdisjoint(state)


def test_session_and_step_persist_across_app_restart(tmp_path):
    from fastapi.testclient import TestClient
    from marketlens.main import create_app

    db_path = tmp_path / "persistent.db"
    with TestClient(create_app(db_path)) as first_client:
        session = create_session(first_client, request_id="persist-session")
        session_id = session["session_id"]
        response = first_client.post(
            f"/session/{session_id}/decision",
            json={
                "request_id": "persist-decision",
                "step": 0,
                "stock_id": "TEST",
                "action": "HOLD",
                "confidence": 50,
                "evidence_sources": [],
                "rationale": None,
            },
        )
        assert response.status_code == 201

    with TestClient(create_app(db_path)) as second_client:
        restored = second_client.get(f"/session/{session_id}")
        assert restored.status_code == 200
        assert restored.json()["current_step"] == 1
