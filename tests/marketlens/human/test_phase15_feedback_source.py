from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import insert

from conftest import create_session
from marketlens.human.feedback import (
    FeedbackKind,
    FeedbackSourceError,
    FeedbackStatisticsSourceAdapter,
)
from marketlens.human.schemas import ParticipantBackgroundRead
from marketlens.human.stores.portfolio_store import (
    PortfolioStore,
)
from marketlens.persistence.schema import (
    portfolio_transactions,
)
from marketlens.stimulus.manifest import sha256_json


DATES = (
    "2023-06-19",
    "2023-06-20",
    "2023-06-21",
    "2023-06-26",
    "2023-06-27",
    "2023-06-28",
    "2023-06-29",
    "2023-06-30",
    "2023-07-03",
    "2023-07-04",
    "2023-07-05",
    "2023-07-06",
    "2023-07-07",
    "2023-07-10",
    "2023-07-11",
)

JUDGEMENT_SPECS = {
    "J0": (0, DATES[0]),
    "J1": (0, DATES[0]),
    "J2": (7, DATES[7]),
    "J3": (7, DATES[7]),
    "J4": (14, DATES[14]),
}


class FakeListStore:
    def __init__(self, rows):
        self.rows = list(rows)

    def list_for_session(self, session_id):
        return tuple(self.rows)


class FakePortfolioStore(FakeListStore):
    def __init__(self, portfolio, rows):
        super().__init__(rows)
        self.portfolio = portfolio

    def get_portfolio(self, session_id):
        return self.portfolio

    def list_transactions_for_session(
        self,
        session_id,
    ):
        return tuple(self.rows)


class FakeAssignmentStore:
    def get(self, session_id):
        return SimpleNamespace(
            episode_id="episode-test"
        )


class FakeProjection:
    def __init__(self, payloads):
        self.episode = SimpleNamespace(
            episode_id="episode-test"
        )
        self.payloads = payloads

    def project(self, *, current_date):
        return self.payloads[current_date]


class FakeContract:
    def checkpoint_date(self, step):
        return DATES[step]

    def judgement_spec(self, event):
        step, day = JUDGEMENT_SPECS[event]
        return SimpleNamespace(
            judgement_event=event,
            experiment_step=step,
            agent_world_date=day,
        )


class FakeCalendar:
    def __init__(self):
        self.statuses = {
            day: SimpleNamespace(
                current_market_date=day,
                market_state_date=day,
                participant_trading_enabled=True,
            )
            for day in DATES
        }

    def status(self, day):
        return self.statuses[day]


class FakePriceProvider:
    def __init__(self):
        self.prices = {}

        for index, day in enumerate(DATES):
            self.prices[
                ("TLEI", day)
            ] = 10.0 + index
            self.prices[
                ("FSEI", day)
            ] = 20.0 + index

    def get_close(self, stock_id, day):
        return SimpleNamespace(
            close=self.prices[
                (stock_id, day)
            ]
        )


def _projection_payloads():
    payloads = {}

    for index, day in enumerate(
        DATES,
        start=1,
    ):
        posts = []

        for post_id in range(
            index,
            0,
            -1,
        ):
            label = (
                "Individual Investor"
                if post_id % 2
                else "Market Blogger"
            )
            posts.append(
                {
                    "post_id": post_id,
                    "author_id": (
                        f"user-{post_id}"
                    ),
                    "source_label": label,
                    "display_text": (
                        f"post {post_id}"
                    ),
                    "created_at": (
                        f"{DATES[post_id - 1]} "
                        "12:00:00"
                    ),
                }
            )

        payloads[day] = {
            "current_date": day,
            "natural_news": [
                f"news {index}"
            ],
            "forum_posts": posts,
        }

    return payloads


