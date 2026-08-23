from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from marketlens.stimulus import StimulusEngine, StimulusValidationError, VisibilityMoment, load_material


ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.candidate.json"
RUNNER = ROOT / "scripts" / "preflight" / "run_phase11_candidate_material_preflight.py"


def test_phase11b_candidate_loads_and_hashes_but_remains_nonformal():
    material = load_material(CANDIDATE)
    assert material.stimulus_set_id == "marketlens-phase11-mei-ownership-candidate-v1"
    assert material.material_version == "1.0-candidate"
    assert material.target_stock_id == "MEI"
    assert material.formal_use_status.value == "development"


def test_phase11b_candidate_formal_mode_fails_closed():
    with pytest.raises(StimulusValidationError, match="formal mode requires formal_frozen"):
        load_material(CANDIDATE, formal=True)


def test_phase11b_correction_targets_the_exact_misinformation_claim():
    material = load_material(CANDIDATE)
    assert material.correction.corrects_stimulus_id == material.misinformation.stimulus_id
    assert "1.85%" in material.misinformation.body
    assert "neither its wholly owned nor controlled subsidiary" in material.correction.body
    assert "did not acquire" not in material.correction.body  # wording uses explicit subject scope instead
    assert "did not" not in material.misinformation.body


def test_phase11b_candidate_inherits_phase10_release_dates_and_persistence():
    engine = StimulusEngine(load_material(CANDIDATE))
    assert engine.release_dates() == {
        "misinformation": "2023-06-19",
        "authoritative_correction": "2023-06-30",
    }
    assert [x.stimulus_id for x in engine.visible_stimuli(0, moment=VisibilityMoment.POST_MISINFORMATION_RELEASE)] == [
        "MISINFO_MEI_OWNERSHIP_001_CANDIDATE"
    ]
    assert [x.stimulus_id for x in engine.visible_stimuli(7, moment=VisibilityMoment.POST_CORRECTION_RELEASE)] == [
        "MISINFO_MEI_OWNERSHIP_001_CANDIDATE",
        "CORRECTION_MEI_OWNERSHIP_001_CANDIDATE",
    ]
    assert [x.stimulus_id for x in engine.visible_stimuli(14)] == [
        "MISINFO_MEI_OWNERSHIP_001_CANDIDATE",
        "CORRECTION_MEI_OWNERSHIP_001_CANDIDATE",
    ]


def test_phase11b_preflight_runner_is_directly_executable_from_repo_root():
    result = subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"status": "PASS"' in result.stdout
    assert '"formal_mode_rejected": true' in result.stdout
    assert '"protected_sources_unchanged": true' in result.stdout
    assert "Artifact:" in result.stdout
