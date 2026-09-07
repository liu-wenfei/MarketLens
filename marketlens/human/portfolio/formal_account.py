from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from marketlens.human.portfolio.policy import PortfolioPolicy


FORMAL_PARTICIPANT_ACCOUNT_CONFIG_PATH = (
    Path(__file__).resolve().parents[3]
    / "config"
    / "formal_participant_account_v1.json"
)


class FormalParticipantAccountError(RuntimeError):
    """Raised when formal participant-account configuration drifts."""


@dataclass(frozen=True)
class FormalParticipantAccountConfig:
    profile_id: str
    initial_cash: float
    initial_holdings: tuple[tuple[str, int], ...]
    transaction_cost_bps: float
    max_position_weight: float | None
    whole_units: bool
    allow_short: bool
    allow_leverage: bool

    def policy(self) -> PortfolioPolicy:
        return PortfolioPolicy(
            transaction_cost_bps=self.transaction_cost_bps,
            max_position_weight=self.max_position_weight,
            whole_units=self.whole_units,
            allow_short=self.allow_short,
            allow_leverage=self.allow_leverage,
        )


def _require_bool(raw: Mapping[str, Any], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise FormalParticipantAccountError(f"{key} must be boolean")
    return value


def load_formal_participant_account(
    path: Path = FORMAL_PARTICIPANT_ACCOUNT_CONFIG_PATH,
) -> FormalParticipantAccountConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))

    if raw.get("status") != "formal_frozen":
        raise FormalParticipantAccountError(
            "formal participant account manifest is not formal_frozen"
        )

    holdings_raw = raw.get("initial_holdings")
    if holdings_raw != {}:
        raise FormalParticipantAccountError(
            "formal participant account must start with no holdings"
        )

    initial_cash = float(raw["initial_cash"])
    if initial_cash != 10_000.0:
        raise FormalParticipantAccountError(
            "formal participant initial cash must be 10000.0"
        )

    fee = float(raw["transaction_cost_bps"])
    if fee != 0.0:
        raise FormalParticipantAccountError(
            "formal participant transaction cost must be 0 bps"
        )

    cap_raw = raw.get("max_position_weight")
    if cap_raw is not None:
        raise FormalParticipantAccountError(
            "formal participant account must not impose a position cap"
        )

    whole_units = _require_bool(raw, "whole_units")
    allow_short = _require_bool(raw, "allow_short")
    allow_leverage = _require_bool(raw, "allow_leverage")

    if not whole_units:
        raise FormalParticipantAccountError(
            "formal participant account requires whole-unit settlement"
        )
    if allow_short:
        raise FormalParticipantAccountError(
            "formal participant account does not allow short selling"
        )
    if allow_leverage:
        raise FormalParticipantAccountError(
            "formal participant account does not allow leverage"
        )

    return FormalParticipantAccountConfig(
        profile_id=str(raw["profile_id"]),
        initial_cash=initial_cash,
        initial_holdings=(),
        transaction_cost_bps=fee,
        max_position_weight=None,
        whole_units=whole_units,
        allow_short=allow_short,
        allow_leverage=allow_leverage,
    )


FORMAL_PARTICIPANT_ACCOUNT = load_formal_participant_account()


def assert_formal_participant_account_runtime(
    *,
    initial_cash: float,
    policy: PortfolioPolicy,
) -> None:
    """Fail fast if formal runtime account behaviour drifts from the freeze."""
    expected = FORMAL_PARTICIPANT_ACCOUNT

    actual = {
        "initial_cash": float(initial_cash),
        "transaction_cost_bps": float(policy.transaction_cost_bps),
        "max_position_weight": policy.max_position_weight,
        "whole_units": bool(policy.whole_units),
        "allow_short": bool(policy.allow_short),
        "allow_leverage": bool(policy.allow_leverage),
    }
    frozen = {
        "initial_cash": expected.initial_cash,
        "transaction_cost_bps": expected.transaction_cost_bps,
        "max_position_weight": expected.max_position_weight,
        "whole_units": expected.whole_units,
        "allow_short": expected.allow_short,
        "allow_leverage": expected.allow_leverage,
    }

    if actual != frozen:
        raise FormalParticipantAccountError(
            "formal participant account runtime drift: "
            f"expected={frozen!r}, actual={actual!r}"
        )
