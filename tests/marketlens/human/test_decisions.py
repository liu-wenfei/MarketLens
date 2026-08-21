from conftest import create_session


def decision_payload(request_id="decision-1", step=0, action="BUY", confidence=75):
    return {
        "request_id": request_id,
        "step": step,
        "stock_id": "TEST",
        "action": action,
        "confidence": confidence,
        "evidence_sources": ["news-001"],
        "rationale": "Test rationale",
    }


def test_decision_persists_without_advancing_session_step(client):
    session = create_session(client)
    session_id = session["session_id"]

    response = client.post(
        f"/session/{session_id}/decision",
        json=decision_payload(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["session_id"] == session_id
    assert body["step"] == 0
    assert body["action"] == "BUY"

    state = client.get(f"/session/{session_id}/state").json()
    assert state["current_step"] == 0


def test_decision_retry_with_same_request_id_is_idempotent(client):
    session = create_session(client)
    session_id = session["session_id"]
    payload = decision_payload(request_id="retry-me")

    first = client.post(f"/session/{session_id}/decision", json=payload)
    second = client.post(f"/session/{session_id}/decision", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["decision_id"] == second.json()["decision_id"]
    assert client.get(f"/session/{session_id}/state").json()["current_step"] == 0



def test_same_request_id_cannot_be_reused_for_different_decision_payload(client):
    session = create_session(client)
    session_id = session["session_id"]

    first = client.post(
        f"/session/{session_id}/decision",
        json=decision_payload(request_id="shared-decision-request", step=0, action="BUY"),
    )
    assert first.status_code == 201

    changed_action = client.post(
        f"/session/{session_id}/decision",
        json=decision_payload(request_id="shared-decision-request", step=0, action="SELL"),
    )
    assert changed_action.status_code == 409

    changed_step = client.post(
        f"/session/{session_id}/decision",
        json=decision_payload(request_id="shared-decision-request", step=1, action="BUY"),
    )
    assert changed_step.status_code == 409

def test_second_decision_for_same_step_with_new_request_is_rejected(client):
    session = create_session(client)
    session_id = session["session_id"]

    assert client.post(
        f"/session/{session_id}/decision",
        json=decision_payload(request_id="first", step=0),
    ).status_code == 201

    response = client.post(
        f"/session/{session_id}/decision",
        json=decision_payload(request_id="second", step=0),
    )
    assert response.status_code == 409


def test_wrong_future_step_is_rejected(client):
    session = create_session(client)
    response = client.post(
        f"/session/{session['session_id']}/decision",
        json=decision_payload(step=1),
    )
    assert response.status_code == 409


def test_unknown_session_decision_is_rejected(client):
    response = client.post(
        "/session/not-real/decision",
        json=decision_payload(),
    )
    assert response.status_code == 404


def test_invalid_action_and_confidence_are_rejected_by_schema(client):
    session = create_session(client)
    url = f"/session/{session['session_id']}/decision"

    invalid_action = client.post(url, json=decision_payload(action="WATCH"))
    invalid_confidence = client.post(url, json=decision_payload(confidence=101))

    assert invalid_action.status_code == 422
    assert invalid_confidence.status_code == 422
