from __future__ import annotations

import pytest

from marketlens.human.feedback.journey import (
    BEHAVIOUR_BUY_ONLY,
    BEHAVIOUR_MIXED,
    BEHAVIOUR_NO_TRADE,
    BEHAVIOUR_SELL_ONLY,
    FEEDBACK_DECISION,
    FEEDBACK_FINAL,
    FEEDBACK_NONE,
    JOURNEY_VERSION,
    PNL_FLAT,
    PNL_GAIN,
    PNL_LOSS,
    JourneyJudgementInput,
    JourneyPeriodInput,
    JourneyTransactionInput,
    ParticipantDecisionJourneyError,
    build_participant_decision_journey,
)


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


def _judgement(
    period,
    *,
    action,
    confidence,
    minute,
    rationale=None,
):
    return JourneyJudgementInput(
        period_number=period,
        stock_id="TLEI",
        action=action,
        confidence=confidence,
        evidence_sources=(
            "market information",
        ),
        rationale=rationale,
        submitted_at=(
            f"{DATES[period - 1]}T12:{minute:02d}:00+00:00"
        ),
    )


def _transaction(
    period,
    *,
    transaction_id,
    stock_id,
    action,
    units,
    notional,
    price,
    fee,
    cash_before,
    cash_after,
    holding_before,
    holding_after,
    minute=30,
):
    return JourneyTransactionInput(
        transaction_id=transaction_id,
        period_number=period,
        stock_id=stock_id,
        action=action,
        requested_amount=notional,
        requested_units=float(units),
        executed_units=units,
        executed_notional=notional,
        settlement_price=price,
        fee=fee,
        cash_before=cash_before,
        cash_after=cash_after,
        holding_before=holding_before,
        holding_after=holding_after,
        submitted_at=(
            f"{DATES[period - 1]}T13:{minute:02d}:00+00:00"
        ),
    )


def _period(
    number,
    *,
    judgements=(),
    transactions=(),
    prices=None,
    round_locked=True,
    trading_enabled=True,
):
    return JourneyPeriodInput(
        period_number=number,
        agent_world_date=DATES[number - 1],
        market_open=True,
        participant_trading_enabled=(
            trading_enabled
        ),
        round_locked=round_locked,
        judgements=tuple(judgements),
        transactions=tuple(transactions),
        canonical_close_prices=(
            dict(prices or {})
        ),
    )


def test_p1_to_p4_reconstructs_decision_and_pnl_journey():
    periods = (
        _period(
            1,
            judgements=(
                _judgement(
                    1,
                    action="HOLD",
                    confidence=70,
                    minute=0,
                    rationale="Initial view.",
                ),
                _judgement(
                    1,
                    action="BUY",
                    confidence=60,
                    minute=5,
                    rationale="Updated view.",
                ),
            ),
            prices={},
        ),
        _period(
            2,
            prices={},
        ),
        _period(
            3,
            transactions=(
                _transaction(
                    3,
                    transaction_id="tx-p3-buy",
                    stock_id="TLEI",
                    action="BUY",
                    units=10,
                    notional=100.0,
                    price=10.0,
                    fee=0.0,
                    cash_before=1000.0,
                    cash_after=900.0,
                    holding_before=0,
                    holding_after=10,
                ),
            ),
            prices={"TLEI": 11.0},
        ),
        _period(
            4,
            prices={"TLEI": 13.0},
        ),
    )

    journey = build_participant_decision_journey(
        target_stock_id="TLEI",
        initial_cash=1000.0,
        initial_holdings={},
        initial_portfolio_value=1000.0,
        periods=periods,
    )

    assert journey.journey_version == JOURNEY_VERSION
    assert len(journey.periods) == 4

    p1, p2, p3, p4 = journey.periods

    assert len(p1.judgements) == 2
    assert [item.action for item in p1.judgements] == [
        "HOLD",
        "BUY",
    ]

    assert p1.behaviour_summary == BEHAVIOUR_NO_TRADE
    assert p2.behaviour_summary == BEHAVIOUR_NO_TRADE
    assert p3.behaviour_summary == BEHAVIOUR_BUY_ONLY
    assert p4.behaviour_summary == BEHAVIOUR_NO_TRADE

    assert p1.portfolio_end.portfolio_value == pytest.approx(
        1000.0
    )
    assert p2.portfolio_end.portfolio_value == pytest.approx(
        1000.0
    )

    # P3: cash 900 + 10 * 11
    assert p3.portfolio_end.portfolio_value == pytest.approx(
        1010.0
    )
    assert p3.period_pnl == pytest.approx(10.0)
    assert p3.cumulative_pnl == pytest.approx(10.0)
    assert p3.pnl_direction == PNL_GAIN

    # P4: cash 900 + 10 * 13
    assert p4.portfolio_end.portfolio_value == pytest.approx(
        1030.0
    )
    assert p4.period_pnl == pytest.approx(20.0)
    assert p4.cumulative_pnl == pytest.approx(30.0)
    assert p4.feedback_boundary == FEEDBACK_DECISION


