"""Authoritative participant-facing market status from TwinMarket's calendar.

Phase 13 does not create an independent market calendar.  It reads the same
protected ``data/trading_days.csv`` source and the same inherited
``pretrade_date`` trading-day semantics already frozen in Phase 7/9.

This module is read-only.  It does not import or invoke Agent reasoning,
matching, market updates, or participant persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


class TradingCalendarError(ValueError):
    """Raised when the inherited trading calendar cannot satisfy the contract."""


class TradingCalendarCoverageError(TradingCalendarError):
    """Raised when a requested date is outside the authoritative coverage."""


@dataclass(frozen=True)
class ParticipantMarketStatus:
    market_open: bool
    market_status_reason: str
    current_market_date: str
    next_trading_date: str | None
    closure_start_date: str | None
    closure_end_date: str | None
    participant_trading_enabled: bool
    market_state_date: str


def default_trading_calendar_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "trading_days.csv"


class TradingCalendar:
    """Read-only adapter over TwinMarket's protected ``pretrade_date`` calendar.

    ``pretrade_date`` is intentionally used rather than creating a second
    interpretation from ``is_open``.  This matches the inherited simulation and
    the already-frozen Phase 9 market-availability contract.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_trading_calendar_path()
        self._trading_dates = self._load()
        self._trading_set = frozenset(item.isoformat() for item in self._trading_dates)
        self._minimum = self._trading_dates[0]
        self._maximum = self._trading_dates[-1]

    def _load(self) -> tuple[date, ...]:
        if not self.path.is_file():
            raise TradingCalendarError(f"TwinMarket trading calendar not found: {self.path}")

        frame = pd.read_csv(self.path)
        if "pretrade_date" not in frame.columns:
            raise TradingCalendarError(
                "TwinMarket trading calendar must contain pretrade_date"
            )
        try:
            values = pd.to_datetime(frame["pretrade_date"]).dt.strftime("%Y-%m-%d")
        except Exception as exc:  # pandas normalises the inherited source format
            raise TradingCalendarError("Invalid pretrade_date values") from exc

        resolved = tuple(sorted({date.fromisoformat(value) for value in values}))
        if not resolved:
            raise TradingCalendarError("TwinMarket trading calendar contains no trading dates")
        return resolved

    @property
    def trading_dates(self) -> tuple[str, ...]:
        return tuple(item.isoformat() for item in self._trading_dates)

    def is_open(self, current_date: str | date) -> bool:
        resolved = self._resolve_covered_date(current_date)
        return resolved.isoformat() in self._trading_set

    def status(self, current_date: str | date) -> ParticipantMarketStatus:
        resolved = self._resolve_covered_date(current_date)
        current_text = resolved.isoformat()

        if current_text in self._trading_set:
            return ParticipantMarketStatus(
                market_open=True,
                market_status_reason="scheduled_trading_day",
                current_market_date=current_text,
                next_trading_date=None,
                closure_start_date=None,
                closure_end_date=None,
                participant_trading_enabled=True,
                market_state_date=current_text,
            )

        previous_open = next(
            (item for item in reversed(self._trading_dates) if item < resolved),
            None,
        )
        next_open = next((item for item in self._trading_dates if item > resolved), None)
        if previous_open is None or next_open is None:
            raise TradingCalendarCoverageError(
                f"Cannot bracket closed date {current_text} with inherited trading dates"
            )

        closure_start = previous_open + timedelta(days=1)
        closure_end = next_open - timedelta(days=1)
        if not closure_start <= resolved <= closure_end:
            raise TradingCalendarError("Internal closure-range invariant failed")

        return ParticipantMarketStatus(
            market_open=False,
            # The source identifies a non-trading date but does not encode whether
            # the cause is weekend vs public holiday.  Do not invent that reason.
            market_status_reason="scheduled_non_trading_day",
            current_market_date=current_text,
            next_trading_date=next_open.isoformat(),
            closure_start_date=closure_start.isoformat(),
            closure_end_date=closure_end.isoformat(),
            participant_trading_enabled=False,
            # Passive portfolio review may use the last sealed OPEN state.  This
            # field is never an execution-price fallback.
            market_state_date=previous_open.isoformat(),
        )

    def _resolve_covered_date(self, value: str | date) -> date:
        try:
            resolved = date.fromisoformat(value) if isinstance(value, str) else value
        except ValueError as exc:
            raise TradingCalendarError(
                f"market date must be ISO YYYY-MM-DD, got {value!r}"
            ) from exc
        if not isinstance(resolved, date):
            raise TradingCalendarError(f"unsupported market date: {value!r}")
        if resolved < self._minimum or resolved > self._maximum:
            raise TradingCalendarCoverageError(
                f"market date {resolved.isoformat()} is outside inherited calendar coverage "
                f"{self._minimum.isoformat()}..{self._maximum.isoformat()}"
            )
        return resolved
