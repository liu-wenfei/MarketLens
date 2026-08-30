from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from marketlens.human.feedback.journey import (
    ParticipantDecisionJourney,
)
from marketlens.human.routers.journey import router
from marketlens.human.services.session_service import (
    SessionNotFoundError,
)


class _JourneyService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.requested = []

    def get(self, session_id: str):
        self.requested.append(session_id)

        if self.error is not None:
            raise self.error

        return self.result


def _client(journey_service=None) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    if journey_service is not None:
        app.state.participant_runtime = SimpleNamespace(
            journey=journey_service
        )

    return TestClient(app)


def test_journey_returns_503_without_participant_runtime():
    response = _client().get(
        "/session/session-1/journey"
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Participant runtime is not configured"
    }


def test_journey_returns_404_for_unknown_session():
    service = _JourneyService(
        error=SessionNotFoundError("missing")
    )

    response = _client(service).get(
        "/session/missing/journey"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Unknown session"
    }


def test_journey_returns_participant_safe_projection():
    journey = ParticipantDecisionJourney(
        journey_version=(
            "marketlens-participant-decision-journey-v1"
        ),
        target_stock_id="TEST",
        initial_cash=10000.0,
        initial_holdings={},
        initial_portfolio_value=10000.0,
        periods=(),
    )
    service = _JourneyService(result=journey)

    response = _client(service).get(
        "/session/session-1/journey"
    )

    assert response.status_code == 200
    assert response.json() == {
        "journey_version": (
            "marketlens-participant-decision-journey-v1"
        ),
        "target_stock_id": "TEST",
        "initial_cash": 10000.0,
        "initial_holdings": {},
        "initial_portfolio_value": 10000.0,
        "periods": [],
    }

    assert service.requested == ["session-1"]


from marketlens.human.feedback.journey import (
    ParticipantDecisionJourneyError,
)
from marketlens.human.feedback.journey_source import (
    JourneySourceError,
)
from marketlens.human.services.journey_service import (
    ParticipantJourneyConfigurationError,
    ParticipantJourneyUnavailableError,
)


def test_journey_returns_409_when_assignment_is_unavailable():
    service = _JourneyService(
        error=ParticipantJourneyUnavailableError(
            "participant session has no canonical episode assignment"
        )
    )

    response = _client(service).get(
        "/session/session-1/journey"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "participant session has no canonical episode assignment"
        )
    }


def test_journey_returns_409_for_configuration_error():
    service = _JourneyService(
        error=ParticipantJourneyConfigurationError(
            "canonical provider unavailable"
        )
    )

    response = _client(service).get(
        "/session/session-1/journey"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "canonical provider unavailable"
    }


def test_journey_returns_409_for_authoritative_source_error():
    service = _JourneyService(
        error=JourneySourceError(
            "authoritative Journey source is inconsistent"
        )
    )

    response = _client(service).get(
        "/session/session-1/journey"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "authoritative Journey source is inconsistent"
    }


def test_journey_returns_409_for_projection_error():
    service = _JourneyService(
        error=ParticipantDecisionJourneyError(
            "Journey inputs are inconsistent"
        )
    )

    response = _client(service).get(
        "/session/session-1/journey"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Journey inputs are inconsistent"
    }