def test_multi_asset_portfolio_is_marked_to_all_held_assets():
    periods = (
        _period(
            1,
            judgements=(
                _judgement(
                    1,
                    action="BUY",
                    confidence=60,
                    minute=0,
                ),
                _judgement(
                    1,
                    action="BUY",
                    confidence=65,
                    minute=5,
                ),
            ),
            transactions=(
                _transaction(
                    1,
                    transaction_id="tx-target",
                    stock_id="TLEI",
                    action="BUY",
                    units=10,
                    notional=100,
                    price=10,
                    fee=0,
                    cash_before=1000,
                    cash_after=900,
                    holding_before=0,
                    holding_after=10,
                    minute=10,
                ),
                _transaction(
                    1,
                    transaction_id="tx-other",
                    stock_id="FSEI",
                    action="BUY",
                    units=2,
                    notional=50,
                    price=25,
                    fee=0,
                    cash_before=900,
                    cash_after=850,
                    holding_before=0,
                    holding_after=2,
                    minute=20,
                ),
            ),
            prices={
                "TLEI": 12,
                "FSEI": 30,
            },
        ),
    )

    journey = build_participant_decision_journey(
        target_stock_id="TLEI",
        initial_cash=1000,
        initial_holdings={},
        initial_portfolio_value=1000,
        periods=periods,
    )

    p1 = journey.periods[0]

    # 850 + 10*12 + 2*30 = 1030
    assert p1.portfolio_end.portfolio_value == pytest.approx(
        1030
    )
    assert p1.period_pnl == pytest.approx(30)
    assert dict(p1.portfolio_end.holdings) == {
        "FSEI": 2,
        "TLEI": 10,
    }


def test_fee_is_not_subtracted_twice():
    periods = (
        _period(
            1,
            judgements=(
                _judgement(
                    1,
                    action="BUY",
                    confidence=50,
                    minute=0,
                ),
                _judgement(
                    1,
                    action="BUY",
                    confidence=55,
                    minute=5,
                ),
            ),
            transactions=(
                _transaction(
                    1,
                    transaction_id="tx-fee",
                    stock_id="TLEI",
                    action="BUY",
                    units=10,
                    notional=100.0,
                    price=10.0,
                    fee=0.10,
                    cash_before=1000.0,
                    cash_after=899.90,
                    holding_before=0,
                    holding_after=10,
                ),
            ),
            prices={"TLEI": 10.0},
        ),
    )

    journey = build_participant_decision_journey(
        target_stock_id="TLEI",
        initial_cash=1000.0,
        initial_holdings={},
        initial_portfolio_value=1000.0,
        periods=periods,
    )

    p1 = journey.periods[0]

    # cash_after already contains the fee:
    # 899.90 + 10*10 = 999.90
    assert p1.portfolio_end.portfolio_value == pytest.approx(
        999.90
    )
    assert p1.period_pnl == pytest.approx(-0.10)
    assert p1.pnl_direction == PNL_LOSS


