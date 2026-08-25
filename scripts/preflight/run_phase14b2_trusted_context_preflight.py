#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select, update

from marketlens.episode.contract import EPISODE_IDS, EPISODE_POOL_ID
from marketlens.experiment.protocol import load_protocol
from marketlens.human.schemas import SessionCreate
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

    with tempfile.TemporaryDirectory(prefix="marketlens-phase14b2-") as temp_dir:
        db = Database(Path(temp_dir) / "human.db")
        session_service = SessionService(SessionStore(db))
        session = session_service.create(SessionCreate(participant_id="PREFLIGHT-P001", request_id="session-request-001"))

        with db.connect() as connection:
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

        assignment_service = EpisodeAssignmentService(EpisodeAssignmentStore(db))
        assignment_service.bind(session.session_id, EPISODE_IDS[0])

        resolver = TrustedParticipantContextResolver(
            sessions=session_service,
            assignments=assignment_service,
            calendar=TradingCalendar(),
            protocol=protocol,
        )
        context = resolver.resolve(session.session_id)

        with db.connect() as connection:
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

        expected_open = checkpoint["market_status"] == "OPEN"
        checks = {
            "participant_identity_server_derived": context.participant_id == "PREFLIGHT-P001",
            "episode_identity_server_derived": context.episode_id == EPISODE_IDS[0],
            "episode_pool_identity_frozen": context.episode_pool_id == EPISODE_POOL_ID,
            "experiment_step_server_derived": context.experiment_step == int(checkpoint["experiment_step"]),
            "agent_world_date_protocol_bound": context.agent_world_date == str(checkpoint["agent_world_date"]),
            "market_status_authoritative": context.market_open == expected_open,
            "participant_session_mutated_by_resolver": session_before != session_after,
            "participant_portfolio_mutated_by_resolver": portfolio_before != portfolio_after,
        }

        passed = (
            all(value for key, value in checks.items() if not key.endswith("mutated_by_resolver"))
            and not checks["participant_session_mutated_by_resolver"]
            and not checks["participant_portfolio_mutated_by_resolver"]
        )

        report = {
            "status": "PASS" if passed else "FAIL",
            "evidence_class": "NON-FORMAL / PHASE 14B2 TRUSTED PARTICIPANT CONTEXT PREFLIGHT / ZERO-LLM",
            "llm_api_calls": 0,
            "formal_experiment_evidence": False,
            "formal_participant_assignment_performed": False,
            "random_allocator_added": False,
            "public_context_override_api_added": False,
            "client_supplied_provenance_fields": 0,
            "participant_events_db_written": False,
            "agent_world_db_written": False,
            "forum_db_written": False,
            "protocol_modified": False,
            "stimulus_timing_modified": False,
            **checks,
            "resolved_context": {
                "session_id": context.session_id,
                "participant_id": context.participant_id,
                "episode_pool_id": context.episode_pool_id,
                "episode_id": context.episode_id,
                "protocol_version": context.protocol_version,
                "experiment_step": context.experiment_step,
                "agent_world_date": context.agent_world_date,
                "market_open": context.market_open,
                "participant_trading_enabled": context.participant_trading_enabled,
            },
            "note": "Read-only trusted context only. Runtime event writing remains deferred to Phase 14B3.",
        }
        print("NON-FORMAL / PHASE 14B2 TRUSTED PARTICIPANT CONTEXT PREFLIGHT / ZERO-LLM")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if not passed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
