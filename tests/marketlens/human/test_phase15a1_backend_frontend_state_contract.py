from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from marketlens.episode.contract import EPISODE_IDS
from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.orchestration import ParticipantStage
from marketlens.main import create_app
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.material import load_material


ROOT = Path(__file__).resolve().parents[3]
FORMAL_STIMULUS = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json"


class FakeProjection:
    def __init__(self, episode_id: str):
        self.episode = SimpleNamespace(episode_id=episode_id)

    def project(self, *, current_date: str):
        return {
            "current_date": current_date,
            "natural_news": [f"background-{current_date}"],
            "forum_posts": [],
        }


def _runtime_app(tmp_path):
    episode_id = EPISODE_IDS[0]
    events = ParticipantEventStore(tmp_path / "participant_events.db")
    engine = StimulusEngine(load_material(FORMAL_STIMULUS, formal=True))
    app = create_app(
        tmp_path / "human.db",
        participant_runtime_enabled=True,
        participant_event_store=events,
        background_projections={episode_id: FakeProjection(episode_id)},
        journey_price_providers={episode_id: object()},
        stimulus_engine=engine,
    )
    return app, events, episode_id


def _create_and_bind(client: TestClient, episode_id: str) -> str:
    created = client.post(
        "/session",
        json={"participant_id": "P001", "request_id": "session-create"},
    )
    assert created.status_code == 201
    sid = created.json()["session_id"]
    client.app.state.participant_runtime.assignments.bind(
        sid,
        episode_id,
        assignment_method="phase15a1-test-fixed",
        assignment_version="phase15a1-test-v1",
    )
    return sid


def _assessment(request_id: str) -> dict:
    return {
        "request_id": request_id,
        "action": "HOLD",
        "confidence": 70.0,
        "evidence_sources": ["market-information"],
        "rationale": "test",
    }


def test_view_requires_authoritative_episode_assignment(tmp_path) -> None:
    app, events, _episode_id = _runtime_app(tmp_path)
    with TestClient(app) as client:
        session = client.post(
            "/session",
            json={"participant_id": "P001", "request_id": "session-create"},
        ).json()
        response = client.get(f"/session/{session['session_id']}/view")
        assert response.status_code == 409
        assert "assignment" in response.json()["detail"]
    events.dispose()


def test_initial_view_is_neutral_and_trade_gate_is_server_derived(tmp_path) -> None:
    app, events, episode_id = _runtime_app(tmp_path)
    with TestClient(app) as client:
        sid = _create_and_bind(client, episode_id)
        response = client.get(f"/session/{sid}/view")
        assert response.status_code == 200
        body = response.json()

        assert body["contract_version"] == "1.0"
        assert body["current_step_assertion"] == 0
        assert body["period_number"] == 1
        assert body["period_count"] == 15
        assert body["current_date"] == "2023-06-19"
        assert body["assessment_target_stock_id"] == "MEI"
        assert body["required_action"] == "LOAD_MARKET_INFORMATION"
        assert body["assessment_mode"] is None
        assert "current_stage" not in body
        assert "judgement_event" not in body
        assert "episode_id" not in body

        assert body["market"]["market_open"] is True
        assert body["market"]["trading_enabled_by_market"] is True
        assert body["allowed_actions"] == {
            "load_market_information": True,
            "load_information_update": False,
            "submit_assessment": False,
            "view_portfolio": True,
            "preview_trade": False,
            "submit_trade": False,
            "complete_round": False,
        }
    events.dispose()


def test_safe_assessment_and_information_update_hide_internal_treatment_fields(tmp_path) -> None:
    app, events, episode_id = _runtime_app(tmp_path)
    with TestClient(app) as client:
        sid = _create_and_bind(client, episode_id)

        assert client.post(
            f"/session/{sid}/exposure/background",
            json={"request_id": "bg-0"},
        ).status_code == 200

        before = client.get(f"/session/{sid}/view").json()
        assert before["required_action"] == "SUBMIT_ASSESSMENT"
        assert before["assessment_mode"] == "PRE_UPDATE"
        assert before["allowed_actions"]["submit_assessment"] is True
        assert before["allowed_actions"]["submit_trade"] is False

        forged = _assessment("assessment-forged")
        forged["stock_id"] = "OTHER"
        forged["judgement_event"] = "J4"
        assert client.post(f"/session/{sid}/assessment", json=forged).status_code == 422

        assessment = client.post(
            f"/session/{sid}/assessment",
            json=_assessment("assessment-0"),
        )
        assert assessment.status_code == 201
        assessment_body = assessment.json()
        assert assessment_body["assessment_target_stock_id"] == "MEI"
        assert assessment_body["assessment_mode"] == "PRE_UPDATE"
        assert "judgement_event" not in assessment_body
        assert "agent_world_date" not in assessment_body
        assert "experiment_step" not in assessment_body

        update_view = client.get(f"/session/{sid}/view").json()
        assert update_view["required_action"] == "LOAD_INFORMATION_UPDATE"
        assert update_view["assessment_mode"] is None
        assert update_view["allowed_actions"]["load_information_update"] is True

        update = client.post(
            f"/session/{sid}/information-update",
            json={"request_id": "info-0"},
        )
        assert update.status_code == 200
        update_body = update.json()
        assert set(update_body) == {
            "session_id",
            "current_date",
            "headline",
            "body",
            "source_label",
            "source_descriptor",
        }
        assert "kind" not in update_body
        assert "stimulus_id" not in update_body
        assert "corrects_stimulus_id" not in update_body
        assert "content_sha256" not in update_body

        after = client.get(f"/session/{sid}/view").json()
        assert after["required_action"] == "SUBMIT_ASSESSMENT"
        assert after["assessment_mode"] == "POST_UPDATE"

        retry = client.post(
            f"/session/{sid}/information-update",
            json={"request_id": "info-0"},
        )
        assert retry.status_code == 200
        assert retry.json() == update_body
    events.dispose()