def test_multiple_same_period_transactions_are_preserved_and_mixed():
    periods = (
        _period(
            1,
            judgements=(
                _judgement(
                    1,
                    action="HOLD",
                    confidence=50,
                    minute=0,
                ),
                _judgement(
                    1,
                    action="HOLD",
                    confidence=50,
                    minute=5,
                ),
            ),
            transactions=(
                _transaction(
                    1,
                    transaction_id="tx-buy",
                    stock_id="TLEI",
                    action="BUY",
                    units=10,
                    notional=100,
                    price=10,
                    fee=0,
                    cash_before=1000,
                    cash_after=900,
                    holding_before=0,
                    holding_after=10,
                    minute=10,
                ),
                _transaction(
                    1,
                    transaction_id="tx-sell",
                    stock_id="TLEI",
                    action="SELL",
                    units=2,
                    notional=20,
                    price=10,
                    fee=0,
                    cash_before=900,
                    cash_after=920,
                    holding_before=10,
                    holding_after=8,
                    minute=20,
                ),
            ),
            prices={"TLEI": 10},
        ),
    )

    journey = build_participant_decision_journey(
        target_stock_id="TLEI",
        initial_cash=1000,
        initial_holdings={},
        initial_portfolio_value=1000,
        periods=periods,
    )

    p1 = journey.periods[0]

    assert len(p1.transactions) == 2
    assert p1.behaviour_summary == BEHAVIOUR_MIXED
    assert dict(p1.holding_changes) == {
        "TLEI": 8,
    }
    assert p1.portfolio_end.portfolio_value == pytest.approx(
        1000
    )
    assert p1.pnl_direction == PNL_FLAT


def test_sell_only_classification():
    periods = (
        _period(
            1,
            judgements=(
                _judgement(
                    1,
                    action="SELL",
                    confidence=60,
                    minute=0,
                ),
                _judgement(
                    1,
                    action="SELL",
                    confidence=65,
                    minute=5,
                ),
            ),
            transactions=(
                _transaction(
                    1,
                    transaction_id="tx-sell",
                    stock_id="TLEI",
                    action="SELL",
                    units=2,
                    notional=20,
                    price=10,
                    fee=0,
                    cash_before=900,
                    cash_after=920,
                    holding_before=10,
                    holding_after=8,
                ),
            ),
            prices={"TLEI": 10},
        ),
    )

    journey = build_participant_decision_journey(
        target_stock_id="TLEI",
        initial_cash=900,
        initial_holdings={"TLEI": 10},
        initial_portfolio_value=1000,
        periods=periods,
    )

    assert (
        journey.periods[0].behaviour_summary
        == BEHAVIOUR_SELL_ONLY
    )


def test_no_transaction_counts_as_no_trade_only_when_round_locked():
    periods = (
        _period(
            1,
            judgements=(
                _judgement(
                    1,
                    action="HOLD",
                    confidence=50,
                    minute=0,
                ),
                _judgement(
                    1,
                    action="HOLD",
                    confidence=50,
                    minute=5,
                ),
            ),
            prices={},
            round_locked=False,
        ),
    )

    with pytest.raises(
        ParticipantDecisionJourneyError,
        match="behaviour-locked",
    ):
        build_participant_decision_journey(
            target_stock_id="TLEI",
            initial_cash=1000,
            initial_holdings={},
            initial_portfolio_value=1000,
            periods=periods,
        )


def test_transaction_is_forbidden_when_trading_disabled():
    periods = (
        _period(
            1,
            judgements=(
                _judgement(
                    1,
                    action="BUY",
                    confidence=50,
                    minute=0,
                ),
                _judgement(
                    1,
                    action="BUY",
                    confidence=55,
                    minute=5,
                ),
            ),
            transactions=(
                _transaction(
                    1,
                    transaction_id="tx-invalid",
                    stock_id="TLEI",
                    action="BUY",
                    units=1,
                    notional=10,
                    price=10,
                    fee=0,
                    cash_before=1000,
                    cash_after=990,
                    holding_before=0,
                    holding_after=1,
                ),
            ),
            prices={"TLEI": 10},
            trading_enabled=False,
        ),
    )

    with pytest.raises(
        ParticipantDecisionJourneyError,
        match="trading was disabled",
    ):
        build_participant_decision_journey(
            target_stock_id="TLEI",
            initial_cash=1000,
            initial_holdings={},
            initial_portfolio_value=1000,
            periods=periods,
        )


