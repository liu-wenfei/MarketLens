from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from marketlens.episode.contract import EPISODE_IDS
from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.schemas import PortfolioTransactionRead
from marketlens.human.routers.portfolio import get_portfolio_service
from marketlens.main import create_app
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.material import load_material


ROOT = Path(__file__).resolve().parents[3]
FORMAL_STIMULUS = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json"


class FakeProjection:
    def __init__(self, episode_id: str, marker: str):
        self.episode = SimpleNamespace(episode_id=episode_id)
        self.marker = marker

    def project(self, *, current_date: str):
        return {
            "current_date": current_date,
            "natural_news": [self.marker],
            "forum_posts": [],
        }


class FakePortfolioService:
    def __init__(self):
        self.rows: dict[tuple[str, str], PortfolioTransactionRead] = {}
        self.submit_calls = 0

    def submit(self, session_id, payload):
        key = (session_id, payload.request_id)
        existing = self.rows.get(key)
        if existing is not None:
            return existing
        self.submit_calls += 1
        row = PortfolioTransactionRead(
            transaction_id=f"tx-{payload.request_id}",
            session_id=session_id,
            request_id=payload.request_id,
            step=payload.step,
            stock_id=payload.stock_id,
            action=payload.action,
            requested_amount=payload.amount,
            requested_units=1.0,
            executed_units=1,
            executed_notional=100.0,
            settlement_price=100.0,
            price_date="2023-06-19",
            transaction_cost_bps=0.0,
            fee=0.0,
            cash_before=10000.0,
            cash_after=9900.0,
            holding_before=0,
            holding_after=1,
            portfolio_value_before=10000.0,
            portfolio_value_after=10000.0,
            weight_before=0.0,
            weight_after=0.01,
            submitted_at=datetime.now(timezone.utc),
        )
        self.rows[key] = row
        return row


def _runtime_app(tmp_path):
    episode_a, episode_b = EPISODE_IDS[:2]
    events = ParticipantEventStore(tmp_path / "participant_events.db")
    engine = StimulusEngine(load_material(FORMAL_STIMULUS, formal=True))
    app = create_app(
        tmp_path / "human.db",
        participant_runtime_enabled=True,
        participant_event_store=events,
        background_projections={
            episode_a: FakeProjection(episode_a, "episode-a-background"),
            episode_b: FakeProjection(episode_b, "episode-b-background"),
        },
        stimulus_engine=engine,
    )
    return app, events, episode_b


def _bind(client: TestClient, session_id: str, episode_id: str) -> None:
    client.app.state.participant_runtime.assignments.bind(
        session_id,
        episode_id,
        assignment_method="phase14b3c1-test-fixed",
        assignment_version="phase14b3c1-test-v1",
    )


def _judgement_payload(request_id: str):
    return {
        "request_id": request_id,
        "stock_id": "MEI",
        "action": "HOLD",
        "confidence": 70.0,
        "evidence_sources": ["background"],
        "rationale": "test",
    }


def test_runtime_session_initializes_protocol_state_and_blocks_legacy_bypasses(tmp_path) -> None:
    app, events, episode_id = _runtime_app(tmp_path)
    with TestClient(app) as client:
        created = client.post(
            "/session",
            json={"participant_id": "P001", "request_id": "session-create"},
        )
        assert created.status_code == 201
        session = created.json()
        assert session["current_step"] == 0
        assert session["current_date"] == "2023-06-19"

        _bind(client, session["session_id"], episode_id)

        assert client.get(f"/session/{session['session_id']}/background").status_code == 409
        assert client.post(
            f"/session/{session['session_id']}/decision",
            json={
                "request_id": "legacy-decision",
                "step": 0,
                "stock_id": "MEI",
                "action": "HOLD",
                "confidence": 50,
            },
        ).status_code == 409
        assert client.post(
            f"/session/{session['session_id']}/round/complete",
            json={"request_id": "legacy-round", "step": 0},
        ).status_code == 409
    events.dispose()


