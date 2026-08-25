from __future__ import annotations

import pytest
from sqlalchemy import inspect, select

from marketlens.episode.contract import EPISODE_IDS, EPISODE_POOL_ID
from marketlens.human.services.episode_assignment_service import (
    ASSIGNMENT_BINDING_VERSION,
    FORMAL_ASSIGNMENT_METHOD,
    EpisodeAssignmentConflictError,
    EpisodeAssignmentService,
    EpisodeAssignmentValidationError,
)
from marketlens.human.services.session_service import SessionNotFoundError
from marketlens.human.stores.episode_assignment_store import EpisodeAssignmentStore
from marketlens.human.stores.session_store import SessionStore
from marketlens.persistence.database import Database
from marketlens.persistence.schema import participant_portfolios


def _create_session(store: SessionStore, *, session_id: str, participant_id: str) -> None:
    store.create_idempotent(
        session_id=session_id,
        participant_id=participant_id,
        request_id=f"request-{session_id}",
        created_at="2026-08-25T12:00:00+00:00",
        initial_cash=10000.0,
    )


def _service(tmp_path):
    db = Database(tmp_path / "human.db")
    return db, SessionStore(db), EpisodeAssignmentService(EpisodeAssignmentStore(db))


def test_assignment_table_is_part_of_human_domain_schema(tmp_path):
    db, _, _ = _service(tmp_path)
    try:
        assert "participant_episode_assignments" in inspect(db.engine).get_table_names()
    finally:
        db.dispose()


def test_binding_derives_participant_identity_from_session(tmp_path):
    db, sessions, service = _service(tmp_path)
    try:
        _create_session(sessions, session_id="S001", participant_id="P001")
        row = service.bind("S001", EPISODE_IDS[0])
        assert row.participant_id == "P001"
        assert row.episode_pool_id == EPISODE_POOL_ID
        assert row.episode_id == EPISODE_IDS[0]
        assert row.assignment_method == FORMAL_ASSIGNMENT_METHOD
        assert row.assignment_version == ASSIGNMENT_BINDING_VERSION
    finally:
        db.dispose()


def test_same_binding_is_idempotent(tmp_path):
    db, sessions, service = _service(tmp_path)
    try:
        _create_session(sessions, session_id="S001", participant_id="P001")
        first = service.bind("S001", EPISODE_IDS[0])
        second = service.bind("S001", EPISODE_IDS[0])
        assert second.assignment_id == first.assignment_id
        assert second.assigned_at == first.assigned_at
    finally:
        db.dispose()


def test_session_cannot_be_rebound_to_different_episode(tmp_path):
    db, sessions, service = _service(tmp_path)
    try:
        _create_session(sessions, session_id="S001", participant_id="P001")
        service.bind("S001", EPISODE_IDS[0])
        with pytest.raises(EpisodeAssignmentConflictError):
            service.bind("S001", EPISODE_IDS[1])
    finally:
        db.dispose()


def test_unknown_episode_is_rejected(tmp_path):
    db, sessions, service = _service(tmp_path)
    try:
        _create_session(sessions, session_id="S001", participant_id="P001")
        with pytest.raises(EpisodeAssignmentValidationError):
            service.bind("S001", "not-a-canonical-episode")
    finally:
        db.dispose()


def test_unknown_session_is_rejected(tmp_path):
    db, _, service = _service(tmp_path)
    try:
        with pytest.raises(SessionNotFoundError):
            service.bind("missing", EPISODE_IDS[0])
    finally:
        db.dispose()


def test_assignments_for_different_sessions_are_isolated(tmp_path):
    db, sessions, service = _service(tmp_path)
    try:
        _create_session(sessions, session_id="S001", participant_id="P001")
        _create_session(sessions, session_id="S002", participant_id="P002")
        one = service.bind("S001", EPISODE_IDS[0])
        two = service.bind("S002", EPISODE_IDS[1])
        assert one.participant_id == "P001"
        assert two.participant_id == "P002"
        assert service.get("S001") == one
        assert service.get("S002") == two
    finally:
        db.dispose()


def test_binding_does_not_mutate_session_progress_or_portfolio(tmp_path):
    db, sessions, service = _service(tmp_path)
    try:
        _create_session(sessions, session_id="S001", participant_id="P001")
        before_session = dict(sessions.get("S001"))
        with db.connect() as connection:
            before_portfolio = dict(
                connection.execute(
                    select(participant_portfolios).where(
                        participant_portfolios.c.session_id == "S001"
                    )
                ).mappings().one()
            )

        service.bind("S001", EPISODE_IDS[0])

        after_session = dict(sessions.get("S001"))
        with db.connect() as connection:
            after_portfolio = dict(
                connection.execute(
                    select(participant_portfolios).where(
                        participant_portfolios.c.session_id == "S001"
                    )
                ).mappings().one()
            )
        assert after_session == before_session
        assert after_portfolio == before_portfolio
    finally:
        db.dispose()
