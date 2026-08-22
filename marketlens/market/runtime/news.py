"""Load TwinMarket market-calendar/news inputs without changing their content."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd


def _iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"current_date must be YYYY-MM-DD: {value!r}") from exc


def load_daily_news(news_pickle: str | Path, *, current_date: str) -> list[Any]:
    """Return the complete source list for one TwinMarket date, without reduction."""
    current_date = _iso_date(current_date)
    path = Path(news_pickle).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"TwinMarket news source not found: {path}")

    frame = pd.read_pickle(path)
    if "cal_date" not in frame.columns or "news" not in frame.columns:
        raise ValueError("TwinMarket news source must contain cal_date and news columns")

    cal = pd.to_datetime(frame["cal_date"]).dt.strftime("%Y-%m-%d")
    rows = frame.loc[cal == current_date]
    if rows.empty:
        raise ValueError(f"TwinMarket news source has no row for {current_date}")
    if len(rows) != 1:
        raise ValueError(
            f"TwinMarket news source must have exactly one row for {current_date}; "
            f"found {len(rows)}"
        )

    cell = rows.iloc[0]["news"]
    if isinstance(cell, list):
        return list(cell)
    if isinstance(cell, tuple):
        return list(cell)
    if isinstance(cell, str):
        return [cell] if cell.strip() else []
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return []
    return [cell]


def load_trading_day_set(calendar_csv: str | Path) -> frozenset[str]:
    """Read TwinMarket's inherited `pretrade_date` calendar column."""
    path = Path(calendar_csv).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"TwinMarket trading-day source not found: {path}")

    frame = pd.read_csv(path)
    if "pretrade_date" not in frame.columns:
        raise ValueError("TwinMarket trading-day source must contain pretrade_date")

    dates = pd.to_datetime(frame["pretrade_date"]).dt.strftime("%Y-%m-%d")
    return frozenset(dates.tolist())
