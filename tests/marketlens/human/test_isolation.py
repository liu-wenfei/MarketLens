from conftest import create_session


def test_two_participant_sessions_remain_isolated(client):
    session_a = create_session(client, participant_id="P-A", request_id="create-a")
    session_b = create_session(client, participant_id="P-B", request_id="create-b")

    response = client.post(
        f"/session/{session_a['session_id']}/decision",
        json={
            "request_id": "a-decision-1",
            "step": 0,
            "stock_id": "TEST",
            "action": "HOLD",
            "confidence": 50,
            "evidence_sources": [],
            "rationale": None,
        },
    )
    assert response.status_code == 201

    state_a = client.get(f"/session/{session_a['session_id']}/state").json()
    state_b = client.get(f"/session/{session_b['session_id']}/state").json()

    assert state_a["current_step"] == 1
    assert state_b["current_step"] == 0
