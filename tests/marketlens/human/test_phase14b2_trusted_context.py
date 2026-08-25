from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from marketlens.human.services.trusted_context_service import (
    TrustedParticipantContextInvariantError,
    TrustedParticipantContextResolver,
    TrustedParticipantContextUnavailableError,
)


EPISODE_POOL_ID = "marketlens-canonical-episode-pool-v1"
EPISODE_ID = "marketlens-canonical-episode-v1-e01"


def protocol(*, date: str = "2023-06-19", market_status: str = "OPEN") -> dict:
    # Minimal valid Phase 10 v1.1 protocol shape is deliberately not recreated
    # here. Resolver unit tests inject a protocol only after monkeypatching
    # validate_protocol so the tests remain focused on trusted-context wiring.
    return {
        "protocol_version": "1.1",
        "timeline": [
            {
                "experiment_step": 0,
                "agent_world_date": date,
                "market_status": market_status,
            }
        ],
    }


class FakeSessions:
    def __init__(self, *, participant_id="P001", step=0, date="2023-06-19"):
        self.row = SimpleNamespace(
            session_id="S001",
            participant_id=participant_id,
            current_step=step,
            current_date=date,
        )

    def get(self, session_id: str):
        assert session_id == "S001"
        return self.row


class FakeAssignments:
    def __init__(self, value=True, *, participant_id="P001", episode_id=EPISODE_ID):
        self.value = value
        self.participant_id = participant_id
        self.episode_id = episode_id

    def get(self, session_id: str):
        assert session_id == "S001"
        if not self.value:
            return None
        return SimpleNamespace(
            assignment_id="A001",
            session_id="S001",
            participant_id=self.participant_id,
            episode_pool_id=EPISODE_POOL_ID,
            episode_id=self.episode_id,
            assignment_method="balanced_random_across_episode_pool",
            assignment_version="phase14b1-v1",
        )


class FakeCalendar:
    def __init__(self, *, open_=True):
        self.open = open_

    def status(self, current_date: str):
        return SimpleNamespace(
            market_open=self.open,
            market_status_reason="open_trading_day" if self.open else "scheduled_market_holiday",
            current_market_date=current_date,
            market_state_date=current_date if self.open else "2023-06-16",
            participant_trading_enabled=self.open,
        )


def resolver(monkeypatch, *, sessions=None, assignments=None, calendar=None, injected_protocol=None):
    import marketlens.human.services.trusted_context_service as module

    monkeypatch.setattr(module, "validate_protocol", lambda value: value)
    return TrustedParticipantContextResolver(
        sessions=sessions or FakeSessions(),
        assignments=assignments or FakeAssignments(),
        calendar=calendar or FakeCalendar(),
        protocol=injected_protocol or protocol(),
    )


def test_context_is_derived_from_authoritative_backend_sources(monkeypatch):
    result = resolver(monkeypatch).resolve("S001")
    assert result.session_id == "S001"
    assert result.participant_id == "P001"
    assert result.episode_pool_id == EPISODE_POOL_ID
    assert result.episode_id == EPISODE_ID
    assert result.experiment_step == 0
    assert result.agent_world_date == "2023-06-19"
    assert result.market_open is True
    assert result.participant_trading_enabled is True


def test_context_object_is_immutable(monkeypatch):
    result = resolver(monkeypatch).resolve("S001")
    with pytest.raises(FrozenInstanceError):
        result.episode_id = "tamper"  # type: ignore[misc]


def test_missing_episode_assignment_fails_closed(monkeypatch):
    service = resolver(monkeypatch, assignments=FakeAssignments(False))
    with pytest.raises(TrustedParticipantContextUnavailableError, match="no canonical episode assignment"):
        service.resolve("S001")


def test_missing_session_date_fails_closed(monkeypatch):
    service = resolver(monkeypatch, sessions=FakeSessions(date=None))
    with pytest.raises(TrustedParticipantContextUnavailableError, match="no authoritative agent_world_date"):
        service.resolve("S001")


def test_non_checkpoint_session_step_fails_closed(monkeypatch):
    service = resolver(monkeypatch, sessions=FakeSessions(step=9))
    with pytest.raises(TrustedParticipantContextUnavailableError, match="not a participant checkpoint"):
        service.resolve("S001")


def test_session_date_must_match_frozen_protocol(monkeypatch):
    service = resolver(monkeypatch, sessions=FakeSessions(date="2023-06-20"))
    with pytest.raises(TrustedParticipantContextInvariantError, match="checkpoint date"):
        service.resolve("S001")


def test_assignment_participant_must_match_session(monkeypatch):
    service = resolver(monkeypatch, assignments=FakeAssignments(participant_id="P999"))
    with pytest.raises(TrustedParticipantContextInvariantError, match="participant_id"):
        service.resolve("S001")


def test_calendar_must_match_frozen_protocol_market_status(monkeypatch):
    service = resolver(monkeypatch, calendar=FakeCalendar(open_=False))
    with pytest.raises(TrustedParticipantContextInvariantError, match="trading calendar"):
        service.resolve("S001")
