from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

from .models import ParticipantEventType


event_metadata = MetaData()

_EVENT_TYPES_SQL = ", ".join(f"'{event_type.value}'" for event_type in ParticipantEventType)

participant_events = Table(
    "participant_events",
    event_metadata,
    Column("event_id", String, primary_key=True),
    Column("request_id", String, nullable=False),
    Column("session_id", String, nullable=False),
    Column("participant_id", String, nullable=False),
    Column("episode_id", String, nullable=False),
    Column("experiment_step", Integer, nullable=False),
    Column("agent_world_date", String, nullable=False),
    Column("event_type", String, nullable=False),
    Column("domain_record_id", String, nullable=True),
    Column("stimulus_id", String, nullable=True),
    Column("stimulus_version", String, nullable=True),
    Column("stimulus_sha256", String, nullable=True),
    Column("source_cue", String, nullable=True),
    Column("market_open", Boolean, nullable=False),
    Column("participant_trading_enabled", Boolean, nullable=False),
    Column("payload_digest", String, nullable=True),
    Column("occurred_at_utc", String, nullable=False),
    CheckConstraint(
        "experiment_step >= 0",
        name="ck_participant_events_experiment_step_nonnegative",
    ),
    CheckConstraint(
        f"event_type IN ({_EVENT_TYPES_SQL})",
        name="ck_participant_events_event_type",
    ),
    UniqueConstraint(
        "session_id",
        "request_id",
        "event_type",
        name="uq_participant_events_session_request_type",
    ),
)
