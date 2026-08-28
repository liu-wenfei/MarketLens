from __future__ import annotations

from marketlens.human.orchestration import (
    ExperimentOrchestrationContract,
    ParticipantStage,
)
from marketlens.human.schemas import ParticipantRequiredAction, RoundComplete
from marketlens.human.services.orchestration_service import ParticipantExperimentState
from marketlens.human.services.round_service import ParticipantProtocolRoundService
from marketlens.human.services.view_state_service import (
    VIEW_CONTRACT_VERSION,
    _required_action,
)


class _FakeRounds:
    def __init__(self):
        self.captured = None

    def get_by_request_id(self, session_id, request_id):
        return None

    def get_by_step(self, session_id, step):
        return None

    def complete_protocol_idempotent(self, **kwargs):
        self.captured = kwargs
        return {
            "completion_id": "completion-test",
            "session_id": kwargs["session_id"],
            "request_id": kwargs["request_id"],
            "step": kwargs["step"],
            "next_step": kwargs["next_step"],
            "completed_at": kwargs["completed_at"],
        }


class _FakeOrchestration:
    def __init__(self, contract, state):
        self.contract = contract
        self._state = state

    def get(self, session_id):
        assert session_id == self._state.session_id
        return self._state


def _state(contract, step):
    return ParticipantExperimentState(
        session_id="session-test",
        participant_id="participant-test",
        experiment_step=step,
        agent_world_date=contract.checkpoint_date(step),
        current_stage=ParticipantStage.ROUND_ACTIVE.value,
        experiment_status="active",
        completed=False,
    )


def test_feedback_checkpoint_policy_is_exactly_p4_p11_p15():
    contract = ExperimentOrchestrationContract()

    feedback_steps = {
        step
        for step in range(15)
        if contract.feedback_required_after_round(step)
    }

    assert feedback_steps == {3, 10, 14}


def test_round_completion_routes_feedback_checkpoints_to_interstitial_stage():
    contract = ExperimentOrchestrationContract()

    for step, expected_next_step in ((3, 4), (10, 11), (14, None)):
        rounds = _FakeRounds()
        service = ParticipantProtocolRoundService(
            rounds=rounds,
            orchestration=_FakeOrchestration(contract, _state(contract, step)),
            contract=contract,
        )

        result = service.complete(
            "session-test",
            RoundComplete(request_id=f"round-{step}", step=step),
        )

        assert result.next_step == expected_next_step
        assert rounds.captured is not None
        assert rounds.captured["interstitial_stage"] == ParticipantStage.FEEDBACK_REQUIRED.value


def test_non_feedback_round_still_advances_normally():
    contract = ExperimentOrchestrationContract()
    rounds = _FakeRounds()
    service = ParticipantProtocolRoundService(
        rounds=rounds,
        orchestration=_FakeOrchestration(contract, _state(contract, 2)),
        contract=contract,
    )

    result = service.complete(
        "session-test",
        RoundComplete(request_id="round-2", step=2),
    )

    assert result.next_step == 3
    assert rounds.captured is not None
    assert rounds.captured["interstitial_stage"] is None


def test_feedback_and_debrief_have_participant_safe_required_actions():
    assert VIEW_CONTRACT_VERSION == "1.0"
    assert _required_action(ParticipantStage.FEEDBACK_REQUIRED) is ParticipantRequiredAction.VIEW_FEEDBACK
    assert _required_action(ParticipantStage.DEBRIEF_REQUIRED) is ParticipantRequiredAction.VIEW_DEBRIEF
