from __future__ import annotations

from marketlens.human.participant_asset_labels import (
    participant_asset_display_name,
    participant_asset_short_name,
    validate_participant_asset_labels,
)


from datetime import datetime, timezone
from uuid import uuid4

from marketlens.human.portfolio.policy import PortfolioPolicy
from marketlens.human.portfolio.settlement import execute_preview
from marketlens.human.portfolio.preview import (
    PortfolioAction as DomainAction,
    OrderPreview,
    preview_order,
)
from marketlens.human.schemas import (
    PortfolioHoldingRead,
    PortfolioOrderCreate,
    PortfolioOrderPreviewCreate,
    PortfolioOrderPreviewRead,
    PortfolioRead,
    PortfolioTransactionRead,
)
from marketlens.human.services.session_service import (
    IdempotencyConflictError,
    SessionNotFoundError,
)
from marketlens.human.stores.errors import (
    StoreIdempotencyConflictError,
    StorePortfolioStateConflictError,
    StoreSessionNotFoundError,
    StoreWrongExperimentStepError,
)
from marketlens.human.stores.portfolio_store import PortfolioSnapshot, PortfolioStore
from marketlens.market.asset_catalog import AssetCatalog, AssetNotFoundError
from marketlens.market.price_provider import CsvClosePriceProvider, PriceNotFoundError
from marketlens.market.status import TradingCalendar, TradingCalendarError


class PortfolioNotFoundError(LookupError):
    pass


class WrongPortfolioStepError(ValueError):
    pass


class MarketDateUnavailableError(ValueError):
    pass


class MarketClosedError(ValueError):
    pass


class InvalidPortfolioOrderError(ValueError):
    pass


class PortfolioStateConflictError(ValueError):
    pass


def _to_transaction(row) -> PortfolioTransactionRead:
    return PortfolioTransactionRead(
        transaction_id=row["transaction_id"],
        session_id=row["session_id"],
        request_id=row["request_id"],
        step=row["step"],
        stock_id=row["stock_id"],
        action=row["action"],
        requested_amount=row["requested_amount"],
        requested_units=row["requested_units"],
        executed_units=row["executed_units"],
        executed_notional=row["executed_notional"],
        settlement_price=row["settlement_price"],
        price_date=row["price_date"],
        transaction_cost_bps=row["transaction_cost_bps"],
        fee=row["fee"],
        cash_before=row["cash_before"],
        cash_after=row["cash_after"],
        holding_before=row["holding_before"],
        holding_after=row["holding_after"],
        portfolio_value_before=row["portfolio_value_before"],
        portfolio_value_after=row["portfolio_value_after"],
        weight_before=row["weight_before"],
        weight_after=row["weight_after"],
        submitted_at=row["submitted_at"],
    )


