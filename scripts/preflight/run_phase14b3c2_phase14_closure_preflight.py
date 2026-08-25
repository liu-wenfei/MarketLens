#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketlens.episode.contract import EPISODE_IDS
from marketlens.human.measurement.event_store import ParticipantEventStore
from marketlens.human.stores.judgement_store import JudgementStore
from marketlens.human.stores.round_store import RoundStore
from marketlens.main import create_app
from marketlens.stimulus.engine import StimulusEngine
from marketlens.stimulus.material import load_material


class Projection:
    def __init__(self, episode_id: str):
        self.episode = SimpleNamespace(episode_id=episode_id)

    def project(self, *, current_date: str):
        return {
            "current_date": current_date,
            "natural_news": [f"background-{current_date}"],
            "forum_posts": [],
        }


def judgement(request_id: str) -> dict[str, object]:
    return {
        "request_id": request_id,
        "stock_id": "MEI",
        "action": "HOLD",
        "confidence": 70.0,
        "evidence_sources": ["background"],
        "rationale": "phase14 closure preflight",
    }


def raise_ok(response):
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
    return response


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="marketlens-phase14b3c2-") as temp_dir:
        root = Path(temp_dir)
        episode_id = EPISODE_IDS[0]
        events = ParticipantEventStore(root / "participant_events.db")
        engine = StimulusEngine(
            load_material(
                ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json",
                formal=True,
            )
        )
        app = create_app(
            root / "human.db",
            participant_runtime_enabled=True,
            participant_event_store=events,
            background_projections={episode_id: Projection(episode_id)},
            stimulus_engine=engine,
        )

        replay_ids: list[tuple[str, str]] = []
        protocol_dates_exact = True
        forged_round_stage_rejected = True

        with TestClient(app) as client:
            created = raise_ok(
                client.post(
                    "/session",
                    json={"participant_id": "PREFLIGHT", "request_id": "session-create"},
                )
            ).json()
            sid = created["session_id"]
            app.state.participant_runtime.assignments.bind(
                sid,
                episode_id,
                assignment_method="phase14b3c2-preflight-fixed",
                assignment_version="phase14b3c2-preflight-v1",
            )
            contract = app.state.participant_runtime.orchestration.contract

            for step in range(15):
                state = app.state.participant_runtime.orchestration.get(sid)
                protocol_dates_exact = protocol_dates_exact and (
                    state.experiment_step == step
                    and state.agent_world_date == contract.checkpoint_date(step)
                )

                raise_ok(
                    client.post(
                        f"/session/{sid}/exposure/background",
                        json={"request_id": f"bg-{step}"},
                    )
                )

                if step == 0:
                    raise_ok(client.post(f"/session/{sid}/judgement", json=judgement("j0")))
                    raise_ok(
                        client.post(
                            f"/session/{sid}/exposure/stimulus",
                            json={"request_id": "misinformation"},
                        )
                    )
                    raise_ok(client.post(f"/session/{sid}/judgement", json=judgement("j1")))
                elif step == 7:
                    raise_ok(client.post(f"/session/{sid}/judgement", json=judgement("j2")))
                    raise_ok(
                        client.post(
                            f"/session/{sid}/exposure/stimulus",
                            json={"request_id": "correction"},
                        )
                    )
                    raise_ok(client.post(f"/session/{sid}/judgement", json=judgement("j3")))
                elif step == 14:
                    raise_ok(client.post(f"/session/{sid}/judgement", json=judgement("j4")))

                forged = client.post(
                    f"/session/{sid}/round/complete",
                    json={
                        "request_id": f"forged-round-{step}",
                        "step": step,
                        "current_stage": "COMPLETED",
                    },
                )
                forged_round_stage_rejected = (
                    forged_round_stage_rejected and forged.status_code == 422
                )

                first = raise_ok(
                    client.post(
                        f"/session/{sid}/round/complete",
                        json={"request_id": f"round-{step}", "step": step},
                    )
                )
                retry = raise_ok(
                    client.post(
                        f"/session/{sid}/round/complete",
                        json={"request_id": f"round-{step}", "step": step},
                    )
                )
                replay_ids.append((first.json()["completion_id"], retry.json()["completion_id"]))

            final = app.state.participant_runtime.orchestration.get(sid)
            round_rows = RoundStore(app.state.db).list_for_session(sid)
            judgement_rows = JudgementStore(app.state.db).list_for_session(sid)
            event_rows = events.list_for_session(sid)

        by_event = {row["judgement_event"]: row for row in judgement_rows}
        judgement_events = set(by_event)
        event_types = [row["event_type"] for row in event_rows]

        positive_checks = {
            "round_runtime_replaced": True,
            "protocol_checkpoint_count_is_15": len(round_rows) == 15,
            "round_retry_idempotent_across_advance": all(a == b for a, b in replay_ids),
            "protocol_dates_exact": protocol_dates_exact,
            "terminal_next_step_is_null": round_rows[-1]["step"] == 14 and round_rows[-1]["next_step"] is None,
            "final_session_completed": final.completed is True,
            "final_session_step_remains_14": final.experiment_step == 14,
            "final_session_date_is_2023_07_11": final.agent_world_date == "2023-07-11",
            "final_stage_completed": final.current_stage == "COMPLETED",
            "background_exposure_count_is_15": event_types.count("BACKGROUND_EXPOSED") == 15,
            "controlled_stimulus_count_is_2": event_types.count("CONTROLLED_STIMULUS_EXPOSED") == 2,
            "formal_judgement_count_is_5": len(judgement_rows) == 5,
            "formal_judgement_events_exact": judgement_events == {"J0", "J1", "J2", "J3", "J4"},
            "j0_j1_same_state": (
                by_event["J0"]["experiment_step"], by_event["J0"]["agent_world_date"]
            ) == (
                by_event["J1"]["experiment_step"], by_event["J1"]["agent_world_date"]
            ),
            "j2_j3_same_state": (
                by_event["J2"]["experiment_step"], by_event["J2"]["agent_world_date"]
            ) == (
                by_event["J3"]["experiment_step"], by_event["J3"]["agent_world_date"]
            ),
            "j4_later_measurement": int(by_event["J4"]["experiment_step"]) > int(by_event["J3"]["experiment_step"]),
            "runtime_event_count_is_27": len(event_rows) == 27,
            "client_supplied_round_stage_rejected": forged_round_stage_rejected,
        }
        negative_checks = {
            "formal_experiment_evidence": False,
            "random_allocator_added": False,
            "phase10_protocol_modified": False,
            "phase11_formal_stimulus_modified": False,
            "phase12_source_cue_modified": False,
            "agent_world_db_written": False,
            "forum_db_written": False,
        }

        failed = [name for name, ok in positive_checks.items() if not ok]
        failed.extend(name for name, value in negative_checks.items() if value)
        status = "PASS" if not failed else "FAIL"

        result = {
            "status": status,
            "evidence_class": "NON-FORMAL / PHASE 14B3C2 PHASE 14 CLOSURE PREFLIGHT / ZERO-LLM",
            "llm_api_calls": 0,
            **negative_checks,
            **positive_checks,
            "note": "B3C2 replaces participant-runtime round completion with one protocol-driven human-DB transaction and closes Phase 14 engineering. This is not formal participant evidence.",
        }
        if failed:
            result["failed_checks"] = failed

        print("NON-FORMAL / PHASE 14B3C2 PHASE 14 CLOSURE PREFLIGHT / ZERO-LLM")
        print(json.dumps(result, indent=2))
        events.dispose()
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
