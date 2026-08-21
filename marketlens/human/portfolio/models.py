from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


# Engineering default only. This is NOT a frozen experimental parameter.
DEFAULT_DEV_INITIAL_CASH = 10_000.00


def round_currency(value: float) -> float:
    """Round currency only when a stored/account value is produced."""

    return round(float(value) + 0.0, 2)


@dataclass
class AccountState:
    """Participant cash plus whole-unit holdings.

    This is intentionally participant-only state. It has no link to the
    inherited TwinMarket Agent portfolio or matching engine.
    """

    cash: float
    positions: dict[str, int]

    @classmethod
    def empty(cls, initial_cash: float = DEFAULT_DEV_INITIAL_CASH) -> "AccountState":
        if initial_cash < 0:
            raise ValueError("initial_cash cannot be negative")
        return cls(cash=round_currency(initial_cash), positions={})

    def total_value(self, prices: Mapping[str, float]) -> float:
        invested = 0.0
        for stock_id, quantity in self.positions.items():
            if quantity < 0:
                raise ValueError("negative holdings are not supported")
            if stock_id not in prices:
                raise KeyError(f"Missing price for {stock_id}")
            invested += quantity * float(prices[stock_id])
        return round_currency(self.cash + invested)

    def weights(self, prices: Mapping[str, float]) -> dict[str, float]:
        total = self.total_value(prices)
        if total <= 0:
            return {stock_id: 0.0 for stock_id in self.positions}
        return {
            stock_id: (quantity * float(prices[stock_id])) / total
            for stock_id, quantity in self.positions.items()
        }

    def copy(self) -> "AccountState":
        return AccountState(cash=self.cash, positions=dict(self.positions))
