from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from marketlens.source_cues import (
    CUE_STATUS,
    CUE_VERSION,
    SOURCE_CUE_MANIFEST_SHA256,
    assert_formal_source_cue_freeze,
    decorate_controlled_stimulus_payload,
    source_cue_manifest_payload,
    source_cue_manifest_sha256,
)
from marketlens.stimulus import StimulusEngine, VisibilityMoment, load_material


ROOT = Path(__file__).resolve().parents[3]
FORMAL_STIMULUS = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json"
RUNNER = ROOT / "scripts" / "preflight" / "run_phase12_formal_source_cue_preflight.py"
EXPECTED_SOURCE_CUE_HASH = "67e567351eb77a1edf186239f6205dc43840fbf6e59076813f702fef55b7d5ef"


def test_phase12b_formal_version_status_and_exact_manifest_hash_are_frozen():
    assert CUE_VERSION == "1.0"
    assert CUE_STATUS == "formal_frozen"
    assert SOURCE_CUE_MANIFEST_SHA256 == EXPECTED_SOURCE_CUE_HASH
    assert source_cue_manifest_sha256() == EXPECTED_SOURCE_CUE_HASH
    assert assert_formal_source_cue_freeze() == EXPECTED_SOURCE_CUE_HASH


def test_phase12b_exact_display_mapping_is_frozen():
    assert source_cue_manifest_payload() == {
        "cue_version": "1.0",
        "cue_status": "formal_frozen",
        "agent_user_type_labels": {
            "普通股民": "Individual Investor",
            "小博主": "Market Blogger",
            "大V": "Influential Market Commentator",
        },
        "controlled_stimulus_cues": {
            "MISINFO_MEI_OWNERSHIP_001": {
                "source_label": "Market News Report",
                "source_descriptor": "Market media report",
            },
            "CORRECTION_MEI_OWNERSHIP_001": {
                "source_label": "LONGi Green Energy",
                "source_descriptor": "Official company announcement",
            },
        },
    }


def test_phase12b_phase11_text_and_visibility_remain_upstream_and_unchanged():
    material = load_material(FORMAL_STIMULUS, formal=True)
    engine = StimulusEngine(material)
    before = engine.participant_payload(7, moment=VisibilityMoment.PRE_CORRECTION_RELEASE)
    after = engine.participant_payload(7, moment=VisibilityMoment.POST_CORRECTION_RELEASE)

    before_decorated = tuple(decorate_controlled_stimulus_payload(x) for x in before)
    after_decorated = tuple(decorate_controlled_stimulus_payload(x) for x in after)

    for originals, decorated in ((before, before_decorated), (after, after_decorated)):
        for original, shown in zip(originals, decorated):
            for key in ("stimulus_id", "kind", "headline", "body", "corrects_stimulus_id"):
                assert shown[key] == original[key]

    assert [(x["source_label"], x["source_descriptor"]) for x in before_decorated] == [
        ("Market News Report", "Market media report")
    ]
    assert [(x["source_label"], x["source_descriptor"]) for x in after_decorated] == [
        ("Market News Report", "Market media report"),
        ("LONGi Green Energy", "Official company announcement"),
    ]


def test_phase12b_formal_preflight_runner_is_directly_executable_from_repo_root():
    result = subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"status": "PASS"' in result.stdout
    assert '"formal_source_cues_accepted": true' in result.stdout
    assert f'"source_cue_manifest_sha256": "{EXPECTED_SOURCE_CUE_HASH}"' in result.stdout
    assert '"participant_behaviour_parameters_added": 0' in result.stdout
    assert '"dynamic_top_user_used_as_credibility": false' in result.stdout
    assert '"protected_sources_unchanged": true' in result.stdout
    assert "Artifact:" in result.stdout
