from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from marketlens.formal_auth import (
    FormalAuthProvisioningError,
    FormalAuthStore,
    create_authenticated_formal_gateway,
)
from marketlens.participant_server import (
    create_formal_participant_app,
)
from marketlens.persistence.schema import (
    participant_episode_assignments,
    sessions,
)


ROOT = Path(__file__).resolve().parents[3]
PASSWORD = "ABCD-EFGH-JKLM"


@pytest.fixture
def authenticated_app(tmp_path):
    inner = create_formal_participant_app(
        repo_root=ROOT,
        db_path=tmp_path / "participant.db",
        participant_event_db_path=(
            tmp_path / "events.db"
        ),
        allowed_origins=(
            "http://localhost:5173",
        ),
    )

    auth = FormalAuthStore(
        tmp_path / "participant_auth.db"
    )
    auth.provision_account(
        participant_id="P001",
        password=PASSWORD,
    )
    auth.provision_account(
        participant_id="P002",
        password=PASSWORD,
    )

    gateway = create_authenticated_formal_gateway(
        inner_app=inner,
        auth_store=auth,
        allowed_origins=(
            "http://localhost:5173",
        ),
    )

    try:
        yield gateway, inner, auth
    finally:
        inner.state.formal_participant_event_store.dispose()
        inner.state.db.dispose()


def _login(
    client: TestClient,
    participant_id: str,
    password: str = PASSWORD,
):
    return client.post(
        "/auth/login",
        json={
            "participant_id": participant_id,
            "password": password,
        },
    )


def _auth_header(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}"
    }


def test_auth_db_has_private_permissions_and_no_plaintext(
    tmp_path,
):
    path = tmp_path / "participant_auth.db"
    store = FormalAuthStore(path)
    store.provision_account(
        participant_id="P001",
        password=PASSWORD,
    )

    assert (path.stat().st_mode & 0o777) == 0o600

    with sqlite3.connect(path) as connection:
        account = connection.execute(
            """
            SELECT
                participant_id,
                password_salt,
                password_hash
            FROM participant_accounts
            """
        ).fetchone()

    assert account is not None
    assert account[0] == "P001"
    assert PASSWORD.encode("utf-8") not in bytes(
        account[1]
    )
    assert PASSWORD.encode("utf-8") not in bytes(
        account[2]
    )


def test_duplicate_account_provisioning_fails_closed(
    tmp_path,
):
    store = FormalAuthStore(
        tmp_path / "participant_auth.db"
    )
    store.provision_account(
        participant_id="P001",
        password=PASSWORD,
    )

    with pytest.raises(
        FormalAuthProvisioningError,
        match="already exists",
    ):
        store.provision_account(
            participant_id="P001",
            password=PASSWORD,
        )


def test_wrong_or_unknown_credentials_create_no_session(
    authenticated_app,
):
    gateway, inner, _auth = authenticated_app

    with TestClient(gateway) as client:
        wrong = _login(
            client,
            "P001",
            "WRONG-PASSWORD",
        )
        unknown = _login(
            client,
            "P999",
        )

    assert wrong.status_code == 401
    assert unknown.status_code == 401

    with inner.state.db.connect() as connection:
        count = connection.execute(
            select(func.count()).select_from(
                sessions
            )
        ).scalar_one()

    assert count == 0


def test_valid_login_creates_one_formal_session_and_assignment(
    authenticated_app,
):
    gateway, inner, _auth = authenticated_app

    with TestClient(gateway) as client:
        first = _login(client, "p001")
        second = _login(client, "P001")

    assert first.status_code == 200
    assert second.status_code == 200

    first_body = first.json()
    second_body = second.json()

    assert (
        first_body["session"]["participant_id"]
        == "P001"
    )
    assert (
        second_body["session"]["session_id"]
        == first_body["session"]["session_id"]
    )
    assert first_body["token_type"] == "bearer"
    assert first_body["access_token"]
    assert second_body["access_token"]

    with inner.state.db.connect() as connection:
        session_count = connection.execute(
            select(func.count()).select_from(
                sessions
            )
        ).scalar_one()
        assignment_count = connection.execute(
            select(func.count()).select_from(
                participant_episode_assignments
            )
        ).scalar_one()

    assert session_count == 1
    assert assignment_count == 1


