from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from marketlens.persistence.database import Database

from .models import ParticipantEvent, ParticipantEventType
from .schema import event_metadata, participant_events


RowMapping = Mapping[str, Any]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ParticipantEventStoreError(RuntimeError):
    pass


class ParticipantEventIdempotencyConflict(ParticipantEventStoreError):
    pass


class ParticipantEventValidationError(ParticipantEventStoreError):
    pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ParticipantEventStore:
    """Append-only participant experimental provenance ledger.

    This store records exposure/context. It is deliberately separate from the
    participant session/decision/portfolio source-of-truth stores and from all
    inherited Agent-world databases.
    """

    def __init__(self, target: str | Path | Database):
        if isinstance(target, Database):
            self.db = target
            self._owns_database = False
        else:
            self.db = Database(target, initialize=False)
            self._owns_database = True
        event_metadata.create_all(self.db.engine)
        self._install_sqlite_append_only_guards()

    def _install_sqlite_append_only_guards(self) -> None:
        if self.db.dialect_name != "sqlite":
            return
        with self.db.engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TRIGGER IF NOT EXISTS participant_events_no_update
                BEFORE UPDATE ON participant_events
                BEGIN
                    SELECT RAISE(ABORT, 'participant_events is append-only');
                END;
                """
            )
            connection.exec_driver_sql(
                """
                CREATE TRIGGER IF NOT EXISTS participant_events_no_delete
                BEFORE DELETE ON participant_events
                BEGIN
                    SELECT RAISE(ABORT, 'participant_events is append-only');
                END;
                """
            )

    @staticmethod
    def _validate(event_value: ParticipantEvent) -> None:
        required_text = {
            "event_id": event_value.event_id,
            "request_id": event_value.request_id,
            "session_id": event_value.session_id,
            "participant_id": event_value.participant_id,
            "episode_id": event_value.episode_id,
            "agent_world_date": event_value.agent_world_date,
            "occurred_at_utc": event_value.occurred_at_utc,
        }
        for field, value in required_text.items():
            if not isinstance(value, str) or not value.strip():
                raise ParticipantEventValidationError(f"{field} must be non-empty")
        if event_value.experiment_step < 0:
            raise ParticipantEventValidationError("experiment_step must be non-negative")
        if not _DATE_RE.fullmatch(event_value.agent_world_date):
            raise ParticipantEventValidationError(
                "agent_world_date must use YYYY-MM-DD"
            )
        if not isinstance(event_value.event_type, ParticipantEventType):
            raise ParticipantEventValidationError("event_type must be ParticipantEventType")

        for field, digest in (
            ("stimulus_sha256", event_value.stimulus_sha256),
            ("payload_digest", event_value.payload_digest),
        ):
            if digest is not None and not _SHA256_RE.fullmatch(digest):
                raise ParticipantEventValidationError(
                    f"{field} must be a lowercase SHA-256 hex digest"
                )

        is_stimulus = (
            event_value.event_type is ParticipantEventType.CONTROLLED_STIMULUS_EXPOSED
        )
        stimulus_fields = (
            event_value.stimulus_id,
            event_value.stimulus_version,
            event_value.stimulus_sha256,
        )
        if is_stimulus and not all(stimulus_fields):
            raise ParticipantEventValidationError(
                "controlled-stimulus exposure requires stimulus id/version/hash"
            )
        if not is_stimulus and any(stimulus_fields):
            raise ParticipantEventValidationError(
                "stimulus identity fields are only valid for controlled-stimulus exposure"
            )

        domain_record_events = {
            ParticipantEventType.JUDGEMENT_SUBMITTED,
            ParticipantEventType.CONFIDENCE_RECORDED,
            ParticipantEventType.ORDER_SUBMITTED,
            ParticipantEventType.TRADE_SETTLED,
            ParticipantEventType.PORTFOLIO_STATE_RECORDED,
        }
        if event_value.event_type in domain_record_events and not event_value.domain_record_id:
            raise ParticipantEventValidationError(
                f"{event_value.event_type.value} requires domain_record_id"
            )

    @staticmethod
    def _same_payload(existing: RowMapping, event_value: ParticipantEvent) -> bool:
        expected = {
            "event_id": event_value.event_id,
            "request_id": event_value.request_id,
            "session_id": event_value.session_id,
            "participant_id": event_value.participant_id,
            "episode_id": event_value.episode_id,
            "experiment_step": event_value.experiment_step,
            "agent_world_date": event_value.agent_world_date,
            "event_type": event_value.event_type.value,
            "domain_record_id": event_value.domain_record_id,
            "stimulus_id": event_value.stimulus_id,
            "stimulus_version": event_value.stimulus_version,
            "stimulus_sha256": event_value.stimulus_sha256,
            "source_cue": event_value.source_cue,
            "market_open": event_value.market_open,
            "participant_trading_enabled": event_value.participant_trading_enabled,
            "payload_digest": event_value.payload_digest,
            "occurred_at_utc": event_value.occurred_at_utc,
        }
        return all(existing[key] == value for key, value in expected.items())

    def append_idempotent(self, event_value: ParticipantEvent) -> RowMapping:
        self._validate(event_value)
        event_type = event_value.event_type.value

        with self.db.connect() as connection:
            existing = connection.execute(
                select(participant_events).where(
                    participant_events.c.session_id == event_value.session_id,
                    participant_events.c.request_id == event_value.request_id,
                    participant_events.c.event_type == event_type,
                )
            ).mappings().first()
            if existing is not None:
                if not self._same_payload(existing, event_value):
                    raise ParticipantEventIdempotencyConflict(
                        "request_id/event_type already exists with a different event payload"
                    )
                return existing

            try:
                connection.execute(
                    insert(participant_events).values(
                        event_id=event_value.event_id,
                        request_id=event_value.request_id,
                        session_id=event_value.session_id,
                        participant_id=event_value.participant_id,
                        episode_id=event_value.episode_id,
                        experiment_step=event_value.experiment_step,
                        agent_world_date=event_value.agent_world_date,
                        event_type=event_type,
                        domain_record_id=event_value.domain_record_id,
                        stimulus_id=event_value.stimulus_id,
                        stimulus_version=event_value.stimulus_version,
                        stimulus_sha256=event_value.stimulus_sha256,
                        source_cue=event_value.source_cue,
                        market_open=event_value.market_open,
                        participant_trading_enabled=event_value.participant_trading_enabled,
                        payload_digest=event_value.payload_digest,
                        occurred_at_utc=event_value.occurred_at_utc,
                    )
                )
            except IntegrityError as exc:
                raise ParticipantEventStoreError(str(exc)) from exc

            row = connection.execute(
                select(participant_events).where(
                    participant_events.c.event_id == event_value.event_id
                )
            ).mappings().first()
            assert row is not None
            return row

    def get_event(self, event_id: str) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(participant_events).where(participant_events.c.event_id == event_id)
            ).mappings().first()

    def list_for_session(self, session_id: str) -> tuple[RowMapping, ...]:
        with self.db.connect() as connection:
            rows = connection.execute(
                select(participant_events)
                .where(participant_events.c.session_id == session_id)
                .order_by(participant_events.c.occurred_at_utc, participant_events.c.event_id)
            ).mappings().all()
        return tuple(rows)

    def list_for_participant(self, participant_id: str) -> tuple[RowMapping, ...]:
        with self.db.connect() as connection:
            rows = connection.execute(
                select(participant_events)
                .where(participant_events.c.participant_id == participant_id)
                .order_by(participant_events.c.occurred_at_utc, participant_events.c.event_id)
            ).mappings().all()
        return tuple(rows)

    def dispose(self) -> None:
        if self._owns_database:
            self.db.dispose()
