from __future__ import annotations

import json

import pytest

from marketlens.human.orchestration import (
    ExperimentOrchestrationContract,
    ParticipantStage,
)
from marketlens.human.services.feedback_delivery_service import (
    FINAL_FEEDBACK_KIND,
    MID_FEEDBACK_KIND,
    ParticipantFeedbackConflictError,
    ParticipantFeedbackDeliveryService,
    ParticipantFeedbackStateError,
    PreparedFeedbackArtifact,
)
from marketlens.human.services.orchestration_service import (
    ParticipantExperimentState,
)
from marketlens.human.stores.feedback_store import (
    FeedbackStore,
)
from marketlens.persistence.database import Database


class _FakeOrchestration:
    def __init__(self, step: int):
        self.contract = ExperimentOrchestrationContract()
        self.continue_calls = 0
        self._state = ParticipantExperimentState(
            session_id="session-feedback-test",
            participant_id="participant-feedback-test",
            experiment_step=step,
            agent_world_date=self.contract.checkpoint_date(
                step
            ),
            current_stage=(
                ParticipantStage.FEEDBACK_REQUIRED.value
            ),
            experiment_status="active",
            completed=False,
        )

    def get(self, session_id: str):
        assert session_id == self._state.session_id
        return self._state

    def continue_after_feedback(self, session_id: str):
        assert session_id == self._state.session_id
        assert (
            self._state.current_stage
            == ParticipantStage.FEEDBACK_REQUIRED.value
        )

        self.continue_calls += 1
        current = self._state
        next_checkpoint = self.contract.next_checkpoint(
            current.experiment_step
        )

        if next_checkpoint is None:
            self._state = ParticipantExperimentState(
                session_id=current.session_id,
                participant_id=current.participant_id,
                experiment_step=current.experiment_step,
                agent_world_date=current.agent_world_date,
                current_stage=(
                    ParticipantStage.DEBRIEF_REQUIRED.value
                ),
                experiment_status=current.experiment_status,
                completed=False,
            )
        else:
            next_step, next_date = next_checkpoint
            self._state = ParticipantExperimentState(
                session_id=current.session_id,
                participant_id=current.participant_id,
                experiment_step=next_step,
                agent_world_date=next_date,
                current_stage=(
                    ParticipantStage.BACKGROUND_REQUIRED.value
                ),
                experiment_status=current.experiment_status,
                completed=False,
            )

        return self._state


def _service(tmp_path, step: int):
    db = Database(tmp_path / f"feedback-{step}.db")
    orchestration = _FakeOrchestration(step)
    store = FeedbackStore(db)
    service = ParticipantFeedbackDeliveryService(
        store=store,
        orchestration=orchestration,
    )
    return db, orchestration, store, service


def _kind(step: int) -> str:
    if step == 14:
        return FINAL_FEEDBACK_KIND
    return MID_FEEDBACK_KIND


def _window(step: int) -> tuple[int, int]:
    if step == 3:
        return 1, 4
    if step == 10:
        return 5, 11
    if step == 14:
        return 1, 15
    raise AssertionError(step)


def _artifact(
    step: int,
    *,
    reflection: str = (
        "Your recorded judgement and trading behaviour "
        "showed a changing pattern across the available "
        "market information, while your own rationale "
        "captured some remaining uncertainty."
    ),
    output_kind: str | None = None,
) -> PreparedFeedbackArtifact:
    start, end = _window(step)
    kind = output_kind or _kind(step)

    statistics = {
        "statistics_version": (
            "marketlens-feedback-statistics-v1"
        ),
        "window": {
            "start_period": start,
            "end_period": end,
            "periods_reviewed": end - start + 1,
        },
        "judgement_metrics": {
            "revision_count": 1,
        },
    }

    context_pack = {
        "context_pack_version": (
            "marketlens-feedback-context-v1"
        ),
        "statistics": statistics,
        "participant_reflections": [],
    }

    validated_output = {
        "feedback_kind": kind,
        "reflection": reflection,
    }

    return PreparedFeedbackArtifact(
        participant_id="participant-feedback-test",
        statistics=statistics,
        context_pack=context_pack,
        prompt_version=(
            "marketlens-feedback-reflection-prompt-v1"
        ),
        prompt_text=(
            "Frozen zero-LLM test prompt fixture."
        ),
        generation_status="TEST_FIXTURE",
        generator_id="zero-llm-test-fixture",
        generation_metadata={
            "llm_called": False,
        },
        raw_output=json.dumps(
            validated_output,
            sort_keys=True,
        ),
        validated_output=validated_output,
        generated_at="2026-08-28T20:00:00+00:00",
    )


@pytest.mark.parametrize("step", [3, 10, 14])
def test_persist_once_is_idempotent_and_server_owned(
    tmp_path,
    step,
):
    db, orchestration, store, service = _service(
        tmp_path,
        step,
    )

    first = service.persist_once(
        "session-feedback-test",
        _artifact(step),
    )
    second = service.persist_once(
        "session-feedback-test",
        _artifact(step),
    )

    assert first == second
    assert first.feedback_kind == _kind(step)

    row = store.get_for_step(
        "session-feedback-test",
        step,
    )
    assert row is not None
    assert row["feedback_kind"] == _kind(step)
    assert row["window_end_period"] == step + 1
    assert row["shown_at"] is None
    assert row["continued_at"] is None

    with pytest.raises(
        ParticipantFeedbackConflictError
    ):
        service.persist_once(
            "session-feedback-test",
            _artifact(
                step,
                reflection="Different immutable reflection.",
            ),
        )

    assert orchestration.continue_calls == 0
    db.dispose()


