#!/usr/bin/env python3
"""Zero-LLM Phase 11 controlled-stimulus contract preflight."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketlens.stimulus import StimulusEngine, VisibilityMoment, load_material  # noqa: E402

LABEL = "NON-FORMAL / PHASE 11 CONTROLLED-STIMULUS CONTRACT PREFLIGHT / ZERO-LLM / NOT FORMAL EXPERIMENT EVIDENCE"

PROTECTED = [
    ROOT / "Agent.py",
    ROOT / "simulation.py",
    ROOT / "data" / "sys_1000.db",
    ROOT / "data" / "stock_profile.csv",
    ROOT / "data" / "stock_data.csv",
    ROOT / "data" / "trading_days.csv",
    ROOT / "data" / "sorted_impact_news.pkl",
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): digest(path) for path in PROTECTED if path.exists()}


def main() -> int:
    before = snapshot()
    material = load_material(formal=False)
    engine = StimulusEngine(material)

    truth_table = {
        "step0_pre_J0_J1_release": [item.stimulus_id for item in engine.visible_stimuli(0, moment=VisibilityMoment.PRE_MISINFORMATION_RELEASE)],
        "step0_post_J0_J1_release": [item.stimulus_id for item in engine.visible_stimuli(0, moment=VisibilityMoment.POST_MISINFORMATION_RELEASE)],
        "step1_default": [item.stimulus_id for item in engine.visible_stimuli(1)],
        "step7_pre_J2_J3_release": [item.stimulus_id for item in engine.visible_stimuli(7, moment=VisibilityMoment.PRE_CORRECTION_RELEASE)],
        "step7_post_J2_J3_release": [item.stimulus_id for item in engine.visible_stimuli(7, moment=VisibilityMoment.POST_CORRECTION_RELEASE)],
        "step14_J4_default": [item.stimulus_id for item in engine.visible_stimuli(14)],
    }
    expected = {
        "step0_pre_J0_J1_release": [],
        "step0_post_J0_J1_release": ["MISINFO_DEV_001"],
        "step1_default": ["MISINFO_DEV_001"],
        "step7_pre_J2_J3_release": ["MISINFO_DEV_001"],
        "step7_post_J2_J3_release": ["MISINFO_DEV_001", "CORRECTION_DEV_001"],
        "step14_J4_default": ["MISINFO_DEV_001", "CORRECTION_DEV_001"],
    }
    after = snapshot()
    result = {
        "status": "PASS" if truth_table == expected and before == after else "FAIL",
        "llm_api_calls": 0,
        "formal_experiment_evidence": False,
        "material_status": material.formal_use_status.value,
        "formal_material_used": False,
        "protocol_version": material.protocol_version,
        "participant_behaviour_parameters_added": 0,
        "release_dates_derived_from_phase10": engine.release_dates(),
        "truth_table": truth_table,
        "protected_sources_unchanged": before == after,
        "agent_world_mutation_performed": False,
        "forum_write_performed": False,
        "market_write_performed": False,
        "note": "Development-only synthetic material; formal mode must fail closed until a later frozen formal material file is supplied.",
    }
    out_dir = ROOT / "artifacts" / "preflight" / "phase11" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_phase11_stimulus_contract")
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / "summary.json"
    artifact.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(LABEL)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Artifact: {artifact}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
