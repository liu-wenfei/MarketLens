from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from marketlens.episode.contract import EPISODE_IDS
from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.orchestration import ParticipantStage
from marketlens.human.schemas import RoundComplete
from marketlens.human.stores.judgement_store import JudgementStore
from marketlens.human.stores.round_store import RoundStore
from marketlens.main import create_app
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.material import load_material


ROOT = Path(__file__).resolve().parents[3]
FORMAL_STIMULUS = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json"


class Projection:
    def __init__(self, episode_id: str):
        self.episode = SimpleNamespace(episode_id=episode_id)

    def project(self, *, current_date: str):
        return {
            "current_date": current_date,
            "natural_news": [f"background-{current_date}"],
            "forum_posts": [],
        }


def _app(tmp_path):
    episode_id = EPISODE_IDS[0]
    events = ParticipantEventStore(tmp_path / "participant_events.db")
    app = create_app(
        tmp_path / "human.db",
        participant_runtime_enabled=True,
        participant_event_store=events,
        background_projections={episode_id: Projection(episode_id)},
        journey_price_providers={episode_id: object()},
        stimulus_engine=StimulusEngine(load_material(FORMAL_STIMULUS, formal=True)),
    )
    return app, events, episode_id


def _bind(client: TestClient, sid: str, episode_id: str) -> None:
    client.app.state.participant_runtime.assignments.bind(
        sid,
        episode_id,
        assignment_method="phase14b3c2-test-fixed",
        assignment_version="phase14b3c2-test-v1",
    )


def _judgement(request_id: str):
    return {
        "request_id": request_id,
        "stock_id": "MEI",
        "action": "HOLD",
        "confidence": 70.0,
        "evidence_sources": ["background"],
        "rationale": "phase14b3c2 test",
    }


def _make_round_active(client: TestClient, sid: str, step: int) -> None:
    bg = client.post(
        f"/session/{sid}/exposure/background",
        json={"request_id": f"bg-{step}"},
    )
    assert bg.status_code == 200
    if step == 0:
        assert client.post(f"/session/{sid}/judgement", json=_judgement("j0")).status_code == 201
        assert client.post(
            f"/session/{sid}/exposure/stimulus",
            json={"request_id": "misinformation"},
        ).status_code == 200
        assert client.post(f"/session/{sid}/judgement", json=_judgement("j1")).status_code == 201
    elif step == 7:
        assert client.post(f"/session/{sid}/judgement", json=_judgement("j2")).status_code == 201
        assert client.post(
            f"/session/{sid}/exposure/stimulus",
            json={"request_id": "correction"},
        ).status_code == 200
        assert client.post(f"/session/{sid}/judgement", json=_judgement("j3")).status_code == 201
    elif step == 14:
        assert client.post(f"/session/{sid}/judgement", json=_judgement("j4")).status_code == 201


def test_runtime_round_uses_protocol_date_and_replays_after_advance(tmp_path) -> None:
    app, events, episode_id = _app(tmp_path)
    with TestClient(app) as client:
        session = client.post(
            "/session",
            json={"participant_id": "P001", "request_id": "session"},
        ).json()
        sid = session["session_id"]
        _bind(client, sid, episode_id)
        _make_round_active(client, sid, 0)

        first = client.post(
            f"/session/{sid}/round/complete",
            json={"request_id": "round-0", "step": 0},
        )
        retry = client.post(
            f"/session/{sid}/round/complete",
            json={"request_id": "round-0", "step": 0},
        )
        assert first.status_code == retry.status_code == 201
        assert first.json()["completion_id"] == retry.json()["completion_id"]
        assert first.json()["next_step"] == 1

        state = app.state.participant_runtime.orchestration.get(sid)
        assert state.experiment_step == 1
        assert state.agent_world_date == app.state.participant_runtime.orchestration.contract.checkpoint_date(1)
        assert state.current_stage == ParticipantStage.BACKGROUND_REQUIRED.value
        assert len(RoundStore(app.state.db).list_for_session(sid)) == 1
    events.dispose()


def test_protocol_round_insert_and_session_advance_roll_back_together(tmp_path) -> None:
    app, events, episode_id = _app(tmp_path)
    with TestClient(app) as client:
        session = client.post(
            "/session",
            json={"participant_id": "P002", "request_id": "session"},
        ).json()
        sid = session["session_id"]
        _bind(client, sid, episode_id)
        _make_round_active(client, sid, 0)

        fired = {"value": False}

        def fail_update(_conn, _cursor, statement, _params, _context, _many):
            normalised = " ".join(statement.upper().split())
            if not fired["value"] and normalised.startswith("UPDATE SESSIONS SET"):
                fired["value"] = True
                raise RuntimeError("forced round update failure")

        event.listen(app.state.db.engine, "before_cursor_execute", fail_update)
        try:
            with pytest.raises(RuntimeError, match="forced round update failure"):
                app.state.participant_runtime.rounds.complete(
                    sid,
                    RoundComplete(request_id="round-fail", step=0),
                )
        finally:
            event.remove(app.state.db.engine, "before_cursor_execute", fail_update)

        state = app.state.participant_runtime.orchestration.get(sid)
        assert state.experiment_step == 0
        assert state.current_stage == ParticipantStage.ROUND_ACTIVE.value
        assert RoundStore(app.state.db).list_for_session(sid) == ()

        recovered = client.post(
            f"/session/{sid}/round/complete",
            json={"request_id": "round-fail", "step": 0},
        )
        assert recovered.status_code == 201
        assert app.state.participant_runtime.orchestration.get(sid).experiment_step == 1
    events.dispose()


