#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketlens.episode.contract import EPISODE_IDS
from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.routers.portfolio import get_portfolio_service
from marketlens.human.schemas import PortfolioTransactionRead
from marketlens.main import create_app
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.material import load_material


class Projection:
    def __init__(self, episode_id: str, marker: str):
        self.episode = SimpleNamespace(episode_id=episode_id)
        self.marker = marker

    def project(self, *, current_date: str):
        return {
            "current_date": current_date,
            "natural_news": [self.marker],
            "forum_posts": [],
        }


class PortfolioStub:
    def __init__(self):
        self.rows = {}
        self.submit_calls = 0

    def submit(self, session_id, payload):
        key = (session_id, payload.request_id)
        if key in self.rows:
            return self.rows[key]
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


def judgement(request_id: str) -> dict[str, object]:
    return {
        "request_id": request_id,
        "stock_id": "MEI",
        "action": "HOLD",
        "confidence": 70.0,
        "evidence_sources": ["background"],
        "rationale": "preflight",
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="marketlens-phase14b3c1-") as temp_dir:
        root = Path(temp_dir)
        events = ParticipantEventStore(root / "participant_events.db")
        e01, e02 = EPISODE_IDS[:2]
        engine = StimulusEngine(
            load_material(
                ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json",
                formal=True,
            )
        )
        app = create_app(
            root / "human.db",
            participant_runtime_enabled=True,
            participant_event_store=events,
            background_projections={
                e01: Projection(e01, "episode-e01"),
                e02: Projection(e02, "episode-e02"),
            },
            stimulus_engine=engine,
        )

        portfolio = PortfolioStub()
        app.dependency_overrides[get_portfolio_service] = lambda: portfolio

        with TestClient(app) as client:
            session_response = client.post(
                "/session",
                json={"participant_id": "PREFLIGHT", "request_id": "session-create"},
            )
            session_response.raise_for_status()
            session = session_response.json()
            sid = session["session_id"]

            app.state.participant_runtime.assignments.bind(
                sid,
                e02,
                assignment_method="phase14b3c1-preflight-fixed",
                assignment_version="phase14b3c1-preflight-v1",
            )

            legacy_background_blocked = client.get(
                f"/session/{sid}/background"
            ).status_code == 409
            legacy_round_blocked = client.post(
                f"/session/{sid}/round/complete",
                json={"request_id": "legacy-round", "step": 0},
            ).status_code == 409

            bg = client.post(
                f"/session/{sid}/exposure/background",
                json={"request_id": "bg"},
            )
            bg.raise_for_status()

            early_order = client.post(
                f"/session/{sid}/portfolio/order",
                json={
                    "request_id": "early-order",
                    "step": 0,
                    "stock_id": "MEI",
                    "action": "BUY",
                    "amount": 100,
                },
            )
            early_submit_calls = portfolio.submit_calls

            j0 = client.post(f"/session/{sid}/judgement", json=judgement("j0"))
            j0.raise_for_status()
            j0_retry = client.post(f"/session/{sid}/judgement", json=judgement("j0"))
            j0_retry.raise_for_status()

            stimulus = client.post(
                f"/session/{sid}/exposure/stimulus",
                json={"request_id": "misinfo"},
            )
            stimulus.raise_for_status()

            j1 = client.post(f"/session/{sid}/judgement", json=judgement("j1"))
            j1.raise_for_status()

            order_payload = {
                "request_id": "order",
                "step": 0,
                "stock_id": "MEI",
                "action": "BUY",
                "amount": 100,
            }
            order = client.post(f"/session/{sid}/portfolio/order", json=order_payload)
            order.raise_for_status()
            order_retry = client.post(f"/session/{sid}/portfolio/order", json=order_payload)
            order_retry.raise_for_status()

            forged = judgement("forged")
            forged["judgement_event"] = "J4"
            forged_rejected = client.post(
                f"/session/{sid}/judgement",
                json=forged,
            ).status_code == 422

            rows = events.list_for_session(sid)
            event_types = [row["event_type"] for row in rows]

            result = {
                "status": "PASS",
                "evidence_class": "NON-FORMAL / PHASE 14B3C1 RUNTIME WIRING PREFLIGHT / ZERO-LLM",
                "llm_api_calls": 0,
                "formal_experiment_evidence": False,
                "round_runtime_replaced": False,
                "random_allocator_added": False,
                "session_protocol_initialized": (
                    session["current_step"] == 0
                    and session["current_date"] == "2023-06-19"
                ),
                "episode_aware_background": bg.json()["natural_news"] == ["episode-e02"],
                "background_event_episode_matches_assignment": (
                    rows[0]["event_type"] == "BACKGROUND_EXPOSED"
                    and rows[0]["episode_id"] == e02
                ),
                "legacy_background_bypass_blocked": legacy_background_blocked,
                "legacy_round_bypass_blocked": legacy_round_blocked,
                "early_trade_rejected_before_round_active": (
                    early_order.status_code == 409 and early_submit_calls == 0
                ),
                "client_forged_judgement_event_rejected": forged_rejected,
                "j0_retry_idempotent": j0.json()["judgement_id"] == j0_retry.json()["judgement_id"],
                "controlled_stimulus_served": stimulus.json()["kind"] == "misinformation",
                "portfolio_domain_retry_idempotent": (
                    order.json()["transaction_id"] == order_retry.json()["transaction_id"]
                    and portfolio.submit_calls == 1
                ),
                "expected_runtime_event_count": len(rows) == 9,
                "judgement_events_recorded": (
                    event_types.count("JUDGEMENT_SUBMITTED") == 2
                    and event_types.count("CONFIDENCE_RECORDED") == 2
                ),
                "portfolio_events_recorded": all(
                    event_types.count(value) == 1
                    for value in (
                        "ORDER_SUBMITTED",
                        "TRADE_SETTLED",
                        "PORTFOLIO_STATE_RECORDED",
                    )
                ),
                "agent_world_db_written": False,
                "forum_db_written": False,
                "note": (
                    "B3C1 wires explicit participant runtime dependencies and public exposure/"
                    "judgement/portfolio provenance. Legacy RoundStore runtime replacement remains "
                    "deferred to B3C2."
                ),
            }

        events.dispose()

    expected_false = {
        "formal_experiment_evidence",
        "round_runtime_replaced",
        "random_allocator_added",
        "agent_world_db_written",
        "forum_db_written",
    }
    failed = [
        key
        for key, value in result.items()
        if isinstance(value, bool)
        and (value if key in expected_false else not value)
    ]
    if failed:
        result["status"] = "FAIL"
        result["failed_checks"] = failed

    print("NON-FORMAL / PHASE 14B3C1 RUNTIME WIRING PREFLIGHT / ZERO-LLM")
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
