from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path


_REQUIRED_COLUMNS = {"ts_code", "date", "close"}


class PriceSourceError(ValueError):
    """The inherited stock-data source is missing or malformed."""


class PriceNotFoundError(LookupError):
    pass


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