def test_hidden_legacy_judgement_is_target_hardened_and_phase15_routes_are_public_contract(tmp_path) -> None:
    app, events, episode_id = _runtime_app(tmp_path)
    with TestClient(app) as client:
        sid = _create_and_bind(client, episode_id)
        assert client.post(
            f"/session/{sid}/exposure/background",
            json={"request_id": "bg-0"},
        ).status_code == 200

        wrong_target = client.post(
            f"/session/{sid}/judgement",
            json={
                "request_id": "wrong-target",
                "stock_id": "OTHER",
                "action": "HOLD",
                "confidence": 50,
                "evidence_sources": [],
                "rationale": None,
            },
        )
        assert wrong_target.status_code == 409
        assert "server-owned assessment target" in wrong_target.json()["detail"]

        paths = client.get("/openapi.json").json()["paths"]
        assert f"/session/{{session_id}}/view" in paths
        assert f"/session/{{session_id}}/assessment" in paths
        assert f"/session/{{session_id}}/information-update" in paths
        assert f"/session/{{session_id}}/judgement" not in paths
        assert f"/session/{{session_id}}/exposure/stimulus" not in paths
    events.dispose()


def test_round_active_trade_permissions_and_completed_state_fail_closed(tmp_path) -> None:
    app, events, episode_id = _runtime_app(tmp_path)
    with TestClient(app) as client:
        sid = _create_and_bind(client, episode_id)

        for step in range(15):
            state = client.app.state.participant_runtime.orchestration.get(sid)
            assert state.experiment_step == step
            assert state.current_stage == ParticipantStage.BACKGROUND_REQUIRED.value

            assert client.post(
                f"/session/{sid}/exposure/background",
                json={"request_id": f"bg-{step}"},
            ).status_code == 200

            view = client.get(f"/session/{sid}/view").json()
            if view["required_action"] == "SUBMIT_ASSESSMENT":
                assert client.post(
                    f"/session/{sid}/assessment",
                    json=_assessment(f"assessment-a-{step}"),
                ).status_code == 201
                view = client.get(f"/session/{sid}/view").json()

            if view["required_action"] == "LOAD_INFORMATION_UPDATE":
                assert client.post(
                    f"/session/{sid}/information-update",
                    json={"request_id": f"info-{step}"},
                ).status_code == 200
                assert client.post(
                    f"/session/{sid}/assessment",
                    json=_assessment(f"assessment-b-{step}"),
                ).status_code == 201
                view = client.get(f"/session/{sid}/view").json()

            assert view["required_action"] == "ROUND_ACTIVE"
            assert view["allowed_actions"]["complete_round"] is True
            assert view["allowed_actions"]["preview_trade"] is True
            assert view["allowed_actions"]["submit_trade"] is True

            completed = client.post(
                f"/session/{sid}/round/complete",
                json={"request_id": f"round-{step}", "step": step},
            )
            assert completed.status_code == 201

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

        final = client.get(f"/session/{sid}/view")
        assert final.status_code == 200
        body = final.json()
        assert body["completed"] is True
        assert body["required_action"] == "COMPLETED"
        assert body["period_number"] == 15
        assert body["current_step_assertion"] == 14
        assert body["allowed_actions"]["load_market_information"] is False
        assert body["allowed_actions"]["load_information_update"] is False
        assert body["allowed_actions"]["submit_assessment"] is False
        assert body["allowed_actions"]["preview_trade"] is False
        assert body["allowed_actions"]["submit_trade"] is False
        assert body["allowed_actions"]["complete_round"] is False
    events.dispose()
