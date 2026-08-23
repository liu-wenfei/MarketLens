from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pandas as pd

from marketlens.stimulus import StimulusEngine, VisibilityMoment, load_material


ROOT = Path(__file__).resolve().parents[3]
FORMAL = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json"
RUNNER = ROOT / "scripts" / "preflight" / "run_phase11_formal_material_preflight.py"

EXPECTED_MISINFO_HASH = "7846c55c7b5ccbcb97ff28ec8d8c52a1b51336197805b7fec4aa4d3e226403b6"
EXPECTED_CORRECTION_HASH = "fd042b4cbe194ef544bd162c7605da75678c32d654c6ae722867c2debd3cf269"
EXPECTED_MANIFEST_HASH = "e65fe566a58af44f0738b14fff160a09dfc42f34d73455accb92aae2cdadef9a"


def test_phase11c_formal_material_loads_only_as_explicit_formal_file():
    material = load_material(FORMAL, formal=True)
    assert material.stimulus_set_id == "marketlens-phase11-mei-ownership-formal-v1"
    assert material.material_version == "1.0"
    assert material.protocol_version == "1.1"
    assert material.target_stock_id == "MEI"
    assert material.formal_use_status.value == "formal_frozen"


def test_phase11c_exact_wording_and_hashes_are_frozen():
    material = load_material(FORMAL, formal=True)
    assert material.misinformation.headline == (
        "Manufacturing Index constituent LONGi takes 1.85% stake in Ningxia Baofeng New Energy"
    )
    assert material.misinformation.body == (
        "LONGi Hong Kong Investment Limited, a subsidiary of LONGi Green Energy, has acquired a "
        "1.8488% stake in Ningxia Baofeng New Energy Technology Co., Ltd."
    )
    assert material.correction.headline == (
        "Correction: reported LONGi stake in Ningxia Baofeng was inaccurate"
    )
    assert material.correction.body == (
        "LONGi Hong Kong Investment Limited is neither a wholly owned nor controlled subsidiary of "
        "LONGi Green Energy. LONGi Green Energy and its subsidiaries did not acquire any stake in "
        "Ningxia Baofeng New Energy Technology Co., Ltd."
    )
    assert material.misinformation.content_sha256 == EXPECTED_MISINFO_HASH
    assert material.correction.content_sha256 == EXPECTED_CORRECTION_HASH
    assert material.manifest_sha256 == EXPECTED_MANIFEST_HASH
    assert material.correction.corrects_stimulus_id == material.misinformation.stimulus_id


def test_phase11c_formal_wording_adds_no_investment_instruction_or_extra_outcome_claim():
    material = load_material(FORMAL, formal=True)
    text = f"{material.misinformation.headline} {material.misinformation.body}".lower()
    forbidden = (
        "buy",
        "sell",
        "hold",
        "price target",
        "share price",
        "guaranteed supply",
        "profit",
        "earnings",
        "lower costs",
        "higher returns",
        "if the reported ownership link is accurate",
    )
    assert not any(term in text for term in forbidden)


def test_phase11c_formal_timing_and_persistence_are_still_phase10_driven():
    engine = StimulusEngine(load_material(FORMAL, formal=True))
    assert engine.release_dates() == {
        "misinformation": "2023-06-19",
        "authoritative_correction": "2023-06-30",
    }
    assert [x.stimulus_id for x in engine.visible_stimuli(0, moment=VisibilityMoment.POST_MISINFORMATION_RELEASE)] == [
        "MISINFO_MEI_OWNERSHIP_001"
    ]
    assert [x.stimulus_id for x in engine.visible_stimuli(7, moment=VisibilityMoment.POST_CORRECTION_RELEASE)] == [
        "MISINFO_MEI_OWNERSHIP_001",
        "CORRECTION_MEI_OWNERSHIP_001",
    ]
    assert [x.stimulus_id for x in engine.visible_stimuli(14)] == [
        "MISINFO_MEI_OWNERSHIP_001",
        "CORRECTION_MEI_OWNERSHIP_001",
    ]


def test_phase11c_mei_contains_longi_and_visible_window_has_no_declared_direct_news_collision():
    profile = pd.read_csv(ROOT / "data" / "stock_profile.csv")
    mei = profile.loc[profile["stock_id"] == "MEI"]
    assert len(mei) == 1
    assert "隆基绿能" in str(mei.iloc[0]["description"])

    news = pd.read_pickle(ROOT / "data" / "sorted_impact_news.pkl")
    window = news[(news["cal_date"] >= "2023-06-19") & (news["cal_date"] <= "2023-07-11")]
    terms = ("隆基", "longi", "601012", "宝丰", "多晶硅", "polysilicon")
    collisions = []
    for _, row in window.iterrows():
        for item in row["news"]:
            lowered = str(item).lower()
            if any(term in lowered for term in terms):
                collisions.append((row["cal_date"], str(item)))
    assert collisions == []


def test_phase11c_formal_preflight_runner_is_directly_executable_from_repo_root():
    result = subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"status": "PASS"' in result.stdout
    assert '"formal_material_accepted": true' in result.stdout
    assert '"participant_behaviour_parameters_added": 0' in result.stdout
    assert '"direct_background_collision_count": 0' in result.stdout
    assert '"protected_sources_unchanged": true' in result.stdout
    assert "Artifact:" in result.stdout
