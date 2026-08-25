#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select, update

from marketlens.episode.contract import EPISODE_IDS
from marketlens.experiment.protocol import load_protocol
from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.measurement.runtime_recorder import ParticipantRuntimeEventRecorder
from marketlens.human.schemas import (
    DecisionAction,
    DecisionRead,
    PortfolioAction,
    PortfolioTransactionRead,
    SessionCreate,
)
from marketlens.human.services.episode_assignment_service import EpisodeAssignmentService
from marketlens.human.services.session_service import SessionService
from marketlens.human.services.trusted_context_service import TrustedParticipantContextResolver
from marketlens.human.stores.episode_assignment_store import EpisodeAssignmentStore
from marketlens.human.stores.session_store import SessionStore
from marketlens.market.status import TradingCalendar
from marketlens.persistence.database import Database
from marketlens.persistence.schema import participant_portfolios, sessions


def main() -> None:
    protocol = load_protocol()
    checkpoint = next(row for row in protocol["timeline"] if row.get("experiment_step") is not None)

    with tempfile.TemporaryDirectory(prefix="marketlens-phase14b3a-") as temp_dir:
        root = Path(temp_dir)
        human_db = Database(root / "human.db")
        session_service = SessionService(SessionStore(human_db))
        session = session_service.create(
            SessionCreate(participant_id="PREFLIGHT-P001", request_id="session-request-001")
        )
        with human_db.connect() as connection:
            connection.execute(
                update(sessions)
                .where(sessions.c.session_id == session.session_id)
                .values(
                    current_step=int(checkpoint["experiment_step"]),
                    current_date=str(checkpoint["agent_world_date"]),
                )
            )
            session_before = dict(
                connection.execute(
                    select(sessions).where(sessions.c.session_id == session.session_id)
                ).mappings().one()
            )
            portfolio_before = dict(
                connection.execute(
                    select(participant_portfolios).where(
                        participant_portfolios.c.session_id == session.session_id
                    )
                ).mappings().one()
            )

        assignment_service = EpisodeAssignmentService(EpisodeAssignmentStore(human_db))
        assignment_service.bind(session.session_id, EPISODE_IDS[0])
        context = TrustedParticipantContextResolver(
            sessions=session_service,
            assignments=assignment_service,
            calendar=TradingCalendar(),
            protocol=protocol,
        )
        event_store = ParticipantEventStore(root / "participant_events.db")
        recorder = ParticipantRuntimeEventRecorder(store=event_store, context=context)

        submitted_at = datetime(2026, 8, 25, 15, 30, tzinfo=timezone.utc)
        decision = DecisionRead(
            decision_id="DEC-PREFLIGHT-001",
            session_id=session.session_id,
            request_id="decision-request-001",
            step=int(checkpoint["experiment_step"]),
            stock_id="MEI",
            action=DecisionAction.HOLD,
            confidence=75.0,
            evidence_sources=["background"],
            rationale="preflight domain read model",
            submitted_at=submitted_at,
        )
        transaction = PortfolioTransactionRead(
            transaction_id="TX-PREFLIGHT-001",
            session_id=session.session_id,
            request_id="transaction-request-001",
            step=int(checkpoint["experiment_step"]),
            stock_id="MEI",
            action=PortfolioAction.BUY,
            requested_amount=100.0,
            requested_units=1.0,
            executed_units=1,
            executed_notional=100.0,
            settlement_price=100.0,
            price_date=str(checkpoint["agent_world_date"]),
            transaction_cost_bps=0.0,
            fee=0.0,
            cash_before=1000.0,
            cash_after=900.0,
            holding_before=0,
            holding_after=1,
            portfolio_value_before=1000.0,
            portfolio_value_after=1000.0,
            weight_before=0.0,
            weight_after=0.1,
            submitted_at=submitted_at,
        )

        recorder.record_decision(decision)
        recorder.record_transaction(transaction)
        recorder.record_decision(decision)
        recorder.record_transaction(transaction)
        rows = event_store.list_for_session(session.session_id)

        with human_db.connect() as connection:
            session_after = dict(
                connection.execute(
                    select(sessions).where(sessions.c.session_id == session.session_id)
                ).mappings().one()
            )
            portfolio_after = dict(
                connection.execute(
                    select(participant_portfolios).where(
                        participant_portfolios.c.session_id == session.session_id
                    )
                ).mappings().one()
            )

        event_types = {row["event_type"] for row in rows}
        expected_types = {
            "JUDGEMENT_SUBMITTED",
            "CONFIDENCE_RECORDED",
            "ORDER_SUBMITTED",
            "TRADE_SETTLED",
            "PORTFOLIO_STATE_RECORDED",
        }
        checks = {
            "five_domain_event_types_recorded": event_types == expected_types,
            "retry_idempotent": len(rows) == 5,
            "decision_domain_reference_only": {
                row["domain_record_id"]
                for row in rows
                if row["event_type"] in {"JUDGEMENT_SUBMITTED", "CONFIDENCE_RECORDED"}
            }
            == {"DEC-PREFLIGHT-001"},
            "transaction_domain_reference_only": {
                row["domain_record_id"]
                for row in rows
                if row["event_type"] in {
                    "ORDER_SUBMITTED",
                    "TRADE_SETTLED",
                    "PORTFOLIO_STATE_RECORDED",
                }
            }
            == {"TX-PREFLIGHT-001"},
            "participant_identity_server_derived": {row["participant_id"] for row in rows}
            == {"PREFLIGHT-P001"},
            "episode_identity_server_derived": {row["episode_id"] for row in rows}
            == {EPISODE_IDS[0]},
            "participant_session_mutated_by_recorder": session_before != session_after,
            "participant_portfolio_mutated_by_recorder": portfolio_before != portfolio_after,
        }
        passed = (
            all(
                value
                for key, value in checks.items()
                if not key.endswith("mutated_by_recorder")
            )
            and not checks["participant_session_mutated_by_recorder"]
            and not checks["participant_portfolio_mutated_by_recorder"]
        )

        report = {
            "status": "PASS" if passed else "FAIL",
            "evidence_class": "NON-FORMAL / PHASE 14B3A DOMAIN EVENT RECORDER PREFLIGHT / ZERO-LLM",
            "llm_api_calls": 0,
            "formal_experiment_evidence": False,
            "runtime_router_wiring_added": False,
            "controlled_stimulus_delivery_added": False,
            "background_exposure_wiring_added": False,
            "random_allocator_added": False,
            "domain_source_of_truth_duplicated": False,
            "event_count_after_replay": len(rows),
            **checks,
            "agent_world_db_written": False,
            "forum_db_written": False,
            "note": "B3A freezes domain-event recording semantics only. HTTP/runtime wiring and participant-visible exposure delivery remain deferred because the current backend has no formal automatic episode allocation or participant-facing controlled-stimulus delivery path.",
        }
        print("NON-FORMAL / PHASE 14B3A DOMAIN EVENT RECORDER PREFLIGHT / ZERO-LLM")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        event_store.dispose()
        human_db.dispose()
        if not passed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
