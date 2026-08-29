from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError

from marketlens.persistence.database import Database


RowMapping = Mapping[str, Any]


class StoreFeedbackError(RuntimeError):
    pass


class StoreFeedbackConflictError(StoreFeedbackError):
    pass


class StoreFeedbackNotFoundError(StoreFeedbackError):
    pass


feedback_metadata = MetaData()

participant_feedback = Table(
    "participant_feedback",
    feedback_metadata,
    Column("feedback_id", String, primary_key=True),
    Column("session_id", String, nullable=False),
    Column("participant_id", String, nullable=False),
    Column("experiment_step", Integer, nullable=False),
    Column("agent_world_date", String, nullable=False),
    Column("feedback_kind", String, nullable=False),
    Column("window_start_period", Integer, nullable=False),
    Column("window_end_period", Integer, nullable=False),
    Column("statistics_version", String, nullable=False),
    Column("statistics_sha256", String, nullable=False),
    Column("statistics_json", Text, nullable=False),
    Column("context_pack_version", String, nullable=False),
    Column("context_pack_sha256", String, nullable=False),
    Column("context_pack_json", Text, nullable=False),
    Column("prompt_version", String, nullable=False),
    Column("prompt_sha256", String, nullable=False),
    Column("generation_status", String, nullable=False),
    Column("generator_id", String, nullable=False),
    Column("generation_metadata_json", Text, nullable=False),
    Column("raw_output", Text, nullable=False),
    Column("validated_output_json", Text, nullable=False),
    Column("output_sha256", String, nullable=False),
    Column("generated_at", String, nullable=False),
    Column("shown_at", String, nullable=True),
    Column("continue_request_id", String, nullable=True),
    Column("continued_at", String, nullable=True),
    CheckConstraint(
        "experiment_step >= 0",
        name="ck_participant_feedback_step_nonnegative",
    ),
    CheckConstraint(
        "window_start_period >= 1",
        name="ck_participant_feedback_window_start_positive",
    ),
    CheckConstraint(
        "window_end_period >= window_start_period",
        name="ck_participant_feedback_window_order",
    ),
    UniqueConstraint(
        "session_id",
        "experiment_step",
        name="uq_participant_feedback_session_step",
    ),
    UniqueConstraint(
        "session_id",
        "continue_request_id",
        name="uq_participant_feedback_session_continue_request",
    ),
)


_IMMUTABLE_FIELDS = (
    "feedback_id",
    "session_id",
    "participant_id",
    "experiment_step",
    "agent_world_date",
    "feedback_kind",
    "window_start_period",
    "window_end_period",
    "statistics_version",
    "statistics_sha256",
    "statistics_json",
    "context_pack_version",
    "context_pack_sha256",
    "context_pack_json",
    "prompt_version",
    "prompt_sha256",
    "generation_status",
    "generator_id",
    "generation_metadata_json",
    "raw_output",
    "validated_output_json",
    "output_sha256",
    "generated_at",
)


