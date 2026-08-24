from __future__ import annotations

from marketlens.human.schemas import SessionState
from marketlens.human.services.session_service import SessionService
from marketlens.market.status import TradingCalendar, TradingCalendarError


class MarketStateUnavailableError(ValueError):
    pass


class StateService:
    def __init__(self, sessions: SessionService, calendar: TradingCalendar):
        self.sessions = sessions
        self.calendar = calendar

    def get_current_state(self, session_id: str) -> SessionState:
        session = self.sessions.get(session_id)
        if session.current_date is None:
            return SessionState(
                session_id=session.session_id,
                current_step=session.current_step,
                current_date=None,
                experiment_status=session.experiment_status,
                completed=session.completed,
                market_open=False,
                market_status_reason="market_date_unavailable",
                current_market_date=None,
                next_trading_date=None,
                closure_start_date=None,
                closure_end_date=None,
                participant_trading_enabled=False,
                market_state_date=None,
            )

        try:
            market = self.calendar.status(session.current_date)
        except TradingCalendarError as exc:
            raise MarketStateUnavailableError(str(exc)) from exc
        return SessionState(
            session_id=session.session_id,
            current_step=session.current_step,
            current_date=session.current_date,
            experiment_status=session.experiment_status,
            completed=session.completed,
            market_open=market.market_open,
            market_status_reason=market.market_status_reason,
            current_market_date=market.current_market_date,
            next_trading_date=market.next_trading_date,
            closure_start_date=market.closure_start_date,
            closure_end_date=market.closure_end_date,
            participant_trading_enabled=market.participant_trading_enabled,
            market_state_date=market.market_state_date,
        )
