from __future__ import annotations

import sqlite3

import pytest

from marketlens.market.price_provider import (
    CanonicalStockDataClosePriceProvider,
    PriceNotFoundError,
)


def _history_db(tmp_path):
    path = tmp_path / "history.db"

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE StockData (
                stock_id TEXT NOT NULL,
                date TEXT NOT NULL,
                close_price REAL NOT NULL
            )
            """
        )

        connection.executemany(
            """
            INSERT INTO StockData (
                stock_id,
                date,
                close_price
            )
            VALUES (?, ?, ?)
            """,
            [
                ("MEI", "2023-01-03", 10.0),
                ("MEI", "2023-01-04", 10.1),
                ("MEI", "2023-01-05", 10.2),
                ("MEI", "2023-01-06", 10.3),
                ("TLEI", "2023-01-03", 11.0),
            ],
        )

        connection.commit()

    return path


def test_canonical_history_is_exact_bounded_and_ordered(
    tmp_path,
) -> None:
    provider = CanonicalStockDataClosePriceProvider(
        _history_db(tmp_path)
    )

    history = provider.get_close_history(
        "MEI",
        "2023-01-04",
        "2023-01-06",
    )

    assert [
        record.date.isoformat()
        for record in history
    ] == [
        "2023-01-04",
        "2023-01-05",
        "2023-01-06",
    ]

    assert [
        record.close
        for record in history
    ] == pytest.approx(
        [
            10.1,
            10.2,
            10.3,
        ]
    )


def test_canonical_history_does_not_nearest_date_fallback(
    tmp_path,
) -> None:
    provider = CanonicalStockDataClosePriceProvider(
        _history_db(tmp_path)
    )

    with pytest.raises(
        PriceNotFoundError
    ):
        provider.get_close_history(
            "MEI",
            "2022-12-01",
            "2022-12-31",
        )
