#!/usr/bin/env python3
"""Zero-LLM Phase 11B candidate-material preflight.

This validates the selected evidence-grounded candidate without authorizing
formal participant use. The runner is intentionally directly executable from
any working directory and resolves all project paths from its own location.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketlens.stimulus import (  # noqa: E402
    StimulusEngine,
    StimulusValidationError,
    VisibilityMoment,
    load_material,
)


LABEL = "NON-FORMAL / PHASE 11B CANDIDATE MATERIAL PREFLIGHT / ZERO-LLM / NOT FORMAL EXPERIMENT EVIDENCE"
CANDIDATE = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.candidate.json"
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
    return {
        str(path.relative_to(ROOT)): digest(path)
        for path in PROTECTED
        if path.exists()
    }


def main() -> int:
    before = snapshot()

    material = load_material(CANDIDATE)
    engine = StimulusEngine(material)

    formal_mode_rejected = False
    try:
        load_material(CANDIDATE, formal=True)
    except StimulusValidationError:
        formal_mode_rejected = True

    correction_targets_misinformation = (
        material.correction.corrects_stimulus_id
        == material.misinformation.stimulus_id
    )

    truth_table = {
        "step0_post_release": [
            x.stimulus_id
            for x in engine.visible_stimuli(
                0, moment=VisibilityMoment.POST_MISINFORMATION_RELEASE
            )
        ],
        "step7_post_correction": [
            x.stimulus_id
            for x in engine.visible_stimuli(
                7, moment=VisibilityMoment.POST_CORRECTION_RELEASE
            )
        ],
        "step14": [x.stimulus_id for x in engine.visible_stimuli(14)],
    }
    expected_truth_table = {
        "step0_post_release": ["MISINFO_MEI_OWNERSHIP_001_CANDIDATE"],
        "step7_post_correction": [
            "MISINFO_MEI_OWNERSHIP_001_CANDIDATE",
            "CORRECTION_MEI_OWNERSHIP_001_CANDIDATE",
        ],
        "step14": [
            "MISINFO_MEI_OWNERSHIP_001_CANDIDATE",
            "CORRECTION_MEI_OWNERSHIP_001_CANDIDATE",
        ],
    }

    after = snapshot()
    protected_sources_unchanged = before == after

    passed = all(
        [
            formal_mode_rejected,
            correction_targets_misinformation,
            truth_table == expected_truth_table,
            protected_sources_unchanged,
        ]
    )

    summary = {
        "status": "PASS" if passed else "FAIL",
        "evidence_class": LABEL,
        "llm_api_calls": 0,
        "formal_experiment_evidence": False,
        "candidate_selected": True,
        "candidate_formal_frozen": False,
        "formal_mode_rejected": formal_mode_rejected,
        "target_stock_id": material.target_stock_id,
        "material_version": material.material_version,
        "participant_behaviour_parameters_added": 0,
        "release_dates_derived_from_phase10": engine.release_dates(),
        "misinformation_id": material.misinformation.stimulus_id,
        "correction_id": material.correction.stimulus_id,
        "correction_targets_misinformation": correction_targets_misinformation,
        "truth_table": truth_table,
        "protected_sources_unchanged": protected_sources_unchanged,
        "agent_world_mutation_performed": False,
        "forum_write_performed": False,
        "market_write_performed": False,
        "note": "Evidence-grounded MEI ownership-link candidate only. Still development status; formal mode intentionally fails closed pending a later freeze step.",
    }

    out_dir = (
        ROOT
        / "artifacts"
        / "preflight"
        / "phase11"
        / datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ_phase11_candidate_material"
        )
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(LABEL)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Artifact: {summary_path}")

    if not passed:
        raise SystemExit("FAIL: Phase 11B candidate-material preflight contract not satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
