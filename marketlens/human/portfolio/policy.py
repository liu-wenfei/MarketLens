from __future__ import annotations

from dataclasses import dataclass


class PortfolioPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class PortfolioPolicy:
    """Participant-only execution policy for Phase 2B.

    The defaults are engineering defaults, not frozen experimental parameters.
    Phase 2B deliberately keeps the account long-only, unlevered, and whole-unit
    because the persisted Phase 2A account schema stores non-negative integer
    quantities.
    """

    transaction_cost_bps: float = 0.0
    max_position_weight: float | None = None
    whole_units: bool = True
    allow_short: bool = False
    allow_leverage: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.transaction_cost_bps) < 10_000.0:
            raise PortfolioPolicyError("transaction_cost_bps must be in [0, 10000)")
        if self.max_position_weight is not None and not 0.0 < float(self.max_position_weight) <= 1.0:
            raise PortfolioPolicyError("max_position_weight must be in (0, 1]")
        if not self.whole_units:
            raise PortfolioPolicyError("Phase 2B account persistence supports whole units only")
        if self.allow_short:
            raise PortfolioPolicyError("Phase 2B participant accounts do not support short selling")
        if self.allow_leverage:
            raise PortfolioPolicyError("Phase 2B participant accounts do not support leverage")

    @property
    def fee_rate(self) -> float:
        return float(self.transaction_cost_bps) / 10_000.0
