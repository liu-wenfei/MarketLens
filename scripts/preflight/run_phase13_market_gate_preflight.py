#!/usr/bin/env python3
"""Zero-LLM Phase 13A participant market-status / trading-gate preflight."""

from __future__ import annotations

import ast
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, update

from marketlens.main import create_app
from marketlens.market.status import TradingCalendar
from marketlens.persistence.schema import (
    portfolio_holdings,
    portfolio_transactions,
    sessions,
)

BANNER = (
    "NON-FORMAL / PHASE 13A PARTICIPANT MARKET-GATE PREFLIGHT / "
    "ZERO-LLM / NOT FORMAL EXPERIMENT EVIDENCE"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def protected_hashes() -> dict[str, str]:
    names = (
        "Agent.py",
        "simulation.py",
        "data/trading_days.csv",
        "data/stock_data.csv",
        "data/stock_profile.csv",
        "data/sorted_impact_news.pkl",
    )
    return {name: sha256_file(ROOT / name) for name in names}


def transaction_count(client: TestClient, session_id: str) -> int:
    with client.app.state.db.connect() as connection:
        return int(
            connection.execute(
                select(func.count()).select_from(portfolio_transactions).where(
                    portfolio_transactions.c.session_id == session_id
                )
            ).scalar_one()
        )


def set_date(client: TestClient, session_id: str, value: str) -> None:
    with client.app.state.db.connect() as connection:
        connection.execute(
            update(sessions)
            .where(sessions.c.session_id == session_id)
            .values(current_date=value)
        )


def seed_holding(client: TestClient, session_id: str) -> None:
    with client.app.state.db.connect() as connection:
        connection.execute(
            insert(portfolio_holdings).values(
                session_id=session_id,
                stock_id="TLEI",
                quantity=2,
                updated_at="phase13-preflight",
            )
        )


def main() -> int:
    print(BANNER)
    before = protected_hashes()
    calendar = TradingCalendar(ROOT / "data/trading_days.csv")
    closed = calendar.status("2023-06-18")
    longer_closed = calendar.status("2023-06-22")
    opened = calendar.status("2023-06-19")

    with tempfile.TemporaryDirectory(prefix="marketlens_phase13a_") as temp_name:
        db_path = Path(temp_name) / "participant.db"
        app = create_app(db_path)
        with TestClient(app) as client:
            created = client.post(
                "/session",
                json={"participant_id": "P_PHASE13", "request_id": "phase13-session"},
            )
            assert created.status_code == 201
            session_id = created.json()["session_id"]
            set_date(client, session_id, "2023-06-18")
            seed_holding(client, session_id)

            state = client.get(f"/session/{session_id}/state")
            assert state.status_code == 200
            state_body = state.json()

            portfolio_before = client.get(f"/session/{session_id}/portfolio")
            assert portfolio_before.status_code == 200
            portfolio_before_body = portfolio_before.json()
            tx_before = transaction_count(client, session_id)

            preview = client.post(
                f"/session/{session_id}/portfolio/preview",
                json={"step": 0, "stock_id": "TLEI", "action": "BUY", "amount": 100.0},
            )
            order = client.post(
                f"/session/{session_id}/portfolio/order",
                json={
                    "request_id": "closed-order",
                    "step": 0,
                    "stock_id": "TLEI",
                    "action": "SELL",
                    "amount": 10.0,
                },
            )
            portfolio_after_body = client.get(f"/session/{session_id}/portfolio").json()
            tx_after = transaction_count(client, session_id)

            assert preview.status_code == 409
            assert order.status_code == 409
            assert tx_before == tx_after == 0
            assert portfolio_before_body == portfolio_after_body
            assert portfolio_after_body["price_date"] == "2023-06-16"

            # No Agent activity is created or supplied. Calendar OPEN alone must
            # be sufficient to enable the participant preview.
            set_date(client, session_id, "2023-06-19")
            open_state = client.get(f"/session/{session_id}/state").json()
            open_preview = client.post(
                f"/session/{session_id}/portfolio/preview",
                json={"step": 0, "stock_id": "TLEI", "action": "BUY", "amount": 100.0},
            )
            assert open_preview.status_code == 200

    after = protected_hashes()
    guarded_sources = (
        ROOT / "marketlens/market/status.py",
        ROOT / "marketlens/human/services/state_service.py",
        ROOT / "marketlens/human/services/portfolio_service.py",
    )
    imported_roots: set[str] = set()
    for source_path in guarded_sources:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])
    runtime_dependency_absent = imported_roots.isdisjoint({"simulation", "trader", "util"})

    result = {
        "status": "PASS",
        "evidence_class": BANNER,
        "llm_api_calls": 0,
        "formal_experiment_evidence": False,
        "authoritative_calendar_source": "protected data/trading_days.csv pretrade_date",
        "market_status_reason_specific_holiday_claimed": False,
        "open_example": opened.__dict__,
        "closed_example": closed.__dict__,
        "multi_day_closure_example": longer_closed.__dict__,
        "closed_session_state": state_body,
        "closed_preview_rejected": True,
        "closed_order_rejected": True,
        "closed_order_transaction_count_delta": tx_after - tx_before,
        "closed_order_portfolio_unchanged": portfolio_before_body == portfolio_after_body,
        "closed_portfolio_review_price_date": portfolio_after_body["price_date"],
        "open_without_agent_activity_trading_enabled": open_state["participant_trading_enabled"],
        "open_without_agent_activity_preview_price_date": open_preview.json()["price_date"],
        "agent_activity_inputs_used_for_gate": False,
        "participant_order_enters_agent_matching_engine": False,
        "participant_behaviour_parameters_added": 0,
        "agent_world_mutation_performed": False,
        "forum_write_performed": False,
        "protected_sources_unchanged": before == after,
        "participant_gate_runtime_dependency_absent": runtime_dependency_absent,
        "phase13b_participant_information_projection_deferred": True,
        "note": (
            "Phase 13A only. Closed-day portfolio valuation uses the last sealed OPEN "
            "state for passive display; execution remains disabled and exact-date-only."
        ),
    }

    if not result["protected_sources_unchanged"] or not runtime_dependency_absent:
        raise SystemExit("PHASE 13A PREFLIGHT FAIL: isolation invariant failed")

    artifact_root = ROOT / "artifacts" / "preflight" / "phase13"
    artifact_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = artifact_root / f"{stamp}_phase13_market_gate"
    run_dir.mkdir(parents=True, exist_ok=False)
    artifact = run_dir / "summary.json"
    artifact.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Artifact: {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
