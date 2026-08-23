from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3

import pytest

from marketlens.market.price_provider import (
    CanonicalStockDataClosePriceProvider,
    PriceNotFoundError,
    PriceSourceError,
)


def _canonical_db(path: Path) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE StockData (
                stock_id TEXT NOT NULL,
                close_price REAL NOT NULL,
                date TEXT NOT NULL,
                PRIMARY KEY (stock_id, date)
            )
            """
        )
        connection.executemany(
            "INSERT INTO StockData(stock_id, close_price, date) VALUES (?, ?, ?)",
            [
                ("TLEI", 11.42, "2023-06-19"),
                ("TLEI", 11.55, "2023-06-20"),
                ("TTEI", 14.18, "2023-06-20 00:00:00"),
            ],
        )
    return path


def test_canonical_price_provider_reads_exact_stockdata_close_price(tmp_path):
    provider = CanonicalStockDataClosePriceProvider(_canonical_db(tmp_path / "canonical.db"))
    close = provider.get_close("TLEI", date(2023, 6, 20))
    assert close.stock_id == "TLEI"
    assert close.date == date(2023, 6, 20)
    assert close.close == pytest.approx(11.55)


def test_canonical_price_provider_accepts_inherited_midnight_date_format(tmp_path):
    provider = CanonicalStockDataClosePriceProvider(_canonical_db(tmp_path / "canonical.db"))
    assert provider.get_close("TTEI", "2023-06-20").close == pytest.approx(14.18)


def test_canonical_price_provider_fails_closed_without_exact_date(tmp_path):
    provider = CanonicalStockDataClosePriceProvider(_canonical_db(tmp_path / "canonical.db"))
    with pytest.raises(PriceNotFoundError):
        provider.get_close("TLEI", "2023-06-21")


def test_canonical_price_provider_requires_stockdata_schema(tmp_path):
    path = tmp_path / "bad.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE Other(value TEXT)")
    with pytest.raises(PriceSourceError):
        CanonicalStockDataClosePriceProvider(path)
