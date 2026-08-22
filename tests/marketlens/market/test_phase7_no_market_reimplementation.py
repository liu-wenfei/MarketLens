from __future__ import annotations

import inspect

from marketlens.market.runtime import inherited_market


def test_phase7_wrapper_contains_no_market_reimplementation():
    source = inspect.getsource(inherited_market)

    forbidden = [
        "import sqlite3",
        "INSERT INTO",
        "UPDATE StockData",
        "UPDATE Profiles",
        "DELETE FROM",
        "def calculate_closing_price",
        "def process_daily_orders",
        "def process_trading_day",
    ]

    for token in forbidden:
        assert token not in source


def test_phase7_wrapper_contains_no_participant_dependency():
    source = inspect.getsource(inherited_market).lower()

    forbidden = [
        "marketlens.human",
        "participant_repository",
        "participant_service",
        "participant_database",
    ]

    for token in forbidden:
        assert token not in source
