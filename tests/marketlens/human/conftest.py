from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from marketlens.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "test_marketlens.db")
    with TestClient(app) as test_client:
        yield test_client


def create_session(client: TestClient, participant_id: str = "P001", request_id: str = "session-1"):
    response = client.post(
        "/session",
        json={"participant_id": participant_id, "request_id": request_id},
    )
    assert response.status_code == 201
    return response.json()