def _judgements():
    return [
        {
            "session_id": "session-test",
            "judgement_event": "J0",
            "experiment_step": 0,
            "agent_world_date": DATES[0],
            "stock_id": "TLEI",
            "action": "HOLD",
            "confidence": 70.0,
        },
        {
            "session_id": "session-test",
            "judgement_event": "J1",
            "experiment_step": 0,
            "agent_world_date": DATES[0],
            "stock_id": "TLEI",
            "action": "SELL",
            "confidence": 60.0,
        },
        {
            "session_id": "session-test",
            "judgement_event": "J2",
            "experiment_step": 7,
            "agent_world_date": DATES[7],
            "stock_id": "TLEI",
            "action": "BUY",
            "confidence": 55.0,
        },
        {
            "session_id": "session-test",
            "judgement_event": "J3",
            "experiment_step": 7,
            "agent_world_date": DATES[7],
            "stock_id": "TLEI",
            "action": "HOLD",
            "confidence": 50.0,
        },
        {
            "session_id": "session-test",
            "judgement_event": "J4",
            "experiment_step": 14,
            "agent_world_date": DATES[14],
            "stock_id": "TLEI",
            "action": "SELL",
            "confidence": 45.0,
        },
    ]


def _transactions():
    return [
        {
            "transaction_id": "tx-01",
            "session_id": "session-test",
            "step": 0,
            "stock_id": "TLEI",
            "action": "BUY",
            "settlement_price": 10.0,
            "price_date": DATES[0],
            "cash_before": 1000.0,
            "cash_after": 900.0,
            "holding_before": 0,
            "holding_after": 10,
            "submitted_at": (
                "2023-06-19T12:00:00+00:00"
            ),
        },
        {
            "transaction_id": "tx-05",
            "session_id": "session-test",
            "step": 4,
            "stock_id": "FSEI",
            "action": "BUY",
            "settlement_price": 24.0,
            "price_date": DATES[4],
            "cash_before": 900.0,
            "cash_after": 850.0,
            "holding_before": 0,
            "holding_after": 2,
            "submitted_at": (
                "2023-06-27T12:00:00+00:00"
            ),
        },
        {
            "transaction_id": "tx-08",
            "session_id": "session-test",
            "step": 7,
            "stock_id": "TLEI",
            "action": "SELL",
            "settlement_price": 17.0,
            "price_date": DATES[7],
            "cash_before": 850.0,
            "cash_after": 875.0,
            "holding_before": 10,
            "holding_after": 8,
            "submitted_at": (
                "2023-06-30T12:00:00+00:00"
            ),
        },
        {
            "transaction_id": "tx-11",
            "session_id": "session-test",
            "step": 10,
            "stock_id": "TLEI",
            "action": "BUY",
            "settlement_price": 20.0,
            "price_date": DATES[10],
            "cash_before": 875.0,
            "cash_after": 860.0,
            "holding_before": 8,
            "holding_after": 9,
            "submitted_at": (
                "2023-07-05T12:00:00+00:00"
            ),
        },
    ]


def _rounds():
    return [
        {
            "session_id": "session-test",
            "step": step,
        }
        for step in range(15)
    ]


def _events():
    payloads = _projection_payloads()
    rows = []

    for step, day in enumerate(DATES):
        background = ParticipantBackgroundRead(
            session_id="session-test",
            current_date=day,
            natural_news=payloads[day]["natural_news"],
            forum_posts=payloads[day]["forum_posts"],
        )

        rows.append(
            {
                "session_id": "session-test",
                "episode_id": "episode-test",
                "experiment_step": step,
                "agent_world_date": day,
                "event_type": "BACKGROUND_EXPOSED",
                "payload_digest": sha256_json(
                    background.model_dump(
                        mode="json"
                    )
                ),
            }
        )

    return rows


def _parts():
    calendar = FakeCalendar()

    return {
        "assignments": FakeAssignmentStore(),
        "projections": {
            "episode-test": FakeProjection(
                _projection_payloads()
            )
        },
        "judgements": FakeListStore(
            _judgements()
        ),
        "portfolios": FakePortfolioStore(
            {"initial_cash": 1000.0},
            _transactions(),
        ),
        "rounds": FakeListStore(
            _rounds()
        ),
        "events": FakeListStore(
            _events()
        ),
        "price_provider": FakePriceProvider(),
        "calendar": calendar,
        "contract": FakeContract(),
        "target_stock_id": "TLEI",
    }


def _adapter(parts=None):
    return FeedbackStatisticsSourceAdapter(
        **(parts or _parts())
    )


