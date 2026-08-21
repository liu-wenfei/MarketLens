from __future__ import annotations

from sqlite3 import Row

from marketlens.human.portfolio.models import AccountState

from .database import Database


class PortfolioStore:
    """Read participant account state created with a MarketLens session.

    Phase 2A deliberately exposes no trade/update method. Settlement writes are
    added only in later Phase 2 gates.
    """

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