class FeedbackStore:
    """Authoritative one-time participant feedback artifact store.

    The exact generated artifact is immutable. Only controlled exposure
    lifecycle fields may advance after creation:
      shown_at -> continue_request_id -> continued_at.
    """

    def __init__(self, db: Database):
        self.db = db
        feedback_metadata.create_all(self.db.engine)

    def get_for_step(
        self,
        session_id: str,
        experiment_step: int,
    ) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(participant_feedback).where(
                    participant_feedback.c.session_id == session_id,
                    participant_feedback.c.experiment_step
                    == int(experiment_step),
                )
            ).mappings().first()

    def get_by_continue_request(
        self,
        session_id: str,
        request_id: str,
    ) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(participant_feedback).where(
                    participant_feedback.c.session_id == session_id,
                    participant_feedback.c.continue_request_id == request_id,
                )
            ).mappings().first()

    @staticmethod
    def _require_same_immutable(
        existing: RowMapping,
        values: Mapping[str, Any],
    ) -> None:
        for field in _IMMUTABLE_FIELDS:
            if field not in values:
                raise StoreFeedbackConflictError(
                    f"missing immutable feedback field: {field}"
                )
            if existing[field] != values[field]:
                raise StoreFeedbackConflictError(
                    "feedback artifact already exists with different "
                    f"immutable field: {field}"
                )

    def create_once(self, **values: Any) -> RowMapping:
        existing = self.get_for_step(
            values["session_id"],
            int(values["experiment_step"]),
        )
        if existing is not None:
            self._require_same_immutable(existing, values)
            return existing

        try:
            with self.db.engine.begin() as connection:
                connection.execute(
                    insert(participant_feedback).values(**values)
                )
        except IntegrityError as exc:
            existing = self.get_for_step(
                values["session_id"],
                int(values["experiment_step"]),
            )
            if existing is not None:
                self._require_same_immutable(existing, values)
                return existing
            raise StoreFeedbackConflictError(
                "feedback artifact uniqueness conflict"
            ) from exc

        created = self.get_for_step(
            values["session_id"],
            int(values["experiment_step"]),
        )
        if created is None:
            raise StoreFeedbackError(
                "feedback artifact was not readable after insertion"
            )
        return created

    def mark_shown_once(
        self,
        *,
        session_id: str,
        experiment_step: int,
        shown_at: str,
    ) -> RowMapping:
        with self.db.engine.begin() as connection:
            connection.execute(
                update(participant_feedback)
                .where(
                    participant_feedback.c.session_id == session_id,
                    participant_feedback.c.experiment_step
                    == int(experiment_step),
                    participant_feedback.c.shown_at.is_(None),
                )
                .values(shown_at=shown_at)
            )
            row = connection.execute(
                select(participant_feedback).where(
                    participant_feedback.c.session_id == session_id,
                    participant_feedback.c.experiment_step
                    == int(experiment_step),
                )
            ).mappings().first()

        if row is None:
            raise StoreFeedbackNotFoundError(
                "feedback artifact does not exist"
            )
        return row

    def reserve_continue(
        self,
        *,
        session_id: str,
        experiment_step: int,
        request_id: str,
    ) -> RowMapping:
        existing = self.get_for_step(session_id, experiment_step)
        if existing is None:
            raise StoreFeedbackNotFoundError(
                "feedback artifact does not exist"
            )

        current_request = existing["continue_request_id"]
        if current_request is not None:
            if current_request != request_id:
                raise StoreFeedbackConflictError(
                    "feedback continuation already reserved by a "
                    "different request_id"
                )
            return existing

        try:
            with self.db.engine.begin() as connection:
                connection.execute(
                    update(participant_feedback)
                    .where(
                        participant_feedback.c.session_id == session_id,
                        participant_feedback.c.experiment_step
                        == int(experiment_step),
                        participant_feedback.c.continue_request_id.is_(None),
                    )
                    .values(continue_request_id=request_id)
                )
                row = connection.execute(
                    select(participant_feedback).where(
                        participant_feedback.c.session_id == session_id,
                        participant_feedback.c.experiment_step
                        == int(experiment_step),
                    )
                ).mappings().first()
        except IntegrityError as exc:
            raise StoreFeedbackConflictError(
                "feedback continuation request_id conflict"
            ) from exc

        if row is None:
            raise StoreFeedbackNotFoundError(
                "feedback artifact does not exist"
            )
        if row["continue_request_id"] != request_id:
            raise StoreFeedbackConflictError(
                "feedback continuation was reserved concurrently"
            )
        return row

    def mark_continued_once(
        self,
        *,
        session_id: str,
        experiment_step: int,
        request_id: str,
        continued_at: str,
    ) -> RowMapping:
        with self.db.engine.begin() as connection:
            connection.execute(
                update(participant_feedback)
                .where(
                    participant_feedback.c.session_id == session_id,
                    participant_feedback.c.experiment_step
                    == int(experiment_step),
                    participant_feedback.c.continue_request_id == request_id,
                    participant_feedback.c.continued_at.is_(None),
                )
                .values(continued_at=continued_at)
            )
            row = connection.execute(
                select(participant_feedback).where(
                    participant_feedback.c.session_id == session_id,
                    participant_feedback.c.experiment_step
                    == int(experiment_step),
                )
            ).mappings().first()

        if row is None:
            raise StoreFeedbackNotFoundError(
                "feedback artifact does not exist"
            )
        if row["continue_request_id"] != request_id:
            raise StoreFeedbackConflictError(
                "feedback continuation request_id does not match reservation"
            )
        return row
