from __future__ import annotations

import re
from types import SimpleNamespace

from marketlens.participant_server import (
    NONFORMAL_SMOKE_CONTEXT_LIMITS,
    create_nonformal_smoke_participant_app,
    nonformal_smoke_feedback_generator,
)


def _words(value: str) -> int:
    return len(value.split())


def test_nonformal_mid_smoke_is_reflection_only():
    payload = nonformal_smoke_feedback_generator(
        SimpleNamespace(
            feedback_kind=(
                "multi_period_decision_feedback"
            )
        )
    )

    assert set(payload) == {
        "feedback_kind",
        "reflection",
    }
    assert (
        payload["feedback_kind"]
        == "multi_period_decision_feedback"
    )
    reflection = str(payload["reflection"])
    assert 110 <= _words(reflection) <= 170
    assert re.search(r"\d", reflection) is None


def test_nonformal_final_smoke_is_reflection_only():
    payload = nonformal_smoke_feedback_generator(
        SimpleNamespace(
            feedback_kind=(
                "final_session_summary"
            )
        )
    )

    assert set(payload) == {
        "feedback_kind",
        "reflection",
    }
    assert (
        payload["feedback_kind"]
        == "final_session_summary"
    )
    reflection = str(payload["reflection"])
    assert 250 <= _words(reflection) <= 350
    assert re.search(r"\d", reflection) is None


def test_nonformal_context_policy_is_explicit():
    assert (
        NONFORMAL_SMOKE_CONTEXT_LIMITS
        .policy_version
        == "marketlens-nonformal-smoke-context-v1"
    )


def test_nonformal_smoke_composition_binds_preparer(
    tmp_path,
):
    app = create_nonformal_smoke_participant_app(
        db_path=tmp_path / "human.db",
        participant_event_db_path=(
            tmp_path / "participant_events.db"
        ),
    )

    runtime = app.state.participant_runtime

    assert runtime is not None
    assert (
        app.state.feedback_preparation_service
        is not None
    )
    assert (
        runtime.rounds.feedback_preparer
        is not None
    )


def test_immutable_mapping_generation_output_detaches_only_for_persistence():
    import json

    import pytest

    from marketlens.human.feedback.generation import (
        FeedbackGenerationResult,
    )
    from marketlens.human.services.feedback_preparation_service import (
        ParticipantFeedbackPreparationError,
        _raw_generation_output,
    )

    payload = {
        "feedback_kind": (
            "multi_period_decision_feedback"
        ),
        "reflection": (
            "Frozen fallback example."
        ),
    }

    result = FeedbackGenerationResult(
        output=payload,
        metadata={
            "fallback_used": True,
        },
    )

    assert (
        type(result.output).__name__
        == "mappingproxy"
    )

    encoded = _raw_generation_output(
        result.output
    )

    assert encoded == (
        '{"feedback_kind":'
        '"multi_period_decision_feedback",'
        '"reflection":'
        '"Frozen fallback example."}'
    )

    assert json.loads(encoded) == payload

    provider_text = (
        '{"feedback_kind":'
        '"multi_period_decision_feedback",'
        '"reflection":"Provider example."}'
    )

    assert (
        _raw_generation_output(
            provider_text
        )
        == provider_text
    )

    with pytest.raises(
        ParticipantFeedbackPreparationError,
        match="JSON text or a mapping",
    ):
        _raw_generation_output(
            object()
        )