def test_runtime_uses_episode_assignment_for_background_and_forbids_client_provenance(tmp_path) -> None:
    app, events, episode_id = _runtime_app(tmp_path)
    with TestClient(app) as client:
        session = client.post(
            "/session",
            json={"participant_id": "P001", "request_id": "session-create"},
        ).json()
        _bind(client, session["session_id"], episode_id)

        rejected = client.post(
            f"/session/{session['session_id']}/exposure/background",
            json={"request_id": "bg-1", "episode_id": EPISODE_IDS[0]},
        )
        assert rejected.status_code == 422

        response = client.post(
            f"/session/{session['session_id']}/exposure/background",
            json={"request_id": "bg-1"},
        )
        assert response.status_code == 200
        assert response.json()["natural_news"] == ["episode-b-background"]

        rows = events.list_for_session(session["session_id"])
        assert len(rows) == 1
        assert rows[0]["episode_id"] == episode_id
        assert rows[0]["event_type"] == "BACKGROUND_EXPOSED"
    events.dispose()


def test_runtime_wires_judgement_stimulus_and_portfolio_events_with_retry(tmp_path) -> None:
    app, events, episode_id = _runtime_app(tmp_path)
    fake_portfolio = FakePortfolioService()
    app.dependency_overrides[get_portfolio_service] = lambda: fake_portfolio

    with TestClient(app) as client:
        session = client.post(
            "/session",
            json={"participant_id": "P001", "request_id": "session-create"},
        ).json()
        sid = session["session_id"]
        _bind(client, sid, episode_id)

        assert client.post(
            f"/session/{sid}/exposure/background",
            json={"request_id": "bg-1"},
        ).status_code == 200

        too_early = client.post(
            f"/session/{sid}/portfolio/order",
            json={
                "request_id": "order-too-early",
                "step": 0,
                "stock_id": "MEI",
                "action": "BUY",
                "amount": 100,
            },
        )
        assert too_early.status_code == 409
        assert fake_portfolio.submit_calls == 0

        forged = _judgement_payload("j0-forged")
        forged["judgement_event"] = "J4"
        assert client.post(f"/session/{sid}/judgement", json=forged).status_code == 422

        j0 = client.post(f"/session/{sid}/judgement", json=_judgement_payload("j0"))
        assert j0.status_code == 201
        assert j0.json()["judgement_event"] == "J0"
        count_after_j0 = len(events.list_for_session(sid))
        assert count_after_j0 == 3

        j0_retry = client.post(f"/session/{sid}/judgement", json=_judgement_payload("j0"))
        assert j0_retry.status_code == 201
        assert len(events.list_for_session(sid)) == count_after_j0

        stimulus = client.post(
            f"/session/{sid}/exposure/stimulus",
            json={"request_id": "misinfo-release"},
        )
        assert stimulus.status_code == 200
        assert stimulus.json()["kind"] == "misinformation"

        j1 = client.post(f"/session/{sid}/judgement", json=_judgement_payload("j1"))
        assert j1.status_code == 201
        assert j1.json()["judgement_event"] == "J1"

        order_payload = {
            "request_id": "order-1",
            "step": 0,
            "stock_id": "MEI",
            "action": "BUY",
            "amount": 100,
        }
        order = client.post(f"/session/{sid}/portfolio/order", json=order_payload)
        assert order.status_code == 201
        assert fake_portfolio.submit_calls == 1
        count_after_order = len(events.list_for_session(sid))
        assert count_after_order == 9

        retry = client.post(f"/session/{sid}/portfolio/order", json=order_payload)
        assert retry.status_code == 201
        assert fake_portfolio.submit_calls == 1
        assert len(events.list_for_session(sid)) == count_after_order

        event_types = [row["event_type"] for row in events.list_for_session(sid)]
        assert event_types.count("BACKGROUND_EXPOSED") == 1
        assert event_types.count("CONTROLLED_STIMULUS_EXPOSED") == 1
        assert event_types.count("JUDGEMENT_SUBMITTED") == 2
        assert event_types.count("CONFIDENCE_RECORDED") == 2
        assert event_types.count("ORDER_SUBMITTED") == 1
        assert event_types.count("TRADE_SETTLED") == 1
        assert event_types.count("PORTFOLIO_STATE_RECORDED") == 1

    events.dispose()


def test_default_app_keeps_legacy_runtime_disabled(tmp_path) -> None:
    with TestClient(create_app(tmp_path / "legacy.db")) as client:
        session = client.post(
            "/session",
            json={"participant_id": "P001", "request_id": "session-create"},
        )
        assert session.status_code == 201
        assert session.json()["current_date"] is None

        runtime_only = client.post(
            f"/session/{session.json()['session_id']}/exposure/background",
            json={"request_id": "bg"},
        )
        assert runtime_only.status_code == 503
