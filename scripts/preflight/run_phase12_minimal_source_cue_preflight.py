#!/usr/bin/env python3
"""Zero-LLM Phase 12 minimal source-cue adapter preflight."""
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
    decorate_controlled_stimulus_payload,
    resolve_agent_source_cue,
)
from marketlens.stimulus import StimulusEngine, VisibilityMoment, load_material  # noqa: E402

EVIDENCE_CLASS = "NON-FORMAL / PHASE 12 MINIMAL SOURCE-CUE ADAPTER PREFLIGHT / ZERO-LLM / NOT FORMAL EXPERIMENT EVIDENCE"
PROTECTED = (
    ROOT / "Agent.py",
    ROOT / "simulation.py",
    ROOT / "util" / "UserDB.py",
    ROOT / "util" / "ForumDB.py",
    ROOT / "data" / "sys_1000.db",
)
FORMAL_STIMULUS = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json"
PROFILE_DATE = "2023-06-14 00:00:00"
SAMPLE_USERS = {
    "普通股民": "91250121016",
    "小博主": "92435351068",
    "大V": "27033813419",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def protected_hashes() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): sha256_file(path) for path in PROTECTED if path.exists()}


def main() -> int:
    before_hashes = protected_hashes()

    agent_examples = {
        inherited_type: resolve_agent_source_cue(
            user_id,
            db_path=str(ROOT / "data" / "sys_1000.db"),
            created_at=PROFILE_DATE,
        )
        for inherited_type, user_id in SAMPLE_USERS.items()
    }
    for inherited_type, cue in agent_examples.items():
        if cue["user_type"] != inherited_type:
            raise SystemExit(f"inherited user_type mismatch for {inherited_type}")

    material = load_material(FORMAL_STIMULUS, formal=True)
    engine = StimulusEngine(material)

    phase11_payloads = {
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
    decorated_payloads = {
        state: tuple(decorate_controlled_stimulus_payload(x) for x in payloads)
        for state, payloads in phase11_payloads.items()
    }

    phase11_text_unchanged = all(
        decorated[key] == original[key]
        for state, originals in phase11_payloads.items()
        for original, decorated in zip(originals, decorated_payloads[state])
        for key in ("stimulus_id", "kind", "headline", "body", "corrects_stimulus_id")
    )

    misinformation_cues = []
    for state in (
        "step0_post_release",
        "step7_pre_correction",
        "step7_post_correction",
        "step14",
    ):
        misinformation = next(
            item
            for item in decorated_payloads[state]
            if item["stimulus_id"] == "MISINFO_MEI_OWNERSHIP_001"
        )
        misinformation_cues.append(
            (misinformation["source_label"], misinformation["source_descriptor"])
        )
    misinformation_source_cue_invariant = len(set(misinformation_cues)) == 1
    if not misinformation_source_cue_invariant:
        raise SystemExit("misinformation source cue changed across the visible horizon")

    after_hashes = protected_hashes()
    protected_unchanged = before_hashes == after_hashes
    if not protected_unchanged:
        raise SystemExit("protected inherited sources changed during read-only source-cue preflight")

    summary = {
        "status": "PASS",
        "evidence_class": EVIDENCE_CLASS,
        "llm_api_calls": 0,
        "formal_experiment_evidence": False,
        "cue_version": CUE_VERSION,
        "cue_status": CUE_STATUS,
        "reuse_contract": {
            "agent_identity_source": "inherited util.UserDB.get_user_profile(...)[user_type]",
            "forum_identity_join_key": "inherited ForumDB post.user_id",
            "controlled_visibility_source": "Phase 11 StimulusEngine.participant_payload",
            "dynamic_top_user_used_as_credibility": False,
        },
        "agent_source_examples": agent_examples,
        "controlled_truth_table": {
            state: [
                {
                    "stimulus_id": x["stimulus_id"],
                    "source_label": x["source_label"],
                    "source_descriptor": x["source_descriptor"],
                }
                for x in payloads
            ]
            for state, payloads in decorated_payloads.items()
        },
        "misinformation_source_cue_invariant": misinformation_source_cue_invariant,
        "phase11_stimulus_text_modified": not phase11_text_unchanged,
        "phase10_timing_modified": False,
        "participant_behaviour_parameters_added": 0,
        "agent_world_mutation_performed": False,
        "forum_write_performed": False,
        "market_write_performed": False,
        "protected_sources_unchanged": protected_unchanged,
        "note": "Minimal adapter reuse/invariance preflight. Formal freeze integrity is validated separately by the Phase 12B formal source-cue preflight.",
    }

    out_dir = ROOT / "artifacts" / "preflight" / "phase12" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_phase12_minimal_source_cue"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / "summary.json"
    artifact.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(EVIDENCE_CLASS)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Artifact: {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
