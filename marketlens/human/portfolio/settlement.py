from __future__ import annotations

from marketlens.human.portfolio.models import AccountState
from marketlens.human.portfolio.preview import OrderPreview


def execute_preview(account: AccountState, preview: OrderPreview) -> AccountState:
    """Apply an already-valid preview without reimplementing settlement maths."""

    if not preview.valid:
        raise ValueError("Cannot execute an invalid order preview")

    result = account.copy()
    untouched = {
        stock_id: quantity
        for stock_id, quantity in account.positions.items()
        if stock_id != preview.stock_id
    }

    result.cash = preview.cash_after
    if preview.holding_after == 0:
        result.positions.pop(preview.stock_id, None)
    else:
        result.positions[preview.stock_id] = preview.holding_after

    for stock_id, quantity in untouched.items():
        if result.positions.get(stock_id) != quantity:
            raise AssertionError("Settlement changed a non-target holding")

    return result