def test_full_15_checkpoint_runtime_finishes_without_step_15(tmp_path) -> None:
    app, events, episode_id = _app(tmp_path)
    with TestClient(app) as client:
        session = client.post(
            "/session",
            json={"participant_id": "P003", "request_id": "session"},
        ).json()
        sid = session["session_id"]
        _bind(client, sid, episode_id)
        contract = app.state.participant_runtime.orchestration.contract

        for step in range(15):
            state = app.state.participant_runtime.orchestration.get(sid)
            assert state.experiment_step == step
            assert state.agent_world_date == contract.checkpoint_date(step)
            _make_round_active(client, sid, step)

            forged = client.post(
                f"/session/{sid}/round/complete",
                json={
                    "request_id": f"forged-{step}",
                    "step": step,
                    "current_stage": "COMPLETED",
                },
            )
            assert forged.status_code == 422

            first = client.post(
                f"/session/{sid}/round/complete",
                json={"request_id": f"round-{step}", "step": step},
            )
            retry = client.post(
                f"/session/{sid}/round/complete",
                json={"request_id": f"round-{step}", "step": step},
            )
            assert first.status_code == retry.status_code == 201
            assert first.json()["completion_id"] == retry.json()["completion_id"]
            if step < 14:
                assert first.json()["next_step"] == step + 1
            else:
                assert first.json()["next_step"] is None

            # Phase 15 feedback interstitial continuation.
            if step in {3, 10, 14}:
                orchestration = client.app.state.participant_runtime.orchestration
                feedback_state = orchestration.get(sid)
                assert feedback_state.experiment_step == step
                assert feedback_state.current_stage == "FEEDBACK_REQUIRED"

                feedback_response = client.get(f"/session/{sid}/view")
                assert feedback_response.status_code == 200
                feedback_view = feedback_response.json()
                assert feedback_view["required_action"] == "VIEW_FEEDBACK"
                assert not any(feedback_view["allowed_actions"].values())

                after_feedback = orchestration.continue_after_feedback(sid)

                if step < 14:
                    assert after_feedback.completed is False
                    assert after_feedback.experiment_step == step + 1
                    assert after_feedback.current_stage == "BACKGROUND_REQUIRED"
                else:
                    assert after_feedback.completed is False
                    assert after_feedback.experiment_step == 14
                    assert after_feedback.current_stage == "DEBRIEF_REQUIRED"

                    debrief_response = client.get(f"/session/{sid}/view")
                    assert debrief_response.status_code == 200
                    debrief_view = debrief_response.json()
                    assert debrief_view["required_action"] == "VIEW_DEBRIEF"
                    assert not any(debrief_view["allowed_actions"].values())

                    completed = orchestration.complete_after_debrief(sid)
                    assert completed.completed is True
                    assert completed.experiment_step == 14
                    assert completed.current_stage == "COMPLETED"

        final = app.state.participant_runtime.orchestration.get(sid)
        assert final.completed is True
        assert final.experiment_step == 14
        assert final.agent_world_date == "2023-07-11"
        assert final.current_stage == ParticipantStage.COMPLETED.value

        rounds = RoundStore(app.state.db).list_for_session(sid)
        assert len(rounds) == 15
        assert rounds[-1]["step"] == 14
        assert rounds[-1]["next_step"] is None

        judgements = JudgementStore(app.state.db).list_for_session(sid)
        assert {row["judgement_event"] for row in judgements} == {"J0", "J1", "J2", "J3", "J4"}
        by_event = {row["judgement_event"]: row for row in judgements}
        assert (by_event["J0"]["experiment_step"], by_event["J0"]["agent_world_date"]) == (
            by_event["J1"]["experiment_step"], by_event["J1"]["agent_world_date"]
        )
        assert (by_event["J2"]["experiment_step"], by_event["J2"]["agent_world_date"]) == (
            by_event["J3"]["experiment_step"], by_event["J3"]["agent_world_date"]
        )
        assert int(by_event["J4"]["experiment_step"]) > int(by_event["J3"]["experiment_step"])

        event_rows = events.list_for_session(sid)
        assert len(event_rows) == 27
        assert sum(row["event_type"] == "BACKGROUND_EXPOSED" for row in event_rows) == 15
        assert sum(row["event_type"] == "CONTROLLED_STIMULUS_EXPOSED" for row in event_rows) == 2
        assert sum(row["event_type"] == "JUDGEMENT_SUBMITTED" for row in event_rows) == 5
        assert sum(row["event_type"] == "CONFIDENCE_RECORDED" for row in event_rows) == 5
    events.dispose()
