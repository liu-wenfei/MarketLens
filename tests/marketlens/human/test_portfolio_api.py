from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from conftest import create_session


def set_session_date(client, session_id: str, trading_date: str) -> None:
    with client.app.state.db.connect() as connection:
        connection.execute(
            "UPDATE sessions SET current_date = ? WHERE session_id = ?",
            (trading_date, session_id),
        )


def seed_holding(client, session_id: str, stock_id: str, quantity: int) -> None:
    with client.app.state.db.connect() as connection:
        connection.execute(
            """
            INSERT INTO portfolio_holdings (session_id, stock_id, quantity, updated_at)
            VALUES (?, ?, ?, 'test-seed')
            ON CONFLICT(session_id, stock_id)
            DO UPDATE SET quantity = excluded.quantity
            """,
            (session_id, stock_id, quantity),
        )


def transaction_count(client, session_id: str) -> int:
    with client.app.state.db.connect() as connection:
        return connection.execute(
            "SELECT COUNT(*) AS count FROM portfolio_transactions WHERE session_id = ?",
            (session_id,),
        ).fetchone()["count"]


def test_assets_endpoint_exposes_definitions_not_prices(client):
    response = client.get("/assets")
    assert response.status_code == 200
    assets = response.json()
    assert len(assets) == 10
    assert assets[0].keys() == {"stock_id", "market_weight", "name", "industry", "description"}


def test_empty_portfolio_can_be_read_before_market_date_is_set(client):
    session = create_session(client, request_id="portfolio-read-empty")
    response = client.get(f"/session/{session['session_id']}/portfolio")
    assert response.status_code == 200
    body = response.json()
    assert body["price_date"] is None
    assert body["cash"] == pytest.approx(10000.0)
    assert body["total_value"] == pytest.approx(10000.0)
    assert body["holdings"] == []


def test_preview_requires_session_authorised_current_date(client):
    session = create_session(client, request_id="preview-no-date")
    response = client.post(
        f"/session/{session['session_id']}/portfolio/preview",
        json={"step": 0, "stock_id": "TLEI", "action": "BUY", "amount": 100.0},
    )
    assert response.status_code == 409
    assert "current_date" in response.json()["detail"]


def test_client_cannot_supply_its_own_future_trading_date(client):
    session = create_session(client, request_id="preview-forbid-date")
    set_session_date(client, session["session_id"], "2023-06-15")
    response = client.post(
        f"/session/{session['session_id']}/portfolio/preview",
        json={
            "step": 0,
            "stock_id": "TLEI",
            "action": "BUY",
            "amount": 100.0,
            "trading_date": "2025-01-10",
        },
    )
    assert response.status_code == 422