class PortfolioService:
    def __init__(
        self,
        *,
        store: PortfolioStore,
        assets: AssetCatalog,
        prices: CsvClosePriceProvider,
        policy: PortfolioPolicy,
        calendar: TradingCalendar,
    ):
        self.store = store
        self.assets = assets
        self.prices = prices
        self.policy = policy
        self.calendar = calendar

    def _snapshot(self, session_id: str, expected_step: int | None = None) -> PortfolioSnapshot:
        try:
            snapshot = self.store.get_snapshot(session_id)
        except StoreSessionNotFoundError as exc:
            raise SessionNotFoundError(session_id) from exc
        except StorePortfolioStateConflictError as exc:
            raise PortfolioStateConflictError(str(exc)) from exc
        if expected_step is not None and snapshot.current_step != expected_step:
            raise WrongPortfolioStepError(
                f"Expected current step {snapshot.current_step}, got {expected_step}"
            )
        return snapshot

    def _market_status(self, snapshot: PortfolioSnapshot):
        if snapshot.current_date is None:
            raise MarketDateUnavailableError(
                "Session current_date is not set; experiment state must authorise a market date before trading"
            )
        try:
            return self.calendar.status(snapshot.current_date)
        except TradingCalendarError as exc:
            raise MarketDateUnavailableError(str(exc)) from exc

    def _authorise_trading(self, snapshot: PortfolioSnapshot):
        market = self._market_status(snapshot)
        if not market.participant_trading_enabled:
            raise MarketClosedError(
                f"Participant trading is unavailable on {market.current_market_date} "
                f"({market.market_status_reason}); next trading date is {market.next_trading_date}"
            )
        return market

    def _prices_for_date(
        self,
        snapshot: PortfolioSnapshot,
        target_stock_id: str,
        *,
        price_date: str,
    ) -> dict[str, float]:
        stock_ids = set(snapshot.account.positions)
        stock_ids.add(target_stock_id)
        prices: dict[str, float] = {}
        try:
            for stock_id in stock_ids:
                prices[stock_id] = self.prices.get_close(stock_id, price_date).close
        except PriceNotFoundError as exc:
            raise MarketDateUnavailableError(
                f"No exact-date close price is available for authorised market state date: {price_date}"
            ) from exc
        return prices

    def _preview(self, session_id: str, payload: PortfolioOrderPreviewCreate) -> tuple[PortfolioSnapshot, OrderPreview, float]:
        try:
            self.assets.get(payload.stock_id)
        except AssetNotFoundError:
            raise
        snapshot = self._snapshot(session_id, payload.step)
        market = self._authorise_trading(snapshot)
        price_map = self._prices_for_date(
            snapshot, payload.stock_id, price_date=market.current_market_date
        )
        price = price_map[payload.stock_id]
        preview = preview_order(
            account=snapshot.account,
            stock_id=payload.stock_id,
            action=DomainAction(payload.action.value),
            requested_amount=payload.amount,
            price=price,
            prices=price_map,
            policy=self.policy,
        )
        return snapshot, preview, price

    def preview(self, session_id: str, payload: PortfolioOrderPreviewCreate) -> PortfolioOrderPreviewRead:
        snapshot, preview, price = self._preview(session_id, payload)
        assert snapshot.current_date is not None
        return PortfolioOrderPreviewRead(
            session_id=session_id,
            step=snapshot.current_step,
            price_date=snapshot.current_date,
            stock_id=preview.stock_id,
            action=preview.action.value,
            settlement_price=price,
            requested_amount=preview.requested_amount,
            requested_units=preview.requested_units,
            executable_units=preview.executable_units,
            executed_notional=preview.executed_notional,
            fee=preview.fee,
            cash_before=preview.cash_before,
            cash_after=preview.cash_after,
            holding_before=preview.holding_before,
            holding_after=preview.holding_after,
            portfolio_value_before=preview.portfolio_value_before,
            portfolio_value_after=preview.portfolio_value_after,
            weight_before=preview.weight_before,
            weight_after=preview.weight_after,
            valid=preview.valid,
            reason_code=preview.reason_code.value,
            maximum_valid_amount=preview.maximum_valid_amount,
        )

    def submit(self, session_id: str, payload: PortfolioOrderCreate) -> PortfolioTransactionRead:
        existing = self.store.get_transaction_by_request_id(session_id, payload.request_id)
        if existing is not None:
            same_payload = (
                int(existing["step"]) == payload.step
                and existing["stock_id"] == payload.stock_id
                and existing["action"] == payload.action.value
                and abs(float(existing["requested_amount"]) - float(payload.amount)) < 1e-9
            )
            if not same_payload:
                raise IdempotencyConflictError(
                    "request_id was already used for a different portfolio order"
                )
            return _to_transaction(existing)

        snapshot, preview, price = self._preview(session_id, payload)
        if not preview.valid:
            detail = preview.reason_code.value
            if preview.maximum_valid_amount is not None:
                detail += f"; maximum_valid_amount={preview.maximum_valid_amount:.2f}"
            raise InvalidPortfolioOrderError(detail)
        assert snapshot.current_date is not None
        post_account = execute_preview(snapshot.account, preview)

        now = datetime.now(timezone.utc).isoformat()
        try:
            row = self.store.apply_order_idempotent(
                transaction_id=str(uuid4()),
                session_id=session_id,
                request_id=payload.request_id,
                step=payload.step,
                stock_id=payload.stock_id,
                action=payload.action.value,
                requested_amount=preview.requested_amount,
                requested_units=preview.requested_units,
                executed_units=preview.executable_units,
                executed_notional=preview.executed_notional,
                settlement_price=price,
                price_date=snapshot.current_date,
                transaction_cost_bps=self.policy.transaction_cost_bps,
                fee=preview.fee,
                cash_before=preview.cash_before,
                cash_after=post_account.cash,
                holding_before=preview.holding_before,
                holding_after=int(post_account.positions.get(payload.stock_id, 0)),
                portfolio_value_before=preview.portfolio_value_before,
                portfolio_value_after=preview.portfolio_value_after,
                weight_before=preview.weight_before,
                weight_after=preview.weight_after,
                submitted_at=now,
            )
        except StoreSessionNotFoundError as exc:
            raise SessionNotFoundError(session_id) from exc
        except StoreIdempotencyConflictError as exc:
            raise IdempotencyConflictError(str(exc)) from exc
        except StoreWrongExperimentStepError as exc:
            raise WrongPortfolioStepError(str(exc)) from exc
        except StorePortfolioStateConflictError as exc:
            raise PortfolioStateConflictError(str(exc)) from exc
        return _to_transaction(row)

    def get_portfolio(self, session_id: str) -> PortfolioRead:
        snapshot = self._snapshot(session_id)
        row = self.store.get_portfolio(session_id)
        if row is None:
            raise PortfolioNotFoundError(session_id)

        if not snapshot.account.positions:
            price_date = None
            if snapshot.current_date is not None:
                price_date = self.calendar.status(snapshot.current_date).market_state_date
            return PortfolioRead(
                session_id=session_id,
                step=snapshot.current_step,
                price_date=price_date,
                initial_cash=float(row["initial_cash"]),
                cash=snapshot.account.cash,
                total_value=snapshot.account.cash,
                holdings=[],
            )

        if snapshot.current_date is None:
            raise MarketDateUnavailableError(
                "Session current_date is required to value non-empty holdings"
            )

        market = self.calendar.status(snapshot.current_date)
        price_map = self._prices_for_date(
            snapshot,
            next(iter(snapshot.account.positions)),
            price_date=market.market_state_date,
        )
        total = snapshot.account.total_value(price_map)
        holdings: list[PortfolioHoldingRead] = []
        validate_participant_asset_labels(
            self.assets.ids()
        )
        for stock_id, quantity in sorted(snapshot.account.positions.items()):
            asset = self.assets.get(stock_id)
            current_price = price_map[stock_id]
            market_value = quantity * current_price
            holdings.append(
                PortfolioHoldingRead(
                    stock_id=stock_id,
                    name=participant_asset_display_name(
                        asset.stock_id
                    ),
                    short_name=participant_asset_short_name(
                        asset.stock_id
                    ),
                    quantity=quantity,
                    current_price=current_price,
                    market_value=round(market_value, 2),
                    portfolio_weight=(market_value / total) if total > 0 else 0.0,
                )
            )
        return PortfolioRead(
            session_id=session_id,
            step=snapshot.current_step,
            price_date=market.market_state_date,
            initial_cash=float(row["initial_cash"]),
            cash=snapshot.account.cash,
            total_value=total,
            holdings=holdings,
        )