def test_raw_bearer_token_is_not_stored(
    authenticated_app,
):
    gateway, _inner, auth = authenticated_app

    with TestClient(gateway) as client:
        response = _login(client, "P001")

    token = response.json()["access_token"]

    with sqlite3.connect(auth.path) as connection:
        row = connection.execute(
            """
            SELECT token_hash
            FROM participant_auth_tokens
            WHERE participant_id = 'P001'
            """
        ).fetchone()

    assert row is not None
    assert row[0] != token
    assert len(row[0]) == 64


def test_session_route_requires_bearer_token(
    authenticated_app,
):
    gateway, _inner, _auth = authenticated_app

    with TestClient(gateway) as client:
        login = _login(client, "P001")
        sid = login.json()["session"]["session_id"]

        no_auth = client.get(
            f"/session/{sid}"
        )
        invalid = client.get(
            f"/session/{sid}",
            headers=_auth_header(
                "not-a-valid-token"
            ),
        )

    assert no_auth.status_code == 401
    assert invalid.status_code == 401


def test_authenticated_participant_can_access_own_session(
    authenticated_app,
):
    gateway, _inner, _auth = authenticated_app

    with TestClient(gateway) as client:
        login = _login(client, "P001")
        body = login.json()

        response = client.get(
            f"/session/{body['session']['session_id']}",
            headers=_auth_header(
                body["access_token"]
            ),
        )

    assert response.status_code == 200
    assert (
        response.json()["participant_id"]
        == "P001"
    )


def test_cross_participant_session_access_is_forbidden(
    authenticated_app,
):
    gateway, _inner, _auth = authenticated_app

    with TestClient(gateway) as client:
        p1 = _login(client, "P001").json()
        p2 = _login(client, "P002").json()

        response = client.get(
            f"/session/{p2['session']['session_id']}",
            headers=_auth_header(
                p1["access_token"]
            ),
        )

    assert response.status_code == 403


def test_inherited_participant_bootstrap_is_hidden(
    authenticated_app,
):
    gateway, _inner, _auth = authenticated_app

    with TestClient(gateway) as client:
        login = _login(client, "P001").json()

        response = client.post(
            "/participant-session",
            headers=_auth_header(
                login["access_token"]
            ),
            json={
                "participant_id": "P001",
                "request_id": "bypass-attempt",
            },
        )

    assert response.status_code == 404


def test_legacy_non_session_surface_is_hidden(
    authenticated_app,
):
    gateway, _inner, _auth = authenticated_app

    with TestClient(gateway) as client:
        response = client.get("/market")

    assert response.status_code == 404


def test_auth_error_responses_receive_cors_headers(
    authenticated_app,
):
    gateway, _inner, _auth = authenticated_app

    with TestClient(gateway) as client:
        response = client.get(
            "/session/not-real",
            headers={
                "Origin": "http://localhost:5173",
            },
        )

    assert response.status_code == 401
    assert (
        response.headers[
            "access-control-allow-origin"
        ]
        == "http://localhost:5173"
    )


def test_completed_participant_relogin_resumes_same_session(
    authenticated_app,
):
    gateway, inner, _auth = authenticated_app

    with TestClient(gateway) as client:
        first = _login(
            client,
            "P001",
        )

        assert first.status_code == 200
        first_body = first.json()
        session_id = first_body["session"]["session_id"]

        with inner.state.db.connect() as connection:
            connection.execute(
                sessions.update()
                .where(
                    sessions.c.session_id
                    == session_id
                )
                .values(
                    current_step=14,
                    current_stage="COMPLETED",
                    experiment_status="completed",
                    completed=True,
                )
            )

        def fail_if_reinitialized(_session_id: str):
            raise AssertionError(
                "completed formal session must not be reinitialized"
            )

        original_initialize = (
            inner.state.participant_runtime
            .orchestration.initialize
        )
        inner.state.participant_runtime.orchestration.initialize = (
            fail_if_reinitialized
        )

        try:
            second = _login(
                client,
                "P001",
            )
        finally:
            inner.state.participant_runtime.orchestration.initialize = (
                original_initialize
            )

    assert second.status_code == 200

    second_body = second.json()
    assert (
        second_body["session"]["session_id"]
        == session_id
    )
    assert (
        second_body["session"]["participant_id"]
        == "P001"
    )
    assert (
        second_body["session"]["completed"]
        is True
    )
    assert (
        second_body["session"]["experiment_status"]
        == "completed"
    )

    orchestration_state = (
        inner.state.participant_runtime
        .orchestration.get(session_id)
    )
    assert (
        orchestration_state.current_stage
        == "COMPLETED"
    )
    assert orchestration_state.completed is True
