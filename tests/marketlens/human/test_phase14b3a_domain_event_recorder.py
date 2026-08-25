from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.measurement.runtime_recorder import (
    ParticipantRuntimeEventInvariantError,
    ParticipantRuntimeEventRecorder,
)
from marketlens.human.schemas import (
    DecisionAction,
    DecisionRead,
    PortfolioAction,
    PortfolioTransactionRead,
)
from marketlens.human.services.trusted_context_service import TrustedParticipantContext


class _ContextResolver:
    def __init__(self, context: TrustedParticipantContext):
        self.value = context

    def resolve(self, session_id: str) -> TrustedParticipantContext:
        assert session_id == self.value.session_id
        return self.value


def _context(**overrides) -> TrustedParticipantContext:
    values = {
        "session_id": "S001",
        "participant_id": "P001",
        "assignment_id": "A001",
        "episode_pool_id": "marketlens-canonical-episode-pool-v1",
        "episode_id": "marketlens-canonical-episode-v1-e01",
        "assignment_method": "balanced_random_across_episode_pool",
        "assignment_version": "phase14b1-v1",
        "protocol_version": "1.1",
        "experiment_step": 0,
        "agent_world_date": "2023-06-19",
        "market_open": True,
        "market_status_reason": "open",
        "current_market_date": "2023-06-19",
        "market_state_date": "2023-06-19",
        "participant_trading_enabled": True,
    }
    values.update(overrides)
    return TrustedParticipantContext(**values)


def _decision(**overrides) -> DecisionRead:
    values = {
        "decision_id": "DEC-001",
        "session_id": "S001",
        "request_id": "REQ-DEC-001",
        "step": 0,
        "stock_id": "MEI",
        "action": DecisionAction.HOLD,
        "confidence": 72.0,
        "evidence_sources": ["background"],
        "rationale": "test",
        "submitted_at": datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return DecisionRead(**values)


def _transaction(**overrides) -> PortfolioTransactionRead:
    values = {
        "transaction_id": "TX-001",
        "session_id": "S001",
        "request_id": "REQ-TX-001",
        "step": 0,
        "stock_id": "MEI",
        "action": PortfolioAction.BUY,
        "requested_amount": 100.0,
        "requested_units": 1.0,
        "executed_units": 1,
        "executed_notional": 100.0,
        "settlement_price": 100.0,
        "price_date": "2023-06-19",
        "transaction_cost_bps": 0.0,
        "fee": 0.0,
        "cash_before": 1000.0,
        "cash_after": 900.0,
        "holding_before": 0,
        "holding_after": 1,
        "portfolio_value_before": 1000.0,
        "portfolio_value_after": 1000.0,
        "weight_before": 0.0,
        "weight_after": 0.1,
        "submitted_at": datetime(2026, 8, 25, 15, 1, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return PortfolioTransactionRead(**values)


def _recorder(tmp_path: Path, *, context: TrustedParticipantContext | None = None):
    store = ParticipantEventStore(tmp_path / "participant_events.db")
    recorder = ParticipantRuntimeEventRecorder(
        store=store,
        context=_ContextResolver(context or _context()),
    )
    return store, recorder


def test_decision_records_judgement_and_confidence_by_reference(tmp_path: Path) -> None:
    store, recorder = _recorder(tmp_path)
    recorder.record_decision(_decision())
    rows = store.list_for_session("S001")
    assert {row["event_type"] for row in rows} == {
        "JUDGEMENT_SUBMITTED",
        "CONFIDENCE_RECORDED",
    }
    assert {row["domain_record_id"] for row in rows} == {"DEC-001"}
    assert {row["request_id"] for row in rows} == {"REQ-DEC-001"}
    store.dispose()


def test_decision_retry_is_idempotent_with_deterministic_event_identity(tmp_path: Path) -> None:
    store, recorder = _recorder(tmp_path)
    first = recorder.record_decision(_decision())
    second = recorder.record_decision(_decision())
    assert [row["event_id"] for row in first] == [row["event_id"] for row in second]
    assert len(store.list_for_session("S001")) == 2
    store.dispose()


def test_decision_values_are_not_duplicated_into_ledger(tmp_path: Path) -> None:
    store, recorder = _recorder(tmp_path)
    recorder.record_decision(_decision(confidence=91.0, rationale="domain source only"))
    row = store.list_for_session("S001")[0]
    assert "confidence" not in row
    assert "rationale" not in row
    assert "action" not in row
    store.dispose()


def test_transaction_records_order_trade_and_resulting_portfolio_state(tmp_path: Path) -> None:
    store, recorder = _recorder(tmp_path)
    recorder.record_transaction(_transaction())
    rows = store.list_for_session("S001")
    assert {row["event_type"] for row in rows} == {
        "ORDER_SUBMITTED",
        "TRADE_SETTLED",
        "PORTFOLIO_STATE_RECORDED",
    }
    assert {row["domain_record_id"] for row in rows} == {"TX-001"}
    assert {row["request_id"] for row in rows} == {"REQ-TX-001"}
    store.dispose()


def test_transaction_retry_is_idempotent(tmp_path: Path) -> None:
    store, recorder = _recorder(tmp_path)
    recorder.record_transaction(_transaction())
    recorder.record_transaction(_transaction())
    assert len(store.list_for_session("S001")) == 3
    store.dispose()


def test_recorder_rejects_domain_step_drift(tmp_path: Path) -> None:
    store, recorder = _recorder(tmp_path)
    with pytest.raises(ParticipantRuntimeEventInvariantError, match="experiment step"):
        recorder.record_decision(_decision(step=1))
    assert store.list_for_session("S001") == ()
    store.dispose()


def test_recorder_uses_server_derived_participant_episode_and_market_context(tmp_path: Path) -> None:
    trusted = _context(
        participant_id="SERVER-P",
        episode_id="marketlens-canonical-episode-v1-e03",
        market_open=False,
        participant_trading_enabled=False,
    )
    store, recorder = _recorder(tmp_path, context=trusted)
    recorder.record_decision(_decision())
    rows = store.list_for_session("S001")
    assert {row["participant_id"] for row in rows} == {"SERVER-P"}
    assert {row["episode_id"] for row in rows} == {"marketlens-canonical-episode-v1-e03"}
    assert {bool(row["market_open"]) for row in rows} == {False}
    assert {bool(row["participant_trading_enabled"]) for row in rows} == {False}
    store.dispose()


def test_naive_domain_timestamp_fails_closed(tmp_path: Path) -> None:
    store, recorder = _recorder(tmp_path)
    with pytest.raises(ParticipantRuntimeEventInvariantError, match="timezone-aware"):
        recorder.record_decision(
            _decision(submitted_at=datetime(2026, 8, 25, 15, 0))
        )
    assert store.list_for_session("S001") == ()
    store.dispose()
