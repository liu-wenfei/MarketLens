from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from marketlens.human.measurement import (
    DEFAULT_PARTICIPANT_EVENT_DB,
    ParticipantEvent,
    ParticipantEventIdempotencyConflict,
    ParticipantEventStore,
    ParticipantEventType,
    ParticipantEventValidationError,
    sha256_text,
)


def _event(**overrides) -> ParticipantEvent:
    values = {
        "event_id": "EVT-001",
        "request_id": "REQ-001",
        "session_id": "S001",
        "participant_id": "P001",
        "episode_id": "marketlens-canonical-episode-v1-e01",
        "experiment_step": 0,
        "agent_world_date": "2023-06-19",
        "event_type": ParticipantEventType.BACKGROUND_EXPOSED,
        "market_open": True,
        "participant_trading_enabled": True,
        "payload_digest": sha256_text("participant-visible-background"),
        "occurred_at_utc": "2026-08-25T13:00:00Z",
    }
    values.update(overrides)
    return ParticipantEvent(**values)


def test_default_path_is_separate_human_event_database() -> None:
    assert DEFAULT_PARTICIPANT_EVENT_DB == "data/marketlens/human/participant_events.db"
    assert "canonical_episode" not in DEFAULT_PARTICIPANT_EVENT_DB


def test_schema_contains_only_participant_events_table(tmp_path: Path) -> None:
    path = tmp_path / "participant_events.db"
    store = ParticipantEventStore(path)
    store.dispose()
    connection = sqlite3.connect(path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        connection.close()
    assert tables == {"participant_events"}


def test_all_participants_share_one_table_but_queries_are_isolated(tmp_path: Path) -> None:
    store = ParticipantEventStore(tmp_path / "participant_events.db")
    store.append_idempotent(_event())
    store.append_idempotent(
        _event(
            event_id="EVT-002",
            request_id="REQ-002",
            session_id="S002",
            participant_id="P002",
            episode_id="marketlens-canonical-episode-v1-e03",
        )
    )
    assert [row["participant_id"] for row in store.list_for_session("S001")] == ["P001"]
    assert [row["participant_id"] for row in store.list_for_session("S002")] == ["P002"]
    assert [row["session_id"] for row in store.list_for_participant("P001")] == ["S001"]
    store.dispose()


def test_append_is_idempotent_for_same_request_type_and_payload(tmp_path: Path) -> None:
    store = ParticipantEventStore(tmp_path / "participant_events.db")
    first = store.append_idempotent(_event())
    second = store.append_idempotent(_event())
    assert first["event_id"] == second["event_id"] == "EVT-001"
    assert len(store.list_for_session("S001")) == 1
    store.dispose()


def test_idempotency_conflict_rejects_changed_payload(tmp_path: Path) -> None:
    store = ParticipantEventStore(tmp_path / "participant_events.db")
    store.append_idempotent(_event())
    with pytest.raises(ParticipantEventIdempotencyConflict):
        store.append_idempotent(_event(episode_id="marketlens-canonical-episode-v1-e02"))
    store.dispose()


def test_same_request_can_record_distinct_event_types(tmp_path: Path) -> None:
    store = ParticipantEventStore(tmp_path / "participant_events.db")
    store.append_idempotent(_event())
    store.append_idempotent(
        _event(
            event_id="EVT-002",
            event_type=ParticipantEventType.JUDGEMENT_SUBMITTED,
            domain_record_id="DEC-001",
            payload_digest=None,
        )
    )
    assert [row["event_type"] for row in store.list_for_session("S001")] == [
        "BACKGROUND_EXPOSED",
        "JUDGEMENT_SUBMITTED",
    ]
    store.dispose()


def test_controlled_stimulus_requires_frozen_identity_fields(tmp_path: Path) -> None:
    store = ParticipantEventStore(tmp_path / "participant_events.db")
    with pytest.raises(ParticipantEventValidationError, match="requires stimulus"):
        store.append_idempotent(
            _event(event_type=ParticipantEventType.CONTROLLED_STIMULUS_EXPOSED)
        )
    stored = store.append_idempotent(
        _event(
            event_type=ParticipantEventType.CONTROLLED_STIMULUS_EXPOSED,
            stimulus_id="MISINFO_MEI_OWNERSHIP_001",
            stimulus_version="1.0",
            stimulus_sha256="7846c55c7b5ccbcb97ff28ec8d8c52a1b51336197805b7fec4aa4d3e226403b6",
            source_cue="Ordinary investor",
        )
    )
    assert stored["stimulus_id"] == "MISINFO_MEI_OWNERSHIP_001"
    store.dispose()


def test_non_stimulus_event_rejects_stimulus_identity_fields(tmp_path: Path) -> None:
    store = ParticipantEventStore(tmp_path / "participant_events.db")
    with pytest.raises(ParticipantEventValidationError, match="only valid"):
        store.append_idempotent(_event(stimulus_id="NOT-ALLOWED"))
    store.dispose()


def test_domain_events_reference_existing_domain_record_identity_only(tmp_path: Path) -> None:
    store = ParticipantEventStore(tmp_path / "participant_events.db")
    with pytest.raises(ParticipantEventValidationError, match="domain_record_id"):
        store.append_idempotent(
            _event(event_type=ParticipantEventType.TRADE_SETTLED, payload_digest=None)
        )
    row = store.append_idempotent(
        _event(
            event_type=ParticipantEventType.TRADE_SETTLED,
            domain_record_id="TX-001",
            payload_digest=None,
        )
    )
    assert row["domain_record_id"] == "TX-001"
    store.dispose()


def test_hash_fields_require_lowercase_sha256(tmp_path: Path) -> None:
    store = ParticipantEventStore(tmp_path / "participant_events.db")
    with pytest.raises(ParticipantEventValidationError, match="payload_digest"):
        store.append_idempotent(_event(payload_digest="abc"))
    store.dispose()


def test_sqlite_table_rejects_update_and_delete(tmp_path: Path) -> None:
    store = ParticipantEventStore(tmp_path / "participant_events.db")
    store.append_idempotent(_event())
    with pytest.raises(DatabaseError, match="append-only"):
        with store.db.connect() as connection:
            connection.execute(
                text("UPDATE participant_events SET participant_id='P999' WHERE event_id='EVT-001'")
            )
    with pytest.raises(DatabaseError, match="append-only"):
        with store.db.connect() as connection:
            connection.execute(text("DELETE FROM participant_events WHERE event_id='EVT-001'"))
    store.dispose()


def test_ledger_schema_does_not_duplicate_decision_trade_or_portfolio_payloads(tmp_path: Path) -> None:
    path = tmp_path / "participant_events.db"
    store = ParticipantEventStore(path)
    store.dispose()
    connection = sqlite3.connect(path)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(participant_events)")}
    finally:
        connection.close()
    forbidden_duplicate_source_fields = {
        "action",
        "confidence",
        "rationale",
        "cash",
        "holdings",
        "settlement_price",
        "executed_units",
    }
    assert not (columns & forbidden_duplicate_source_fields)
    assert "domain_record_id" in columns
