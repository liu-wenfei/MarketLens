"""Audit-only models for inherited TwinMarket market calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InheritedMarketCallResult:
    inherited_function: str
    current_date: str
    runtime_db: str
    runtime_db_sha256_before: str
    runtime_db_sha256_after: str
    runtime_db_changed: bool
    participant_data_used: bool = False
    custom_market_logic_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "inherited_function": self.inherited_function,
            "current_date": self.current_date,
            "runtime_db": self.runtime_db,
            "runtime_db_sha256_before": self.runtime_db_sha256_before,
            "runtime_db_sha256_after": self.runtime_db_sha256_after,
            "runtime_db_changed": self.runtime_db_changed,
            "participant_data_used": self.participant_data_used,
            "custom_market_logic_used": self.custom_market_logic_used,
        }