def test_preview_uses_exact_session_date_and_has_no_side_effect(client):
    session = create_session(client, request_id="preview-exact")
    set_session_date(client, session["session_id"], "2023-06-15")
    sid = session["session_id"]

    response = client.post(
        f"/session/{sid}/portfolio/preview",
        json={"step": 0, "stock_id": "TLEI", "action": "BUY", "amount": 100.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["price_date"] == "2023-06-15"
    assert body["settlement_price"] == pytest.approx(11.34)
    assert body["valid"] is True
    assert body["executable_units"] == 8
    assert body["executed_notional"] == pytest.approx(90.72)
    assert transaction_count(client, sid) == 0

    portfolio = client.get(f"/session/{sid}/portfolio").json()
    assert portfolio["cash"] == pytest.approx(10000.0)
    assert portfolio["holdings"] == []


def test_confirmed_buy_persists_transaction_and_does_not_advance_round(client):
    session = create_session(client, request_id="buy-confirm")
    sid = session["session_id"]
    set_session_date(client, sid, "2023-06-15")

    response = client.post(
        f"/session/{sid}/portfolio/order",
        json={
            "request_id": "order-buy-1",
            "step": 0,
            "stock_id": "TLEI",
            "action": "BUY",
            "amount": 100.0,
        },
    )
    assert response.status_code == 201
    tx = response.json()
    assert tx["requested_amount"] == pytest.approx(100.0)
    assert tx["executed_units"] == 8
    assert tx["executed_notional"] == pytest.approx(90.72)

    state = client.get(f"/session/{sid}/state").json()
    assert state["current_step"] == 0
    portfolio = client.get(f"/session/{sid}/portfolio").json()
    assert portfolio["cash"] == pytest.approx(9909.28)
    assert portfolio["holdings"][0]["stock_id"] == "TLEI"
    assert portfolio["holdings"][0]["quantity"] == 8


def test_multiple_assets_can_be_traded_in_same_round_then_finish_round(client):
    session = create_session(client, request_id="multi-order")
    sid = session["session_id"]
    set_session_date(client, sid, "2023-06-15")

    for request_id, stock_id in (("multi-1", "TLEI"), ("multi-2", "FSEI")):
        response = client.post(
            f"/session/{sid}/portfolio/order",
            json={
                "request_id": request_id,
                "step": 0,
                "stock_id": stock_id,
                "action": "BUY",
                "amount": 100.0,
            },
        )
        assert response.status_code == 201
        assert client.get(f"/session/{sid}/state").json()["current_step"] == 0

    portfolio = client.get(f"/session/{sid}/portfolio").json()
    assert {item["stock_id"] for item in portfolio["holdings"]} == {"TLEI", "FSEI"}
    assert transaction_count(client, sid) == 2

    complete = client.post(
        f"/session/{sid}/round/complete",
        json={"request_id": "multi-finish", "step": 0},
    )
    assert complete.status_code == 201
    assert client.get(f"/session/{sid}/state").json()["current_step"] == 1


def test_sell_only_changes_selected_holding_and_returns_cash(client):
    session = create_session(client, request_id="sell-target-only")
    sid = session["session_id"]
    set_session_date(client, sid, "2023-06-15")
    seed_holding(client, sid, "TLEI", 10)
    seed_holding(client, sid, "FSEI", 5)

    before = client.get(f"/session/{sid}/portfolio").json()
    fsei_before = next(item for item in before["holdings"] if item["stock_id"] == "FSEI")["quantity"]

    response = client.post(
        f"/session/{sid}/portfolio/order",
        json={
            "request_id": "sell-1",
            "step": 0,
            "stock_id": "TLEI",
            "action": "SELL",
            "amount": 50.0,
        },
    )
    assert response.status_code == 201
    tx = response.json()
    assert tx["executed_units"] == 4
    assert tx["holding_after"] == 6
    assert tx["cash_after"] > tx["cash_before"]

    after = client.get(f"/session/{sid}/portfolio").json()
    fsei_after = next(item for item in after["holdings"] if item["stock_id"] == "FSEI")["quantity"]
    assert fsei_after == fsei_before


def test_invalid_overspend_creates_no_transaction_and_no_state_change(client):
    session = create_session(client, request_id="overspend")
    sid = session["session_id"]
    set_session_date(client, sid, "2023-06-15")

    preview = client.post(
        f"/session/{sid}/portfolio/preview",
        json={"step": 0, "stock_id": "TLEI", "action": "BUY", "amount": 10001.0},
    )
    assert preview.status_code == 200
    assert preview.json()["valid"] is False
    assert preview.json()["reason_code"] == "INSUFFICIENT_CASH"

    order = client.post(
        f"/session/{sid}/portfolio/order",
        json={
            "request_id": "overspend-order",
            "step": 0,
            "stock_id": "TLEI",
            "action": "BUY",
            "amount": 10001.0,
        },
    )
    assert order.status_code == 409
    assert transaction_count(client, sid) == 0
    portfolio = client.get(f"/session/{sid}/portfolio").json()
    assert portfolio["cash"] == pytest.approx(10000.0)
    assert portfolio["holdings"] == []


def test_invalid_oversell_creates_no_transaction(client):
    session = create_session(client, request_id="oversell")
    sid = session["session_id"]
    set_session_date(client, sid, "2023-06-15")
    seed_holding(client, sid, "TLEI", 2)

    response = client.post(
        f"/session/{sid}/portfolio/order",
        json={
            "request_id": "oversell-order",
            "step": 0,
            "stock_id": "TLEI",
            "action": "SELL",
            "amount": 30.0,
        },
    )
    assert response.status_code == 409
    assert transaction_count(client, sid) == 0


def test_same_order_request_id_is_idempotent(client):
    session = create_session(client, request_id="order-idem")
    sid = session["session_id"]
    set_session_date(client, sid, "2023-06-15")
    payload = {
        "request_id": "same-order",
        "step": 0,
        "stock_id": "TLEI",
        "action": "BUY",
        "amount": 100.0,
    }

    first = client.post(f"/session/{sid}/portfolio/order", json=payload)
    second = client.post(f"/session/{sid}/portfolio/order", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["transaction_id"] == first.json()["transaction_id"]
    assert transaction_count(client, sid) == 1
    assert client.get(f"/session/{sid}/portfolio").json()["holdings"][0]["quantity"] == 8


def test_reusing_order_request_id_for_different_payload_is_conflict(client):
    session = create_session(client, request_id="order-idem-conflict")
    sid = session["session_id"]
    set_session_date(client, sid, "2023-06-15")

    first = client.post(
        f"/session/{sid}/portfolio/order",
        json={
            "request_id": "same-id",
            "step": 0,
            "stock_id": "TLEI",
            "action": "BUY",
            "amount": 100.0,
        },
    )
    assert first.status_code == 201

    second = client.post(
        f"/session/{sid}/portfolio/order",
        json={
            "request_id": "same-id",
            "step": 0,
            "stock_id": "FSEI",
            "action": "BUY",
            "amount": 100.0,
        },
    )
    assert second.status_code == 409
    assert transaction_count(client, sid) == 1


def test_wrong_step_is_rejected(client):
    session = create_session(client, request_id="order-step")
    sid = session["session_id"]
    set_session_date(client, sid, "2023-06-15")
    response = client.post(
        f"/session/{sid}/portfolio/order",
        json={
            "request_id": "wrong-step",
            "step": 1,
            "stock_id": "TLEI",
            "action": "BUY",
            "amount": 100.0,
        },
    )
    assert response.status_code == 409
    assert transaction_count(client, sid) == 0


def test_unknown_asset_is_rejected(client):
    session = create_session(client, request_id="unknown-asset")
    sid = session["session_id"]
    set_session_date(client, sid, "2023-06-15")
    response = client.post(
        f"/session/{sid}/portfolio/preview",
        json={"step": 0, "stock_id": "NOPE", "action": "BUY", "amount": 100.0},
    )
    assert response.status_code == 404


def test_participant_portfolios_remain_isolated(client):
    first = create_session(client, participant_id="P001", request_id="iso-order-1")
    second = create_session(client, participant_id="P002", request_id="iso-order-2")
    set_session_date(client, first["session_id"], "2023-06-15")
    set_session_date(client, second["session_id"], "2023-06-15")

    response = client.post(
        f"/session/{first['session_id']}/portfolio/order",
        json={
            "request_id": "iso-buy",
            "step": 0,
            "stock_id": "TLEI",
            "action": "BUY",
            "amount": 100.0,
        },
    )
    assert response.status_code == 201

    second_portfolio = client.get(f"/session/{second['session_id']}/portfolio").json()
    assert second_portfolio["cash"] == pytest.approx(10000.0)
    assert second_portfolio["holdings"] == []


def test_source_market_csvs_are_not_modified_by_participant_order(client):
    profile_path = Path(client.app.state.asset_catalog.path)
    data_path = Path(client.app.state.price_provider.path)
    before = {
        profile_path: hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        data_path: hashlib.sha256(data_path.read_bytes()).hexdigest(),
    }

    session = create_session(client, request_id="source-immutable")
    sid = session["session_id"]
    set_session_date(client, sid, "2023-06-15")
    response = client.post(
        f"/session/{sid}/portfolio/order",
        json={
            "request_id": "source-buy",
            "step": 0,
            "stock_id": "TLEI",
            "action": "BUY",
            "amount": 100.0,
        },
    )
    assert response.status_code == 201

    assert hashlib.sha256(profile_path.read_bytes()).hexdigest() == before[profile_path]
    assert hashlib.sha256(data_path.read_bytes()).hexdigest() == before[data_path]
