from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import delete, insert, select, update

from marketlens.human.portfolio.models import AccountState
from marketlens.persistence.database import Database
from marketlens.persistence.schema import (
    participant_portfolios,
    portfolio_holdings,
    portfolio_transactions,
    sessions,
)

from .errors import (
    StoreIdempotencyConflictError,
    StorePortfolioStateConflictError,
    StoreSessionNotFoundError,
    StoreWrongExperimentStepError,
)


RowMapping = Mapping[str, Any]


@dataclass(frozen=True)
class PortfolioSnapshot:
    session_id: str
    current_step: int
    current_date: str | None
    account: AccountState


class PortfolioStore:
    def __init__(self, db: Database):
        self.db = db

    def get_portfolio(self, session_id: str) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(participant_portfolios).where(
                    participant_portfolios.c.session_id == session_id
                )
            ).mappings().first()

    def get_holdings(self, session_id: str) -> tuple[RowMapping, ...]:
        with self.db.connect() as connection:
            rows = connection.execute(
                select(portfolio_holdings)
                .where(portfolio_holdings.c.session_id == session_id)
                .order_by(portfolio_holdings.c.stock_id)
            ).mappings().all()
        return tuple(rows)

    def get_account_state(self, session_id: str) -> AccountState | None:
        portfolio = self.get_portfolio(session_id)
        if portfolio is None:
            return None
        positions = {
            row["stock_id"]: int(row["quantity"])
            for row in self.get_holdings(session_id)
        }
        return AccountState(cash=float(portfolio["cash"]), positions=positions)

    def get_snapshot(self, session_id: str) -> PortfolioSnapshot:
        with self.db.connect() as connection:
            session = connection.execute(
                select(sessions).where(sessions.c.session_id == session_id)
            ).mappings().first()
            if session is None:
                raise StoreSessionNotFoundError(session_id)
            portfolio = connection.execute(
                select(participant_portfolios).where(
                    participant_portfolios.c.session_id == session_id
                )
            ).mappings().first()
            if portfolio is None:
                raise StorePortfolioStateConflictError("Participant portfolio is missing")
            holdings = connection.execute(
                select(portfolio_holdings.c.stock_id, portfolio_holdings.c.quantity).where(
                    portfolio_holdings.c.session_id == session_id
                )
            ).mappings().all()
        return PortfolioSnapshot(
            session_id=session_id,
            current_step=int(session["current_step"]),
            current_date=session["current_date"],
            account=AccountState(
                cash=float(portfolio["cash"]),
                positions={row["stock_id"]: int(row["quantity"]) for row in holdings},
            ),
        )

    def get_transaction_by_request_id(
        self,
        session_id: str,
        request_id: str,
    ) -> RowMapping | None:
        with self.db.connect() as connection:
            return connection.execute(
                select(portfolio_transactions).where(
                    portfolio_transactions.c.session_id == session_id,
                    portfolio_transactions.c.request_id == request_id,
                )
            ).mappings().first()

    def list_transactions_for_session(
        self,
        session_id: str,
    ) -> tuple[RowMapping, ...]:
        """Return this participant session's settled transactions in stable order."""

        with self.db.connect() as connection:
            rows = connection.execute(
                select(portfolio_transactions)
                .where(
                    portfolio_transactions.c.session_id
                    == session_id
                )
                .order_by(
                    portfolio_transactions.c.step,
                    portfolio_transactions.c.submitted_at,
                    portfolio_transactions.c.transaction_id,
                )
            ).mappings().all()
        return tuple(rows)

    def apply_order_idempotent(
        self,
        *,
        transaction_id: str,
        session_id: str,
        request_id: str,
        step: int,
        stock_id: str,
        action: str,
        requested_amount: float,
        requested_units: float,
        executed_units: int,
        executed_notional: float,
        settlement_price: float,
        price_date: str,
        transaction_cost_bps: float,
        fee: float,
        cash_before: float,
        cash_after: float,
        holding_before: int,
        holding_after: int,
        portfolio_value_before: float,
        portfolio_value_after: float,
        weight_before: float,
        weight_after: float,
        submitted_at: str,
    ) -> RowMapping:
        with self.db.connect() as connection:
            # The session lock serialises round completion and confirmed orders
            # for one participant on PostgreSQL. SQLite ignores FOR UPDATE but
            # still keeps the same transactional correctness in local use.
            session = connection.execute(
                select(sessions)
                .where(sessions.c.session_id == session_id)
                .with_for_update()
            ).mappings().first()
            if session is None:
                raise StoreSessionNotFoundError(session_id)

            existing = connection.execute(
                select(portfolio_transactions).where(
                    portfolio_transactions.c.session_id == session_id,
                    portfolio_transactions.c.request_id == request_id,
                )
            ).mappings().first()
            if existing is not None:
                same_payload = (
                    int(existing["step"]) == int(step)
                    and existing["stock_id"] == stock_id
                    and existing["action"] == action
                    and abs(float(existing["requested_amount"]) - float(requested_amount)) < 1e-9
                )
                if not same_payload:
                    raise StoreIdempotencyConflictError(
                        "request_id was already used for a different portfolio order"
                    )
                return existing

            if int(session["current_step"]) != int(step):
                raise StoreWrongExperimentStepError(
                    f"Expected current step {session['current_step']}, got {step}"
                )
            if session["current_date"] != price_date:
                raise StorePortfolioStateConflictError(
                    "Session market date changed; preview the order again"
                )

            portfolio = connection.execute(
                select(participant_portfolios)
                .where(participant_portfolios.c.session_id == session_id)
                .with_for_update()
            ).mappings().first()
            if portfolio is None:
                raise StorePortfolioStateConflictError("Participant portfolio is missing")

            holding = connection.execute(
                select(portfolio_holdings).where(
                    portfolio_holdings.c.session_id == session_id,
                    portfolio_holdings.c.stock_id == stock_id,
                )
            ).mappings().first()
            current_holding = int(holding["quantity"]) if holding is not None else 0

            if (
                abs(float(portfolio["cash"]) - float(cash_before)) > 0.005
                or current_holding != holding_before
            ):
                raise StorePortfolioStateConflictError(
                    "Participant portfolio changed; preview the order again"
                )

            result = connection.execute(
                update(participant_portfolios)
                .where(participant_portfolios.c.session_id == session_id)
                .values(cash=cash_after, updated_at=submitted_at)
            )
            if result.rowcount != 1:
                raise StorePortfolioStateConflictError("Participant portfolio is missing")

            if holding_after == 0:
                connection.execute(
                    delete(portfolio_holdings).where(
                        portfolio_holdings.c.session_id == session_id,
                        portfolio_holdings.c.stock_id == stock_id,
                    )
                )
            elif holding is None:
                connection.execute(
                    insert(portfolio_holdings).values(
                        session_id=session_id,
                        stock_id=stock_id,
                        quantity=holding_after,
                        updated_at=submitted_at,
                    )
                )
            else:
                connection.execute(
                    update(portfolio_holdings)
                    .where(
                        portfolio_holdings.c.session_id == session_id,
                        portfolio_holdings.c.stock_id == stock_id,
                    )
                    .values(quantity=holding_after, updated_at=submitted_at)
                )

            connection.execute(
                insert(portfolio_transactions).values(
                    transaction_id=transaction_id,
                    session_id=session_id,
                    request_id=request_id,
                    step=step,
                    stock_id=stock_id,
                    action=action,
                    requested_amount=requested_amount,
                    requested_units=requested_units,
                    executed_units=executed_units,
                    executed_notional=executed_notional,
                    settlement_price=settlement_price,
                    price_date=price_date,
                    transaction_cost_bps=transaction_cost_bps,
                    fee=fee,
                    cash_before=cash_before,
                    cash_after=cash_after,
                    holding_before=holding_before,
                    holding_after=holding_after,
                    portfolio_value_before=portfolio_value_before,
                    portfolio_value_after=portfolio_value_after,
                    weight_before=weight_before,
                    weight_after=weight_after,
                    submitted_at=submitted_at,
                )
            )
            row = connection.execute(
                select(portfolio_transactions).where(
                    portfolio_transactions.c.transaction_id == transaction_id
                )
            ).mappings().first()
            assert row is not None
            return row
