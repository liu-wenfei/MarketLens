from __future__ import annotations

import pytest

import marketlens.human.services.journey_service as journey_service_module
from marketlens.human.services.journey_service import (
    ParticipantJourneyConfigurationError,
    ParticipantJourneyService,
)


class _Sessions:
    def __init__(self) -> None:
        self.requested: list[str] = []

    def get(self, session_id: str):
        self.requested.append(session_id)
        return object()


class _Assignment:
    def __init__(self, episode_id: str) -> None:
        self.episode_id = episode_id


class _Assignments:
    def __init__(self, episode_by_session: dict[str, str]) -> None:
        self.episode_by_session = episode_by_session

    def get(self, session_id: str):
        episode_id = self.episode_by_session.get(session_id)
        if episode_id is None:
            return None
        return _Assignment(episode_id)


class _Adapter:
    created: list["_Adapter"] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.created.append(self)

    def build(self, session_id: str):
        return {
            "session_id": session_id,
            "price_provider": self.kwargs["price_provider"],
        }


def _service(*, episode_by_session, price_providers):
    return ParticipantJourneyService(
        sessions=_Sessions(),
        assignments=_Assignments(episode_by_session),
        judgements=object(),
        portfolios=object(),
        rounds=object(),
        price_providers=price_providers,
        calendar=object(),
        contract=object(),
        target_stock_id="TEST",
    )


def test_routes_session_to_its_assigned_episode_price_provider(monkeypatch):
    _Adapter.created.clear()
    monkeypatch.setattr(
        journey_service_module,
        "JourneyAuthoritativeSourceAdapter",
        _Adapter,
    )

    e01_provider = object()
    e02_provider = object()
    service = _service(
        episode_by_session={
            "session-e01": "episode-e01",
            "session-e02": "episode-e02",
        },
        price_providers={
            "episode-e01": e01_provider,
            "episode-e02": e02_provider,
        },
    )

    first = service.get("session-e01")
    second = service.get("session-e02")

    assert first["price_provider"] is e01_provider
    assert second["price_provider"] is e02_provider


def test_missing_assigned_episode_provider_fails_closed(monkeypatch):
    _Adapter.created.clear()
    monkeypatch.setattr(
        journey_service_module,
        "JourneyAuthoritativeSourceAdapter",
        _Adapter,
    )

    service = _service(
        episode_by_session={"session-e01": "episode-e01"},
        price_providers={"episode-e02": object()},
    )

    with pytest.raises(
        ParticipantJourneyConfigurationError,
        match="no canonical close-price provider is bound",
    ):
        service.get("session-e01")

    assert _Adapter.created == []


def test_empty_price_provider_binding_is_rejected():
    with pytest.raises(
        ParticipantJourneyConfigurationError,
        match="explicitly bound canonical episode price providers",
    ):
        _service(
            episode_by_session={"session-e01": "episode-e01"},
            price_providers={},
        )
