from __future__ import annotations

from inspect import signature

import pytest

from marketlens.market.status import TradingCalendar, TradingCalendarCoverageError


def test_authoritative_calendar_matches_frozen_open_closed_examples():
    calendar = TradingCalendar()

    open_day = calendar.status("2023-06-19")
    assert open_day.market_open is True
    assert open_day.participant_trading_enabled is True
    assert open_day.market_status_reason == "scheduled_trading_day"
    assert open_day.market_state_date == "2023-06-19"
    assert open_day.next_trading_date is None

    weekend = calendar.status("2023-06-18")
    assert weekend.market_open is False
    assert weekend.participant_trading_enabled is False
    assert weekend.market_status_reason == "scheduled_non_trading_day"
    assert weekend.closure_start_date == "2023-06-17"
    assert weekend.closure_end_date == "2023-06-18"
    assert weekend.next_trading_date == "2023-06-19"
    assert weekend.market_state_date == "2023-06-16"

    multi_day = calendar.status("2023-06-22")
    assert multi_day.closure_start_date == "2023-06-22"
    assert multi_day.closure_end_date == "2023-06-25"
    assert multi_day.next_trading_date == "2023-06-26"
    assert multi_day.market_state_date == "2023-06-21"


def test_market_status_gate_has_no_agent_activity_inputs():
    parameters = set(signature(TradingCalendar.status).parameters)
    assert parameters == {"self", "current_date"}
    forbidden = {
        "active_agents",
        "agent_orders",
        "matched_trades",
        "top_users",
        "participant_orders",
    }
    assert parameters.isdisjoint(forbidden)


def test_market_status_uses_pretrade_date_not_is_open(tmp_path):
    path = tmp_path / "calendar.csv"
    path.write_text(
        "cal_date,is_open,pretrade_date\n"
        "2023-06-15,close,2023-06-14\n"
        "2023-06-16,close,2023-06-15\n"
        "2023-06-17,open,2023-06-16\n"
        "2023-06-18,open,2023-06-16\n"
        "2023-06-19,close,2023-06-16\n"
        "2023-06-20,close,2023-06-19\n",
        encoding="utf-8",
    )
    calendar = TradingCalendar(path)
    assert calendar.is_open("2023-06-15") is True
    assert calendar.is_open("2023-06-18") is False
    assert calendar.is_open("2023-06-19") is True


def test_out_of_coverage_date_fails_closed():
    calendar = TradingCalendar()
    with pytest.raises(TradingCalendarCoverageError):
        calendar.status("1900-01-01")
