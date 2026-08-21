from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import floor, isfinite
from typing import Mapping

from marketlens.human.portfolio.models import AccountState, round_currency
from marketlens.human.portfolio.policy import PortfolioPolicy


class PortfolioAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class PreviewReason(str, Enum):
    OK = "OK"
    BELOW_ONE_UNIT = "BELOW_ONE_UNIT"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    INSUFFICIENT_HOLDINGS = "INSUFFICIENT_HOLDINGS"
    POSITION_LIMIT = "POSITION_LIMIT"


@dataclass(frozen=True)
class OrderPreview:
    stock_id: str
    action: PortfolioAction
    requested_amount: float
    requested_units: float
    executable_units: int
    executed_notional: float
    fee: float
    cash_before: float
    cash_after: float
    holding_before: int
    holding_after: int
    portfolio_value_before: float
    portfolio_value_after: float
    weight_before: float
    weight_after: float
    valid: bool
    reason_code: PreviewReason
    maximum_valid_amount: float | None


def _asset_weight(account: AccountState, prices: Mapping[str, float], stock_id: str) -> float:
    total = account.total_value(prices)
    if total <= 0:
        return 0.0
    quantity = int(account.positions.get(stock_id, 0))
    return (quantity * float(prices[stock_id])) / total


def _max_buy_capacity(
    *,
    account: AccountState,
    stock_id: str,
    price: float,
    prices: Mapping[str, float],
    policy: PortfolioPolicy,
) -> tuple[int, float, bool]:
    fee_rate = policy.fee_rate
    cash_max_amount = float(account.cash) / (1.0 + fee_rate)
    max_amount = cash_max_amount
    cap_is_binding = False

    if policy.max_position_weight is not None:
        cap = float(policy.max_position_weight)
        total_before = account.total_value(prices)
        current_asset_value = int(account.positions.get(stock_id, 0)) * price
        numerator = cap * total_before - current_asset_value
        cap_max_amount = 0.0 if numerator <= 0 else numerator / (1.0 + cap * fee_rate)
        if cap_max_amount < max_amount:
            max_amount = cap_max_amount
            cap_is_binding = True

    max_amount = max(max_amount, 0.0)
    max_units = max(floor(max_amount / price), 0)
    return max_units, max_amount, cap_is_binding


def preview_order(
    *,
    account: AccountState,
    stock_id: str,
    action: PortfolioAction,
    requested_amount: float,
    price: float,
    prices: Mapping[str, float],
    policy: PortfolioPolicy,
) -> OrderPreview:
    """Pure, side-effect-free participant order preview.

    ``requested_amount`` is gross asset notional. Any configured transaction fee
    is charged in addition for BUY and deducted from proceeds for SELL.
    """

    amount = float(requested_amount)
    price = float(price)
    if not isfinite(amount) or amount <= 0:
        raise ValueError("requested_amount must be a positive finite number")
    if not isfinite(price) or price <= 0:
        raise ValueError("price must be a positive finite number")
    if stock_id not in prices:
        raise KeyError(f"Missing price for {stock_id}")

    holding_before = int(account.positions.get(stock_id, 0))
    requested_units = amount / price
    requested_whole_units = floor(requested_units)
    cash_before = round_currency(account.cash)
    portfolio_value_before = account.total_value(prices)
    weight_before = _asset_weight(account, prices, stock_id)

    max_valid_amount: float | None = None
    valid = True
    reason = PreviewReason.OK

    if requested_whole_units < 1:
        valid = False
        reason = PreviewReason.BELOW_ONE_UNIT
        executable_units = 0
    elif action == PortfolioAction.BUY:
        max_units, max_amount, cap_is_binding = _max_buy_capacity(
            account=account,
            stock_id=stock_id,
            price=price,
            prices=prices,
            policy=policy,
        )
        max_valid_amount = round_currency(max_amount)
        if amount > max_amount + 1e-9 or requested_whole_units > max_units:
            valid = False
            reason = PreviewReason.POSITION_LIMIT if cap_is_binding else PreviewReason.INSUFFICIENT_CASH
            executable_units = 0
        else:
            executable_units = requested_whole_units
    elif action == PortfolioAction.SELL:
        max_amount = holding_before * price
        max_valid_amount = round_currency(max_amount)
        if amount > max_amount + 1e-9 or requested_whole_units > holding_before:
            valid = False
            reason = PreviewReason.INSUFFICIENT_HOLDINGS
            executable_units = 0
        else:
            executable_units = requested_whole_units
    else:  # pragma: no cover - enum guards this in production
        raise ValueError(f"Unsupported action: {action}")

    if not valid:
        return OrderPreview(
            stock_id=stock_id,
            action=action,
            requested_amount=round_currency(amount),
            requested_units=requested_units,
            executable_units=0,
            executed_notional=0.0,
            fee=0.0,
            cash_before=cash_before,
            cash_after=cash_before,
            holding_before=holding_before,
            holding_after=holding_before,
            portfolio_value_before=portfolio_value_before,
            portfolio_value_after=portfolio_value_before,
            weight_before=weight_before,
            weight_after=weight_before,
            valid=False,
            reason_code=reason,
            maximum_valid_amount=max_valid_amount,
        )

    executed_notional = round_currency(executable_units * price)
    fee = round_currency(executed_notional * policy.fee_rate)
    if action == PortfolioAction.BUY:
        cash_after = round_currency(cash_before - executed_notional - fee)
        holding_after = holding_before + executable_units
    else:
        cash_after = round_currency(cash_before + executed_notional - fee)
        holding_after = holding_before - executable_units

    if cash_after < -1e-9:
        raise AssertionError("preview produced negative cash")
    if holding_after < 0:
        raise AssertionError("preview produced negative holdings")

    post_account = account.copy()
    post_account.cash = cash_after
    if holding_after == 0:
        post_account.positions.pop(stock_id, None)
    else:
        post_account.positions[stock_id] = holding_after

    portfolio_value_after = post_account.total_value(prices)
    weight_after = _asset_weight(post_account, prices, stock_id)

    if policy.max_position_weight is not None and action == PortfolioAction.BUY:
        if weight_after > float(policy.max_position_weight) + 1e-12:
            raise AssertionError("preview exceeded configured max_position_weight")

    return OrderPreview(
        stock_id=stock_id,
        action=action,
        requested_amount=round_currency(amount),
        requested_units=requested_units,
        executable_units=executable_units,
        executed_notional=executed_notional,
        fee=fee,
        cash_before=cash_before,
        cash_after=cash_after,
        holding_before=holding_before,
        holding_after=holding_after,
        portfolio_value_before=portfolio_value_before,
        portfolio_value_after=portfolio_value_after,
        weight_before=weight_before,
        weight_after=weight_after,
        valid=True,
        reason_code=PreviewReason.OK,
        maximum_valid_amount=max_valid_amount,
    )