def test_f1_builds_from_locked_authoritative_sources():
    result = _adapter().build(
        "session-test",
        FeedbackKind.F1,
    )

    assert result.window == {
        "start_period": 1,
        "end_period": 4,
        "periods_reviewed": 4,
    }

    assert result.market_metrics[
        "price_start"
    ] == pytest.approx(10.0)

    assert result.market_metrics[
        "price_end"
    ] == pytest.approx(13.0)

    assert result.portfolio_metrics[
        "starting_value"
    ] == pytest.approx(1000.0)

    # Cash 900 + 10 TLEI marked at P4 price 13.
    assert result.portfolio_metrics[
        "ending_value"
    ] == pytest.approx(1030.0)

    assert result.trading_metrics[
        "transaction_count"
    ] == 1

    assert result.trading_metrics[
        "trade_periods"
    ] == 1

    assert result.trading_metrics[
        "no_trade_periods"
    ] == 3

    assert result.judgement_action_metrics[
        "opposite_direction_actions"
    ] == 1

    assert result.information_metrics[
        "news_items_available"
    ] == 4

    assert result.information_metrics[
        "community_posts_available"
    ] == 4


def test_f2_uses_p4_forum_baseline_and_marks_portfolio_to_market():
    result = _adapter().build(
        "session-test",
        FeedbackKind.F2,
    )

    assert result.window[
        "start_period"
    ] == 5
    assert result.window[
        "end_period"
    ] == 11

    # Before P5 trades:
    # cash 900 + 10 TLEI * P5 price 14.
    assert result.portfolio_metrics[
        "starting_value"
    ] == pytest.approx(1040.0)

    # After P11 trades:
    # cash 860 + 9*TLEI(20) + 2*FSEI(30).
    assert result.portfolio_metrics[
        "ending_value"
    ] == pytest.approx(1100.0)

    assert result.trading_metrics[
        "transaction_count"
    ] == 3
    assert result.trading_metrics[
        "trade_periods"
    ] == 3

    assert result.judgement_action_metrics[
        "hold_with_trade"
    ] == 1

    assert result.information_metrics[
        "news_items_available"
    ] == 7

    # P4 already exposed posts 1..4.
    # F2 counts only new post identities 5..11.
    assert result.information_metrics[
        "community_posts_available"
    ] == 7

    assert result.information_metrics[
        "source_label_counts"
    ] == {
        "Individual Investor": 4,
        "Market Blogger": 3,
    }


def test_final_uses_whole_session_and_j4_no_trade_link():
    result = _adapter().build(
        "session-test",
        FeedbackKind.FINAL,
    )

    assert result.window[
        "periods_reviewed"
    ] == 15

    assert result.portfolio_metrics[
        "starting_value"
    ] == pytest.approx(1000.0)

    # cash 860 + 9*TLEI(24) + 2*FSEI(34)
    assert result.portfolio_metrics[
        "ending_value"
    ] == pytest.approx(1144.0)

    assert result.trading_metrics[
        "transaction_count"
    ] == 4

    assert result.judgement_action_metrics[
        "no_trade"
    ] == 1

    assert result.information_metrics[
        "community_posts_available"
    ] == 15


def test_calendar_not_trade_presence_controls_eligibility():
    parts = _parts()
    parts["calendar"].statuses[
        DATES[1]
    ] = SimpleNamespace(
        market_state_date=DATES[1],
        participant_trading_enabled=False,
    )

    result = _adapter(parts).build(
        "session-test",
        FeedbackKind.F1,
    )

    assert result.trading_metrics[
        "eligible_periods"
    ] == 3


def test_missing_round_lock_fails_closed():
    parts = _parts()
    parts["rounds"].rows = [
        row
        for row in parts["rounds"].rows
        if row["step"] != 3
    ]

    with pytest.raises(
        FeedbackSourceError,
        match="locked completion",
    ):
        _adapter(parts).build(
            "session-test",
            FeedbackKind.F1,
        )


def test_missing_background_exposure_fails_closed():
    parts = _parts()
    parts["events"].rows = [
        row
        for row in parts["events"].rows
        if row["experiment_step"] != 2
    ]

    with pytest.raises(
        FeedbackSourceError,
        match="BACKGROUND_EXPOSED",
    ):
        _adapter(parts).build(
            "session-test",
            FeedbackKind.F1,
        )


