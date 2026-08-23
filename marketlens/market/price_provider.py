from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import sqlite3
from typing import Protocol


_REQUIRED_COLUMNS = {"ts_code", "date", "close"}


class PriceSourceError(ValueError):
    """The inherited stock-data source is missing or malformed."""


class PriceNotFoundError(LookupError):
    pass


class ClosePriceProvider(Protocol):
    """Exact-date participant price interface.

    Formal Phase 10 execution must use the sealed canonical Agent-world source.
    The CSV adapter remains for earlier development/backend tests only.
    """

    def get_close(self, stock_id: str, trading_date: str | date) -> "MarketClose": ...


@dataclass(frozen=True)
class MarketClose:
    stock_id: str
    date: date
    close: float


def default_stock_data_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "stock_data.csv"


class CsvClosePriceProvider:
    """Exact-date close-price lookup over inherited stock_data.csv.

    This adapter deliberately does not decide which experiment date a
    participant is allowed to access. A later experiment-state layer must pass
    the already-authorised current date. There is no "latest price" or
    forward-looking fallback here.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_stock_data_path()
        self._prices = self._load()

    def _load(self) -> dict[tuple[str, date], MarketClose]:
        if not self.path.exists():
            raise PriceSourceError(f"Stock data not found: {self.path}")

        prices: dict[tuple[str, date], MarketClose] = {}
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = set(reader.fieldnames or [])
            missing = _REQUIRED_COLUMNS - columns
            if missing:
                raise PriceSourceError(
                    f"Stock data is missing required columns: {sorted(missing)}"
                )

            for line_number, row in enumerate(reader, start=2):
                stock_id = (row.get("ts_code") or "").strip()
                raw_date = (row.get("date") or "").strip()
                raw_close = (row.get("close") or "").strip()
                try:
                    trading_date = date.fromisoformat(raw_date)
                    close = float(raw_close)
                except ValueError as exc:
                    raise PriceSourceError(
                        f"Invalid date/close on line {line_number}"
                    ) from exc
                if not stock_id or close <= 0:
                    raise PriceSourceError(
                        f"Invalid stock_id/close on line {line_number}"
                    )

                key = (stock_id, trading_date)
                if key in prices:
                    raise PriceSourceError(
                        f"Duplicate close price for {stock_id} on {trading_date}"
                    )
                prices[key] = MarketClose(stock_id, trading_date, close)

        if not prices:
            raise PriceSourceError("Stock data contains no close prices")
        return prices

    def get_close(self, stock_id: str, trading_date: str | date) -> MarketClose:
        resolved_date = (
            date.fromisoformat(trading_date)
            if isinstance(trading_date, str)
            else trading_date
        )
        try:
            return self._prices[(stock_id, resolved_date)]
        except KeyError as exc:
            raise PriceNotFoundError(f"{stock_id} @ {resolved_date.isoformat()}") from exc


class CanonicalStockDataClosePriceProvider:
    """Read exact participant settlement prices from a sealed Agent-world DB.

    The database must be an immutable canonical episode/state store produced by
    inherited TwinMarket execution.  This adapter opens it read-only and reads
    only ``StockData.close_price`` for the exact ``stock_id`` and
    ``agent_world_date``.  It never falls back to CSV, nearest date, forward
    fill, frontend input, or the Agent matching engine.
    """

    def __init__(self, runtime_db: str | Path):
        self.runtime_db = Path(runtime_db).resolve()
        if not self.runtime_db.is_file():
            raise PriceSourceError(f"Canonical Agent-world database not found: {self.runtime_db}")
        self._validate_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"file:{self.runtime_db}?mode=ro", uri=True
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    def _validate_schema(self) -> None:
        try:
            with self._connect() as connection:
                columns = {
                    str(row[1]) for row in connection.execute("PRAGMA table_info(StockData)")
                }
        except sqlite3.Error as exc:
            raise PriceSourceError("Cannot inspect canonical StockData") from exc
        required = {"stock_id", "date", "close_price"}
        missing = required - columns
        if missing:
            raise PriceSourceError(
                f"Canonical StockData is missing required columns: {sorted(missing)}"
            )

    def get_close(self, stock_id: str, trading_date: str | date) -> MarketClose:
        resolved_date = (
            date.fromisoformat(trading_date)
            if isinstance(trading_date, str)
            else trading_date
        )
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT CAST(stock_id AS TEXT) AS stock_id,
                           CAST(date AS TEXT) AS date,
                           close_price
                    FROM StockData
                    WHERE CAST(stock_id AS TEXT) = ?
                      AND substr(CAST(date AS TEXT), 1, 10) = ?
                    """,
                    (str(stock_id), resolved_date.isoformat()),
                ).fetchall()
        except sqlite3.Error as exc:
            raise PriceSourceError("Cannot read canonical StockData") from exc

        if not rows:
            raise PriceNotFoundError(f"{stock_id} @ {resolved_date.isoformat()}")
        if len(rows) != 1:
            raise PriceSourceError(
                f"Canonical StockData contains duplicate exact-date rows for "
                f"{stock_id} @ {resolved_date.isoformat()}"
            )

        raw_close = rows[0]["close_price"]
        try:
            close = float(raw_close)
        except (TypeError, ValueError) as exc:
            raise PriceSourceError(
                f"Invalid canonical close_price for {stock_id} @ {resolved_date.isoformat()}"
            ) from exc
        if close <= 0:
            raise PriceSourceError(
                f"Invalid canonical close_price for {stock_id} @ {resolved_date.isoformat()}"
            )
        return MarketClose(str(stock_id), resolved_date, close)