def test_cash_continuity_mismatch_fails_closed():
    periods = (
        _period(
            1,
            judgements=(
                _judgement(
                    1,
                    action="BUY",
                    confidence=50,
                    minute=0,
                ),
                _judgement(
                    1,
                    action="BUY",
                    confidence=55,
                    minute=5,
                ),
            ),
            transactions=(
                _transaction(
                    1,
                    transaction_id="tx-bad-cash",
                    stock_id="TLEI",
                    action="BUY",
                    units=1,
                    notional=10,
                    price=10,
                    fee=0,
                    cash_before=999,
                    cash_after=989,
                    holding_before=0,
                    holding_after=1,
                ),
            ),
            prices={"TLEI": 10},
        ),
    )

    with pytest.raises(
        ParticipantDecisionJourneyError,
        match="cash continuity",
    ):
        build_participant_decision_journey(
            target_stock_id="TLEI",
            initial_cash=1000,
            initial_holdings={},
            initial_portfolio_value=1000,
            periods=periods,
        )


def test_holding_continuity_mismatch_fails_closed():
    periods = (
        _period(
            1,
            judgements=(
                _judgement(
                    1,
                    action="BUY",
                    confidence=50,
                    minute=0,
                ),
                _judgement(
                    1,
                    action="BUY",
                    confidence=55,
                    minute=5,
                ),
            ),
            transactions=(
                _transaction(
                    1,
                    transaction_id="tx-bad-holding",
                    stock_id="TLEI",
                    action="BUY",
                    units=1,
                    notional=10,
                    price=10,
                    fee=0,
                    cash_before=1000,
                    cash_after=990,
                    holding_before=2,
                    holding_after=3,
                ),
            ),
            prices={"TLEI": 10},
        ),
    )

    with pytest.raises(
        ParticipantDecisionJourneyError,
        match="holding continuity",
    ):
        build_participant_decision_journey(
            target_stock_id="TLEI",
            initial_cash=1000,
            initial_holdings={},
            initial_portfolio_value=1000,
            periods=periods,
        )


def test_missing_canonical_price_for_held_asset_fails_closed():
    periods = (
        _period(
            1,
            judgements=(
                _judgement(
                    1,
                    action="BUY",
                    confidence=50,
                    minute=0,
                ),
                _judgement(
                    1,
                    action="BUY",
                    confidence=55,
                    minute=5,
                ),
            ),
            transactions=(
                _transaction(
                    1,
                    transaction_id="tx-buy",
                    stock_id="TLEI",
                    action="BUY",
                    units=1,
                    notional=10,
                    price=10,
                    fee=0,
                    cash_before=1000,
                    cash_after=990,
                    holding_before=0,
                    holding_after=1,
                ),
            ),
            prices={},
        ),
    )

    with pytest.raises(
        ParticipantDecisionJourneyError,
        match="price missing",
    ):
        build_participant_decision_journey(
            target_stock_id="TLEI",
            initial_cash=1000,
            initial_holdings={},
            initial_portfolio_value=1000,
            periods=periods,
        )


def test_judgement_schedule_is_protocol_specific_without_internal_labels():
    p1 = _period(
        1,
        judgements=(
            _judgement(
                1,
                action="HOLD",
                confidence=50,
                minute=0,
            ),
            _judgement(
                1,
                action="BUY",
                confidence=60,
                minute=5,
            ),
        ),
        prices={},
    )

    p2 = _period(
        2,
        judgements=(
            _judgement(
                2,
                action="HOLD",
                confidence=50,
                minute=0,
            ),
        ),
        prices={},
    )

    with pytest.raises(
        ParticipantDecisionJourneyError,
        match="requires 0 formal judgement",
    ):
        build_participant_decision_journey(
            target_stock_id="TLEI",
            initial_cash=1000,
            initial_holdings={},
            initial_portfolio_value=1000,
            periods=(p1, p2),
        )


