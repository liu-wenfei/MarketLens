from __future__ import annotations

import pytest

from conftest import create_session
from marketlens.human.portfolio.models import DEFAULT_DEV_INITIAL_CASH
from marketlens.human.stores.portfolio_store import PortfolioStore


def test_new_session_gets_one_isolated_empty_participant_portfolio(client):
    session = create_session(client, participant_id="P001", request_id="portfolio-P001")
    store = PortfolioStore(client.app.state.db)

    row = store.get_portfolio(session["session_id"])
    account = store.get_account_state(session["session_id"])

    assert row is not None
    assert row["initial_cash"] == pytest.approx(DEFAULT_DEV_INITIAL_CASH)
    assert row["cash"] == pytest.approx(DEFAULT_DEV_INITIAL_CASH)
    assert account is not None
    assert account.cash == pytest.approx(DEFAULT_DEV_INITIAL_CASH)
    assert account.positions == {}


def test_two_sessions_have_distinct_portfolio_rows(client):
    first = create_session(client, participant_id="P001", request_id="portfolio-1")
    second = create_session(client, participant_id="P002", request_id="portfolio-2")
    store = PortfolioStore(client.app.state.db)

    first_row = store.get_portfolio(first["session_id"])
    second_row = store.get_portfolio(second["session_id"])

    assert first_row is not None
    assert second_row is not None
    assert first_row["session_id"] != second_row["session_id"]
    assert store.get_holdings(first["session_id"]) == ()
    assert store.get_holdings(second["session_id"]) == ()


def test_idempotent_session_replay_does_not_create_a_second_portfolio(client):
    first = create_session(client, participant_id="P001", request_id="same-portfolio-session")
    second = create_session(client, participant_id="P001", request_id="same-portfolio-session")

    assert second["session_id"] == first["session_id"]

    with client.app.state.db.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM participant_portfolios WHERE session_id = ?",
            (first["session_id"],),
        ).fetchone()["count"]

    assert count == 1
