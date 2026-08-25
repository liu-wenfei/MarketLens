#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import inspect, select

from marketlens.episode.contract import EPISODE_IDS, EPISODE_POOL_ID
from marketlens.human.services.episode_assignment_service import (
    ASSIGNMENT_BINDING_VERSION,
    FORMAL_ASSIGNMENT_METHOD,
    EpisodeAssignmentConflictError,
    EpisodeAssignmentService,
)
from marketlens.human.stores.episode_assignment_store import EpisodeAssignmentStore
from marketlens.human.stores.session_store import SessionStore
from marketlens.persistence.database import Database
from marketlens.persistence.schema import participant_portfolios


def main() -> None:
    print("NON-FORMAL / PHASE 14B1 EPISODE ASSIGNMENT BINDING PREFLIGHT / ZERO-LLM")
    with tempfile.TemporaryDirectory(prefix="marketlens-phase14b1-") as tmp:
        db = Database(Path(tmp) / "human.db")
        sessions = SessionStore(db)
        assignments = EpisodeAssignmentService(EpisodeAssignmentStore(db))

        sessions.create_idempotent(
            session_id="S001",
            participant_id="P001",
            request_id="create-S001",
            created_at="2026-08-25T12:00:00+00:00",
            initial_cash=10000.0,
        )
        sessions.create_idempotent(
            session_id="S002",
            participant_id="P002",
            request_id="create-S002",
            created_at="2026-08-25T12:00:00+00:00",
            initial_cash=10000.0,
        )

        with db.connect() as connection:
            portfolio_before = dict(
                connection.execute(
                    select(participant_portfolios).where(
                        participant_portfolios.c.session_id == "S001"
                    )
                ).mappings().one()
            )
        session_before = dict(sessions.get("S001"))

        first = assignments.bind("S001", EPISODE_IDS[0])
        replay = assignments.bind("S001", EPISODE_IDS[0])
        second = assignments.bind("S002", EPISODE_IDS[1])

        with db.connect() as connection:
            portfolio_after = dict(
                connection.execute(
                    select(participant_portfolios).where(
                        participant_portfolios.c.session_id == "S001"
                    )
                ).mappings().one()
            )
        session_after = dict(sessions.get("S001"))

        conflict_blocked = False
        try:
            assignments.bind("S001", EPISODE_IDS[1])
        except EpisodeAssignmentConflictError:
            conflict_blocked = True

        report = {
            "status": "PASS" if (
                conflict_blocked
                and first.assignment_id == replay.assignment_id
                and session_before == session_after
                and portfolio_before == portfolio_after
            ) else "FAIL",
            "evidence_class": "NON-FORMAL / PHASE 14B1 EPISODE ASSIGNMENT BINDING PREFLIGHT / ZERO-LLM",
            "llm_api_calls": 0,
            "formal_experiment_evidence": False,
            "formal_participant_assignment_performed": False,
            "random_allocator_added": False,
            "random_draws": 0,
            "human_domain_table": "participant_episode_assignments",
            "table_present": "participant_episode_assignments" in inspect(db.engine).get_table_names(),
            "episode_pool_id": EPISODE_POOL_ID,
            "episode_ids_reused_from_phase13c_contract": list(EPISODE_IDS),
            "assignment_method_contract": FORMAL_ASSIGNMENT_METHOD,
            "assignment_binding_version": ASSIGNMENT_BINDING_VERSION,
            "participant_identity_server_derived": first.participant_id == "P001",
            "one_assignment_per_session": conflict_blocked,
            "idempotent_same_binding": first.assignment_id == replay.assignment_id,
            "cross_session_isolation": first.session_id != second.session_id and first.participant_id != second.participant_id,
            "public_assignment_api_added": False,
            "participant_events_db_written": False,
            "agent_world_db_written": False,
            "forum_db_written": False,
            "participant_session_mutated_by_assignment": session_before != session_after,
            "participant_portfolio_mutated_by_assignment": portfolio_before != portfolio_after,
            "note": "Binding only. This phase persists an already-chosen canonical episode for a participant session; it does not implement or execute balanced random allocation.",
        }
        print(json.dumps(report, indent=2))
        db.dispose()
        if report["status"] != "PASS":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