def test_periods_must_start_at_p1_and_be_contiguous():
    with pytest.raises(
        ParticipantDecisionJourneyError,
        match="begin at P1",
    ):
        build_participant_decision_journey(
            target_stock_id="TLEI",
            initial_cash=1000,
            initial_holdings={},
            initial_portfolio_value=1000,
            periods=(
                JourneyPeriodInput(
                    period_number=2,
                    agent_world_date=DATES[1],
                    market_open=True,
                    participant_trading_enabled=True,
                    round_locked=True,
                    judgements=(),
                    transactions=(),
                    canonical_close_prices={},
                ),
            ),
        )


def test_feedback_boundaries_are_p4_p11_p15():
    periods = []

    for number in range(1, 16):
        if number == 1:
            judgements = (
                _judgement(
                    1,
                    action="HOLD",
                    confidence=50,
                    minute=0,
                ),
                _judgement(
                    1,
                    action="HOLD",
                    confidence=50,
                    minute=5,
                ),
            )
        elif number == 8:
            judgements = (
                _judgement(
                    8,
                    action="HOLD",
                    confidence=50,
                    minute=0,
                ),
                _judgement(
                    8,
                    action="HOLD",
                    confidence=50,
                    minute=5,
                ),
            )
        elif number == 15:
            judgements = (
                _judgement(
                    15,
                    action="HOLD",
                    confidence=50,
                    minute=0,
                ),
            )
        else:
            judgements = ()

        periods.append(
            _period(
                number,
                judgements=judgements,
                prices={},
            )
        )

    journey = build_participant_decision_journey(
        target_stock_id="TLEI",
        initial_cash=1000,
        initial_holdings={},
        initial_portfolio_value=1000,
        periods=periods,
    )

    boundaries = {
        period.period_number: period.feedback_boundary
        for period in journey.periods
        if period.feedback_boundary != FEEDBACK_NONE
    }

    assert boundaries == {
        4: FEEDBACK_DECISION,
        11: FEEDBACK_DECISION,
        15: FEEDBACK_FINAL,
    }


def test_early_journey_contains_no_future_periods():
    periods = []

    for number in range(1, 5):
        judgements = ()

        if number == 1:
            judgements = (
                _judgement(
                    1,
                    action="HOLD",
                    confidence=50,
                    minute=0,
                ),
                _judgement(
                    1,
                    action="HOLD",
                    confidence=55,
                    minute=5,
                ),
            )

        periods.append(
            _period(
                number,
                judgements=judgements,
                prices={},
            )
        )

    journey = build_participant_decision_journey(
        target_stock_id="TLEI",
        initial_cash=1000,
        initial_holdings={},
        initial_portfolio_value=1000,
        periods=periods,
    )

    assert [
        period.period_number
        for period in journey.periods
    ] == [1, 2, 3, 4]


def test_to_dict_is_structured_and_contains_no_internal_j_labels():
    periods = (
        _period(
            1,
            judgements=(
                _judgement(
                    1,
                    action="HOLD",
                    confidence=50,
                    minute=0,
                ),
                _judgement(
                    1,
                    action="BUY",
                    confidence=55,
                    minute=5,
                ),
            ),
            prices={},
        ),
    )

    journey = build_participant_decision_journey(
        target_stock_id="TLEI",
        initial_cash=1000,
        initial_holdings={},
        initial_portfolio_value=1000,
        periods=periods,
    )

    payload = journey.to_dict()

    assert payload["journey_version"] == JOURNEY_VERSION
    assert payload["periods"][0]["period_number"] == 1

    rendered = repr(payload)

    for forbidden in (
        "J0",
        "J1",
        "J2",
        "J3",
        "J4",
        "episode_id",
        "truth_label",
        "correct_answer",
        "expected_action",
    ):
        assert forbidden not in rendered
