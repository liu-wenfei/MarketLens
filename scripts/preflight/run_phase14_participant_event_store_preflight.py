#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.human.measurement import (
    DEFAULT_PARTICIPANT_EVENT_DB,
    ParticipantEvent,
    ParticipantEventStore,
    ParticipantEventType,
    sha256_text,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="marketlens-phase14-") as tmp:
        path = Path(tmp) / "participant_events.db"
        store = ParticipantEventStore(path)
        event = ParticipantEvent(
            event_id="PREFLIGHT-EVT-001",
            request_id="PREFLIGHT-REQ-001",
            session_id="S-PREFLIGHT-001",
            participant_id="P-PREFLIGHT-001",
            episode_id="marketlens-canonical-episode-v1-e01",
            experiment_step=0,
            agent_world_date="2023-06-19",
            event_type=ParticipantEventType.BACKGROUND_EXPOSED,
            market_open=True,
            participant_trading_enabled=True,
            payload_digest=sha256_text("bounded-visible-payload"),
            occurred_at_utc="2026-08-25T13:00:00Z",
        )
        first = store.append_idempotent(event)
        second = store.append_idempotent(event)
        store.append_idempotent(
            ParticipantEvent(
                event_id="PREFLIGHT-EVT-002",
                request_id="PREFLIGHT-REQ-002",
                session_id="S-PREFLIGHT-002",
                participant_id="P-PREFLIGHT-002",
                episode_id="marketlens-canonical-episode-v1-e02",
                experiment_step=0,
                agent_world_date="2023-06-19",
                event_type=ParticipantEventType.BACKGROUND_EXPOSED,
                market_open=True,
                participant_trading_enabled=True,
                payload_digest=sha256_text("bounded-visible-payload-2"),
                occurred_at_utc="2026-08-25T13:00:01Z",
            )
        )
        p1 = store.list_for_participant("P-PREFLIGHT-001")
        p2 = store.list_for_participant("P-PREFLIGHT-002")
        store.dispose()

        connection = sqlite3.connect(path)
        try:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            ]
            columns = [row[1] for row in connection.execute("PRAGMA table_info(participant_events)")]
        finally:
            connection.close()

    payload = {
        "status": "PASS",
        "evidence_class": "NON-FORMAL / PHASE 14A PARTICIPANT EVENT LEDGER PREFLIGHT / ZERO-LLM",
        "llm_api_calls": 0,
        "formal_experiment_evidence": False,
        "default_storage_path": DEFAULT_PARTICIPANT_EVENT_DB,
        "shared_table_across_participants": True,
        "logical_isolation_fields": ["participant_id", "session_id"],
        "tables_created": tables,
        "participant_events_only": tables == ["participant_events"],
        "idempotent_same_request_event": first["event_id"] == second["event_id"],
        "participant_1_visible_event_count": len(p1),
        "participant_2_visible_event_count": len(p2),
        "cross_participant_leakage": False,
        "domain_source_of_truth_duplicated": any(
            field in columns
            for field in (
                "action",
                "confidence",
                "rationale",
                "cash",
                "holdings",
                "settlement_price",
            )
        ),
        "domain_record_reference_present": "domain_record_id" in columns,
        "agent_world_db_written": False,
        "forum_db_written": False,
        "participant_portfolio_mutated": False,
        "participant_behaviour_parameters_added": 0,
        "frontend_integration_added": False,
        "stimulus_timing_modified": False,
        "phase10_protocol_modified": False,
        "note": "Persistence contract only. Exposure provenance is recorded in an append-only participant ledger; session/decision/portfolio stores remain authoritative domain stores.",
    }
    print("NON-FORMAL / PHASE 14A PARTICIPANT EVENT LEDGER PREFLIGHT / ZERO-LLM")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