@pytest.mark.parametrize("step", [3, 10, 14])
def test_refresh_returns_same_artifact_and_marks_shown_once(
    tmp_path,
    step,
):
    db, _, store, service = _service(
        tmp_path,
        step,
    )

    service.persist_once(
        "session-feedback-test",
        _artifact(step),
    )

    first = service.get_current(
        "session-feedback-test"
    )
    row_after_first = store.get_for_step(
        "session-feedback-test",
        step,
    )
    assert row_after_first is not None
    shown_at = row_after_first["shown_at"]
    assert shown_at is not None

    second = service.get_current(
        "session-feedback-test"
    )
    row_after_second = store.get_for_step(
        "session-feedback-test",
        step,
    )
    assert row_after_second is not None

    assert first == second
    assert row_after_second["shown_at"] == shown_at
    assert row_after_second["continued_at"] is None

    db.dispose()


def test_continue_requires_feedback_exposure(tmp_path):
    db, orchestration, _, service = _service(
        tmp_path,
        3,
    )

    service.persist_once(
        "session-feedback-test",
        _artifact(3),
    )

    with pytest.raises(
        ParticipantFeedbackStateError,
        match="exposed",
    ):
        service.continue_current(
            "session-feedback-test",
            "continue-before-view",
        )

    assert (
        orchestration.get(
            "session-feedback-test"
        ).current_stage
        == ParticipantStage.FEEDBACK_REQUIRED.value
    )
    assert orchestration.continue_calls == 0

    db.dispose()


@pytest.mark.parametrize(
    ("step", "expected_step", "expected_stage"),
    [
        (
            3,
            4,
            ParticipantStage.BACKGROUND_REQUIRED.value,
        ),
        (
            10,
            11,
            ParticipantStage.BACKGROUND_REQUIRED.value,
        ),
        (
            14,
            14,
            ParticipantStage.DEBRIEF_REQUIRED.value,
        ),
    ],
)
def test_continue_is_retry_safe_and_server_advances(
    tmp_path,
    step,
    expected_step,
    expected_stage,
):
    db, orchestration, store, service = _service(
        tmp_path,
        step,
    )

    service.persist_once(
        "session-feedback-test",
        _artifact(step),
    )
    service.get_current(
        "session-feedback-test"
    )

    assert service.continue_current(
        "session-feedback-test",
        "continue-001",
    )

    state = orchestration.get(
        "session-feedback-test"
    )
    assert state.experiment_step == expected_step
    assert state.current_stage == expected_stage
    assert orchestration.continue_calls == 1

    row = store.get_for_step(
        "session-feedback-test",
        step,
    )
    assert row is not None
    assert (
        row["continue_request_id"]
        == "continue-001"
    )
    assert row["continued_at"] is not None

    # Network retry after state advancement must not advance again.
    assert service.continue_current(
        "session-feedback-test",
        "continue-001",
    )
    assert orchestration.continue_calls == 1

    # A new request after the one-time transition is not valid.
    with pytest.raises(
        ParticipantFeedbackStateError
    ):
        service.continue_current(
            "session-feedback-test",
            "continue-002",
        )

    db.dispose()


def test_final_kind_is_derived_from_terminal_checkpoint(
    tmp_path,
):
    db, _, _, service = _service(
        tmp_path,
        14,
    )

    view = service.persist_once(
        "session-feedback-test",
        _artifact(14),
    )

    assert (
        view.feedback_kind
        == FINAL_FEEDBACK_KIND
    )

    db.dispose()


def test_client_cannot_override_feedback_kind(tmp_path):
    db, _, _, service = _service(
        tmp_path,
        3,
    )

    with pytest.raises(
        ParticipantFeedbackConflictError,
        match="kind",
    ):
        service.persist_once(
            "session-feedback-test",
            _artifact(
                3,
                output_kind=FINAL_FEEDBACK_KIND,
            ),
        )

    db.dispose()


def test_artifact_survives_database_restart(tmp_path):
    path = tmp_path / "feedback-restart.db"

    db1 = Database(path)
    orchestration1 = _FakeOrchestration(3)
    service1 = ParticipantFeedbackDeliveryService(
        store=FeedbackStore(db1),
        orchestration=orchestration1,
    )

    service1.persist_once(
        "session-feedback-test",
        _artifact(3),
    )
    first = service1.get_current(
        "session-feedback-test"
    )
    db1.dispose()

    db2 = Database(path)
    orchestration2 = _FakeOrchestration(3)
    service2 = ParticipantFeedbackDeliveryService(
        store=FeedbackStore(db2),
        orchestration=orchestration2,
    )

    second = service2.get_current(
        "session-feedback-test"
    )

    assert second == first
    db2.dispose()


def test_public_contract_has_no_generate_or_persist_route(
    client,
):
    paths = client.app.openapi()["paths"]

    assert (
        "/session/{session_id}/feedback/current"
        in paths
    )
    assert (
        "/session/{session_id}/feedback/current/continue"
        in paths
    )

    feedback_paths = {
        path
        for path in paths
        if "/feedback" in path
    }

    assert not any(
        "generate" in path.lower()
        or "persist" in path.lower()
        for path in feedback_paths
    )

    # Client is not permitted to send feedback_kind/F1/F2/Final.
    response = client.post(
        "/session/not-configured/feedback/current/continue",
        json={
            "request_id": "continue-public-contract",
            "feedback_kind": "FINAL",
        },
    )
    assert response.status_code == 422
