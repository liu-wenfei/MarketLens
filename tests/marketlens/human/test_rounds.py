from conftest import create_session


def round_payload(request_id="round-0-complete", step=0):
    return {"request_id": request_id, "step": step}


def test_round_completion_advances_exactly_one_step(client):
    session = create_session(client)
    session_id = session["session_id"]

    response = client.post(
        f"/session/{session_id}/round/complete",
        json=round_payload(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["step"] == 0
    assert body["next_step"] == 1

    state = client.get(f"/session/{session_id}/state").json()
    assert state["current_step"] == 1


def test_round_completion_retry_is_idempotent(client):
    session = create_session(client)
    session_id = session["session_id"]
    payload = round_payload(request_id="retry-round")

    first = client.post(f"/session/{session_id}/round/complete", json=payload)
    second = client.post(f"/session/{session_id}/round/complete", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["completion_id"] == second.json()["completion_id"]
    assert client.get(f"/session/{session_id}/state").json()["current_step"] == 1


def test_same_request_id_cannot_complete_a_different_step(client):
    session = create_session(client)
    session_id = session["session_id"]

    assert client.post(
        f"/session/{session_id}/round/complete",
        json=round_payload(request_id="shared-round-request", step=0),
    ).status_code == 201

    response = client.post(
        f"/session/{session_id}/round/complete",
        json=round_payload(request_id="shared-round-request", step=1),
    )
    assert response.status_code == 409


def test_second_completion_for_same_step_with_new_request_is_rejected(client):
    session = create_session(client)
    session_id = session["session_id"]

    assert client.post(
        f"/session/{session_id}/round/complete",
        json=round_payload(request_id="first-completion", step=0),
    ).status_code == 201

    response = client.post(
        f"/session/{session_id}/round/complete",
        json=round_payload(request_id="second-completion", step=0),
    )
    assert response.status_code == 409


def test_wrong_future_round_step_is_rejected(client):
    session = create_session(client)
    response = client.post(
        f"/session/{session['session_id']}/round/complete",
        json=round_payload(step=1),
    )
    assert response.status_code == 409


def test_unknown_session_round_completion_is_rejected(client):
    response = client.post(
        "/session/not-real/round/complete",
        json=round_payload(),
    )
    assert response.status_code == 404
