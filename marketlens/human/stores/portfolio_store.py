from __future__ import annotations

from dataclasses import dataclass
from sqlite3 import Row

from marketlens.human.portfolio.models import AccountState

from .database import Database
from .errors import (
    StoreIdempotencyConflictError,
    StorePortfolioStateConflictError,
    StoreSessionNotFoundError,
    StoreWrongExperimentStepError,
)


@dataclass(frozen=True)
class PortfolioSnapshot:
    session_id: str
    current_step: int
    current_date: str | None
    account: AccountState


class PortfolioStore:
    def __init__(self, db: Database):
        self.db = db

    def get_portfolio(self, session_id: str) -> Row | None:
        with self.db.connect() as connection:
            return connection.execute(
                "SELECT * FROM participant_portfolios WHERE session_id = ?",
                (session_id,),
            ).fetchone()

    def get_holdings(self, session_id: str) -> tuple[Row, ...]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM portfolio_holdings
                WHERE session_id = ?
                ORDER BY stock_id
                """,
                (session_id,),
            ).fetchall()
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
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session is None:
                raise StoreSessionNotFoundError(session_id)
            portfolio = connection.execute(
                "SELECT * FROM participant_portfolios WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if portfolio is None:
                raise StorePortfolioStateConflictError("Participant portfolio is missing")
            holdings = connection.execute(
                "SELECT stock_id, quantity FROM portfolio_holdings WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        return PortfolioSnapshot(
            session_id=session_id,
            current_step=int(session["current_step"]),
            current_date=session["current_date"],
            account=AccountState(
                cash=float(portfolio["cash"]),
                positions={row["stock_id"]: int(row["quantity"]) for row in holdings},
            ),
        )

    def get_transaction_by_request_id(self, session_id: str, request_id: str) -> Row | None:
        with self.db.connect() as connection:
            return connection.execute(
                """
                SELECT * FROM portfolio_transactions
                WHERE session_id = ? AND request_id = ?
                """,
                (session_id, request_id),
            ).fetchone()

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
    ) -> Row:
        with self.db.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            existing = connection.execute(
                """
                SELECT * FROM portfolio_transactions
                WHERE session_id = ? AND request_id = ?
                """,
                (session_id, request_id),
            ).fetchone()
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

            session = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session is None:
                raise StoreSessionNotFoundError(session_id)
            if int(session["current_step"]) != int(step):
                raise StoreWrongExperimentStepError(
                    f"Expected current step {session['current_step']}, got {step}"
                )
            if session["current_date"] != price_date:
                raise StorePortfolioStateConflictError(
                    "Session market date changed; preview the order again"
                )

            portfolio = connection.execute(
                "SELECT * FROM participant_portfolios WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if portfolio is None:
                raise StorePortfolioStateConflictError("Participant portfolio is missing")
            holding = connection.execute(
                """
                SELECT quantity FROM portfolio_holdings
                WHERE session_id = ? AND stock_id = ?
                """,
                (session_id, stock_id),
            ).fetchone()
            current_holding = int(holding["quantity"]) if holding is not None else 0

            if abs(float(portfolio["cash"]) - float(cash_before)) > 0.005 or current_holding != holding_before:
                raise StorePortfolioStateConflictError(
                    "Participant portfolio changed; preview the order again"
                )

            connection.execute(
                "UPDATE participant_portfolios SET cash = ?, updated_at = ? WHERE session_id = ?",
                (cash_after, submitted_at, session_id),
            )
            if holding_after == 0:
                connection.execute(
                    "DELETE FROM portfolio_holdings WHERE session_id = ? AND stock_id = ?",
                    (session_id, stock_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO portfolio_holdings (session_id, stock_id, quantity, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(session_id, stock_id)
                    DO UPDATE SET quantity = excluded.quantity, updated_at = excluded.updated_at
                    """,
                    (session_id, stock_id, holding_after, submitted_at),
                )

            connection.execute(
                """
                INSERT INTO portfolio_transactions (
                    transaction_id, session_id, request_id, step, stock_id, action,
                    requested_amount, requested_units, executed_units, executed_notional,
                    settlement_price, price_date, transaction_cost_bps, fee,
                    cash_before, cash_after, holding_before, holding_after,
                    portfolio_value_before, portfolio_value_after,
                    weight_before, weight_after, submitted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction_id, session_id, request_id, step, stock_id, action,
                    requested_amount, requested_units, executed_units, executed_notional,
                    settlement_price, price_date, transaction_cost_bps, fee,
                    cash_before, cash_after, holding_before, holding_after,
                    portfolio_value_before, portfolio_value_after,
                    weight_before, weight_after, submitted_at,
                ),
            )
            row = connection.execute(
                "SELECT * FROM portfolio_transactions WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
            assert row is not None
            return row
