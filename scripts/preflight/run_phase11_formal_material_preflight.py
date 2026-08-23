#!/usr/bin/env python3
"""Zero-LLM Phase 11C formal-material freeze preflight.

This validates exact formal material, provenance-compatible target mapping,
Phase-10-derived timing/persistence, direct inherited-news collision guard,
and protected-source immutability. It does not run formal participants or LLMs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketlens.stimulus import StimulusEngine, VisibilityMoment, load_material  # noqa: E402


LABEL = "NON-FORMAL / PHASE 11C FORMAL-MATERIAL FREEZE PREFLIGHT / ZERO-LLM / NOT FORMAL EXPERIMENT EVIDENCE"
FORMAL = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json"
EXPECTED_MISINFO_HASH = "7846c55c7b5ccbcb97ff28ec8d8c52a1b51336197805b7fec4aa4d3e226403b6"
EXPECTED_CORRECTION_HASH = "fd042b4cbe194ef544bd162c7605da75678c32d654c6ae722867c2debd3cf269"
EXPECTED_MANIFEST_HASH = "e65fe566a58af44f0738b14fff160a09dfc42f34d73455accb92aae2cdadef9a"
COLLISION_TERMS = ("隆基", "longi", "601012", "宝丰", "多晶硅", "polysilicon")
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


def background_collisions() -> list[dict[str, str]]:
    news = pd.read_pickle(ROOT / "data" / "sorted_impact_news.pkl")
    window = news[(news["cal_date"] >= "2023-06-19") & (news["cal_date"] <= "2023-07-11")]
    hits: list[dict[str, str]] = []
    for _, row in window.iterrows():
        for item in row["news"]:
            text = str(item)
            lowered = text.lower()
            matched = [term for term in COLLISION_TERMS if term in lowered]
            if matched:
                hits.append({"date": str(row["cal_date"]), "terms": ",".join(matched), "text": text})
    return hits


def main() -> int:
    before = snapshot()

    material = load_material(FORMAL, formal=True)
    engine = StimulusEngine(material)

    formal_material_accepted = material.formal_use_status.value == "formal_frozen"
    exact_hashes_frozen = (
        material.misinformation.content_sha256 == EXPECTED_MISINFO_HASH
        and material.correction.content_sha256 == EXPECTED_CORRECTION_HASH
        and material.manifest_sha256 == EXPECTED_MANIFEST_HASH
    )
    correction_targets_misinformation = (
        material.correction.corrects_stimulus_id == material.misinformation.stimulus_id
    )

    profile = pd.read_csv(ROOT / "data" / "stock_profile.csv")
    mei = profile.loc[profile["stock_id"] == "MEI"]
    mei_contains_longi = len(mei) == 1 and "隆基绿能" in str(mei.iloc[0]["description"])

    collisions = background_collisions()
    direct_background_collision_count = len(collisions)

    truth_table = {
        "step0_pre_release": [
            x.stimulus_id
            for x in engine.visible_stimuli(
                0, moment=VisibilityMoment.PRE_MISINFORMATION_RELEASE
            )
        ],
        "step0_post_release": [
            x.stimulus_id
            for x in engine.visible_stimuli(
                0, moment=VisibilityMoment.POST_MISINFORMATION_RELEASE
            )
        ],
        "step7_pre_correction": [
            x.stimulus_id
            for x in engine.visible_stimuli(
                7, moment=VisibilityMoment.PRE_CORRECTION_RELEASE
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
        "step0_pre_release": [],
        "step0_post_release": ["MISINFO_MEI_OWNERSHIP_001"],
        "step7_pre_correction": ["MISINFO_MEI_OWNERSHIP_001"],
        "step7_post_correction": [
            "MISINFO_MEI_OWNERSHIP_001",
            "CORRECTION_MEI_OWNERSHIP_001",
        ],
        "step14": [
            "MISINFO_MEI_OWNERSHIP_001",
            "CORRECTION_MEI_OWNERSHIP_001",
        ],
    }

    after = snapshot()
    protected_sources_unchanged = before == after

    passed = all(
        [
            formal_material_accepted,
            exact_hashes_frozen,
            correction_targets_misinformation,
            material.target_stock_id == "MEI",
            mei_contains_longi,
            direct_background_collision_count == 0,
            engine.release_dates()
            == {
                "misinformation": "2023-06-19",
                "authoritative_correction": "2023-06-30",
            },
            truth_table == expected_truth_table,
            protected_sources_unchanged,
        ]
    )

    summary = {
        "status": "PASS" if passed else "FAIL",
        "evidence_class": LABEL,
        "llm_api_calls": 0,
        "formal_experiment_evidence": False,
        "formal_material_accepted": formal_material_accepted,
        "material_status": material.formal_use_status.value,
        "material_version": material.material_version,
        "protocol_version": material.protocol_version,
        "target_stock_id": material.target_stock_id,
        "mei_contains_longi": mei_contains_longi,
        "participant_behaviour_parameters_added": 0,
        "release_dates_derived_from_phase10": engine.release_dates(),
        "misinformation_id": material.misinformation.stimulus_id,
        "correction_id": material.correction.stimulus_id,
        "correction_targets_misinformation": correction_targets_misinformation,
        "misinformation_sha256": material.misinformation.content_sha256,
        "correction_sha256": material.correction.content_sha256,
        "manifest_sha256": material.manifest_sha256,
        "exact_hashes_frozen": exact_hashes_frozen,
        "declared_background_collision_terms": list(COLLISION_TERMS),
        "direct_background_collision_count": direct_background_collision_count,
        "direct_background_collisions": collisions,
        "truth_table": truth_table,
        "protected_sources_unchanged": protected_sources_unchanged,
        "agent_world_mutation_performed": False,
        "forum_write_performed": False,
        "market_write_performed": False,
        "note": "Formal stimulus material only; source-cue presentation remains outside Phase 11. This zero-LLM preflight is not participant/formal experiment evidence.",
    }

    out_dir = (
        ROOT
        / "artifacts"
        / "preflight"
        / "phase11"
        / datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ_phase11_formal_material"
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
        raise SystemExit("FAIL: Phase 11C formal-material freeze preflight contract not satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