def test_judgement_protocol_mismatch_fails_closed():
    parts = _parts()

    for row in parts["judgements"].rows:
        if row["judgement_event"] == "J1":
            row["agent_world_date"] = (
                "2023-06-20"
            )

    with pytest.raises(
        FeedbackSourceError,
        match="disagrees with frozen protocol",
    ):
        _adapter(parts).build(
            "session-test",
            FeedbackKind.F1,
        )


def test_transaction_continuity_mismatch_fails_closed():
    parts = _parts()

    for row in parts["portfolios"].rows:
        if row["transaction_id"] == "tx-05":
            row["cash_before"] = 999.0

    with pytest.raises(
        FeedbackSourceError,
        match="cash continuity",
    ):
        _adapter(parts).build(
            "session-test",
            FeedbackKind.F2,
        )


def _db_transaction_row(
    *,
    session_id,
    transaction_id,
    request_id,
    step,
    submitted_at,
):
    return {
        "transaction_id": transaction_id,
        "session_id": session_id,
        "request_id": request_id,
        "step": step,
        "stock_id": "TLEI",
        "action": "BUY",
        "requested_amount": 10.0,
        "requested_units": 1.0,
        "executed_units": 1,
        "executed_notional": 10.0,
        "settlement_price": 10.0,
        "price_date": "2023-06-19",
        "transaction_cost_bps": 0.0,
        "fee": 0.0,
        "cash_before": 1000.0,
        "cash_after": 990.0,
        "holding_before": 0,
        "holding_after": 1,
        "portfolio_value_before": 1000.0,
        "portfolio_value_after": 1000.0,
        "weight_before": 0.0,
        "weight_after": 0.01,
        "submitted_at": submitted_at,
    }


def test_portfolio_store_transaction_reader_is_session_scoped_and_stable(
    client,
):
    session = create_session(
        client,
        participant_id="feedback-reader",
        request_id="feedback-reader-session",
    )
    session_id = session["session_id"]

    later = _db_transaction_row(
        session_id=session_id,
        transaction_id="tx-later",
        request_id="req-later",
        step=1,
        submitted_at=(
            "2023-06-20T12:00:00+00:00"
        ),
    )
    earlier = _db_transaction_row(
        session_id=session_id,
        transaction_id="tx-earlier",
        request_id="req-earlier",
        step=0,
        submitted_at=(
            "2023-06-19T12:00:00+00:00"
        ),
    )

    with client.app.state.db.connect() as connection:
        connection.execute(
            insert(
                portfolio_transactions
            ),
            [later, earlier],
        )

    rows = PortfolioStore(
        client.app.state.db
    ).list_transactions_for_session(
        session_id
    )

    assert [
        row["transaction_id"]
        for row in rows
    ] == [
        "tx-earlier",
        "tx-later",
    ]

    assert all(
        row["session_id"] == session_id
        for row in rows
    )


def test_background_payload_digest_mismatch_fails_closed():
    parts = _parts()

    parts["events"].rows[0][
        "payload_digest"
    ] = "0" * 64

    with pytest.raises(
        FeedbackSourceError,
        match="payload digest mismatch",
    ):
        _adapter(parts).build(
            "session-test",
            FeedbackKind.F1,
        )


def test_transaction_price_date_mismatch_fails_closed():
    parts = _parts()

    for row in parts["portfolios"].rows:
        if row["transaction_id"] == "tx-05":
            row["price_date"] = DATES[5]

    with pytest.raises(
        FeedbackSourceError,
        match="price_date disagrees",
    ):
        _adapter(parts).build(
            "session-test",
            FeedbackKind.F2,
        )


def test_transaction_settlement_price_mismatch_fails_closed():
    parts = _parts()

    for row in parts["portfolios"].rows:
        if row["transaction_id"] == "tx-05":
            row["settlement_price"] = 999.0

    with pytest.raises(
        FeedbackSourceError,
        match="settlement price mismatch",
    ):
        _adapter(parts).build(
            "session-test",
            FeedbackKind.F2,
        )


def test_transaction_on_disabled_period_fails_closed():
    parts = _parts()

    parts["calendar"].statuses[
        DATES[4]
    ] = SimpleNamespace(
        current_market_date=DATES[4],
        market_state_date=DATES[4],
        participant_trading_enabled=False,
    )

    with pytest.raises(
        FeedbackSourceError,
        match="non-trading-enabled",
    ):
        _adapter(parts).build(
            "session-test",
            FeedbackKind.F2,
        )
