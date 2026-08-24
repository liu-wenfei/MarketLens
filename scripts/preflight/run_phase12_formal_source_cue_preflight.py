#!/usr/bin/env python3
"""Zero-LLM Phase 12B formal source-cue freeze preflight."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marketlens.source_cues import (  # noqa: E402
    CUE_STATUS,
    CUE_VERSION,
    SOURCE_CUE_MANIFEST_SHA256,
    assert_formal_source_cue_freeze,
    decorate_controlled_stimulus_payload,
    resolve_agent_source_cue,
    source_cue_manifest_payload,
)
from marketlens.stimulus import StimulusEngine, VisibilityMoment, load_material  # noqa: E402


LABEL = "NON-FORMAL / PHASE 12B FORMAL SOURCE-CUE FREEZE PREFLIGHT / ZERO-LLM / NOT FORMAL EXPERIMENT EVIDENCE"
EXPECTED_SOURCE_CUE_HASH = "67e567351eb77a1edf186239f6205dc43840fbf6e59076813f702fef55b7d5ef"
EXPECTED_PHASE11_MANIFEST_HASH = "e65fe566a58af44f0738b14fff160a09dfc42f34d73455accb92aae2cdadef9a"
FORMAL_STIMULUS = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json"
PROFILE_DATE = "2023-06-14 00:00:00"
SAMPLE_USERS = {
    "普通股民": "91250121016",
    "小博主": "92435351068",
    "大V": "27033813419",
}
PROTECTED = (
    ROOT / "Agent.py",
    ROOT / "simulation.py",
    ROOT / "util" / "UserDB.py",
    ROOT / "util" / "ForumDB.py",
    ROOT / "data" / "sys_1000.db",
    ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def protected_hashes() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): sha256_file(path) for path in PROTECTED if path.exists()}


def cue_view(payloads):
    return [
        {
            "stimulus_id": item["stimulus_id"],
            "source_label": item["source_label"],
            "source_descriptor": item["source_descriptor"],
        }
        for item in payloads
    ]


def main() -> int:
    before = protected_hashes()

    actual_hash = assert_formal_source_cue_freeze()
    formal_source_cues_accepted = (
        CUE_VERSION == "1.0"
        and CUE_STATUS == "formal_frozen"
        and SOURCE_CUE_MANIFEST_SHA256 == EXPECTED_SOURCE_CUE_HASH
        and actual_hash == EXPECTED_SOURCE_CUE_HASH
    )

    agent_examples = {
        inherited_type: resolve_agent_source_cue(
            user_id,
            db_path=str(ROOT / "data" / "sys_1000.db"),
            created_at=PROFILE_DATE,
        )
        for inherited_type, user_id in SAMPLE_USERS.items()
    }
    inherited_types_exact = all(
        agent_examples[user_type]["user_type"] == user_type
        for user_type in SAMPLE_USERS
    )

    material = load_material(FORMAL_STIMULUS, formal=True)
    phase11_manifest_unchanged = material.manifest_sha256 == EXPECTED_PHASE11_MANIFEST_HASH
    engine = StimulusEngine(material)
    release_dates = engine.release_dates()

    states = {
        "step0_post_release": engine.participant_payload(
            0, moment=VisibilityMoment.POST_MISINFORMATION_RELEASE
        ),
        "step7_pre_correction": engine.participant_payload(
            7, moment=VisibilityMoment.PRE_CORRECTION_RELEASE
        ),
        "step7_post_correction": engine.participant_payload(
            7, moment=VisibilityMoment.POST_CORRECTION_RELEASE
        ),
        "step14": engine.participant_payload(14),
    }
    decorated = {
        state: tuple(decorate_controlled_stimulus_payload(item) for item in payloads)
        for state, payloads in states.items()
    }

    phase11_stimulus_text_modified = any(
        shown[key] != original[key]
        for state, originals in states.items()
        for original, shown in zip(originals, decorated[state])
        for key in ("stimulus_id", "kind", "headline", "body", "corrects_stimulus_id")
    )

    misinformation_cues = []
    for state in ("step0_post_release", "step7_pre_correction", "step7_post_correction", "step14"):
        item = next(
            x for x in decorated[state]
            if x["stimulus_id"] == "MISINFO_MEI_OWNERSHIP_001"
        )
        misinformation_cues.append((item["source_label"], item["source_descriptor"]))
    misinformation_source_cue_invariant = len(set(misinformation_cues)) == 1

    expected_truth_table = {
        "step0_post_release": [
            {
                "stimulus_id": "MISINFO_MEI_OWNERSHIP_001",
                "source_label": "Market News Report",
                "source_descriptor": "Market media report",
            }
        ],
        "step7_pre_correction": [
            {
                "stimulus_id": "MISINFO_MEI_OWNERSHIP_001",
                "source_label": "Market News Report",
                "source_descriptor": "Market media report",
            }
        ],
        "step7_post_correction": [
            {
                "stimulus_id": "MISINFO_MEI_OWNERSHIP_001",
                "source_label": "Market News Report",
                "source_descriptor": "Market media report",
            },
            {
                "stimulus_id": "CORRECTION_MEI_OWNERSHIP_001",
                "source_label": "LONGi Green Energy",
                "source_descriptor": "Official company announcement",
            },
        ],
        "step14": [
            {
                "stimulus_id": "MISINFO_MEI_OWNERSHIP_001",
                "source_label": "Market News Report",
                "source_descriptor": "Market media report",
            },
            {
                "stimulus_id": "CORRECTION_MEI_OWNERSHIP_001",
                "source_label": "LONGi Green Energy",
                "source_descriptor": "Official company announcement",
            },
        ],
    }
    truth_table = {state: cue_view(payloads) for state, payloads in decorated.items()}

    after = protected_hashes()
    protected_sources_unchanged = before == after

    passed = all(
        [
            formal_source_cues_accepted,
            inherited_types_exact,
            source_cue_manifest_payload()["agent_user_type_labels"]
            == {
                "普通股民": "Individual Investor",
                "小博主": "Market Blogger",
                "大V": "Influential Market Commentator",
            },
            phase11_manifest_unchanged,
            not phase11_stimulus_text_modified,
            release_dates
            == {
                "misinformation": "2023-06-19",
                "authoritative_correction": "2023-06-30",
            },
            misinformation_source_cue_invariant,
            truth_table == expected_truth_table,
            protected_sources_unchanged,
        ]
    )

    summary = {
        "status": "PASS" if passed else "FAIL",
        "evidence_class": LABEL,
        "llm_api_calls": 0,
        "formal_experiment_evidence": False,
        "formal_source_cues_accepted": formal_source_cues_accepted,
        "cue_version": CUE_VERSION,
        "cue_status": CUE_STATUS,
        "source_cue_manifest_sha256": actual_hash,
        "exact_source_cue_hash_frozen": actual_hash == EXPECTED_SOURCE_CUE_HASH,
        "phase11_manifest_sha256": material.manifest_sha256,
        "phase11_manifest_unchanged": phase11_manifest_unchanged,
        "reuse_contract": {
            "agent_identity_source": "inherited util.UserDB.get_user_profile(...)[user_type]",
            "forum_identity_join_key": "inherited ForumDB post.user_id",
            "controlled_visibility_source": "Phase 11 StimulusEngine.participant_payload",
            "canonical_hash_helper": "Phase 11 marketlens.stimulus.manifest.sha256_json",
            "dynamic_top_user_used_as_credibility": False,
        },
        "agent_source_examples": agent_examples,
        "release_dates_derived_from_phase10": release_dates,
        "controlled_truth_table": truth_table,
        "misinformation_source_cue_invariant": misinformation_source_cue_invariant,
        "phase11_stimulus_text_modified": phase11_stimulus_text_modified,
        "phase10_timing_modified": False,
        "participant_behaviour_parameters_added": 0,
        "agent_world_mutation_performed": False,
        "forum_write_performed": False,
        "market_write_performed": False,
        "protected_sources_unchanged": protected_sources_unchanged,
        "note": "Formal source-cue engineering freeze only. It does not imply supervisor, ethics, participant, or domain-expert approval and is not formal experiment evidence.",
    }

    out_dir = ROOT / "artifacts" / "preflight" / "phase12" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "_phase12_formal_source_cue"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / "summary.json"
    artifact.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(LABEL)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Artifact: {artifact}")

    if not passed:
        raise SystemExit("FAIL: Phase 12B formal source-cue freeze contract not satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
