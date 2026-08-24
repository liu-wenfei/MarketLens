from __future__ import annotations

import inspect
import sys
import types
from pathlib import Path

import pytest

from marketlens.source_cues import (
    SourceCueError,
    decorate_controlled_stimulus_payload,
    resolve_agent_source_cue,
    source_label_for_user_type,
)
from marketlens.source_cues import adapter as adapter_module
from marketlens.stimulus import StimulusEngine, VisibilityMoment, load_material

ROOT = Path(__file__).resolve().parents[3]
FORMAL_STIMULUS = ROOT / "data" / "marketlens" / "stimuli" / "stimulus_v1.formal.json"


def test_inherited_user_type_display_mapping_is_complete_and_neutral():
    assert source_label_for_user_type("普通股民") == "Individual Investor"
    assert source_label_for_user_type("小博主") == "Market Blogger"
    assert source_label_for_user_type("大V") == "Influential Market Commentator"
    labels = [source_label_for_user_type(x) for x in ("普通股民", "小博主", "大V")]
    forbidden = ("trusted", "reliable", "verified", "expert", "correct", "incorrect")
    assert all(not any(word in label.lower() for word in forbidden) for label in labels)


def test_unknown_user_type_fails_closed():
    with pytest.raises(SourceCueError):
        source_label_for_user_type("analyst")


def test_agent_source_cue_directly_reuses_inherited_get_user_profile(monkeypatch):
    calls = []

    def fake_get_user_profile(user_id, db_path, created_at):
        calls.append((user_id, db_path, created_at))
        return {"user_id": user_id, "user_type": "小博主"}

    fake_util = types.ModuleType("util")
    fake_userdb = types.ModuleType("util.UserDB")
    fake_userdb.get_user_profile = fake_get_user_profile
    fake_util.UserDB = fake_userdb
    monkeypatch.setitem(sys.modules, "util", fake_util)
    monkeypatch.setitem(sys.modules, "util.UserDB", fake_userdb)
    cue = resolve_agent_source_cue("123", db_path="candidate.db", created_at="2023-06-19 00:00:00")
    assert calls == [("123", "candidate.db", "2023-06-19 00:00:00")]
    assert cue == {"user_id": "123", "user_type": "小博主", "source_label": "Market Blogger"}


def test_controlled_stimulus_decoration_preserves_phase11_text_exactly():
    material = load_material(FORMAL_STIMULUS, formal=True)
    engine = StimulusEngine(material)
    phase11 = engine.participant_payload(
        0, moment=VisibilityMoment.POST_MISINFORMATION_RELEASE
    )[0]
    decorated = decorate_controlled_stimulus_payload(phase11)
    for key in ("stimulus_id", "kind", "headline", "body", "corrects_stimulus_id"):
        assert decorated[key] == phase11[key]
    assert decorated["source_label"] == "Market News Report"
    assert decorated["source_descriptor"] == "Market media report"


def test_phase11_visibility_prevents_future_correction_source_cue_leakage():
    material = load_material(FORMAL_STIMULUS, formal=True)
    engine = StimulusEngine(material)

    before = engine.participant_payload(
        7, moment=VisibilityMoment.PRE_CORRECTION_RELEASE
    )
    after = engine.participant_payload(
        7, moment=VisibilityMoment.POST_CORRECTION_RELEASE
    )

    before_decorated = tuple(decorate_controlled_stimulus_payload(x) for x in before)
    after_decorated = tuple(decorate_controlled_stimulus_payload(x) for x in after)
    assert [x["stimulus_id"] for x in before_decorated] == ["MISINFO_MEI_OWNERSHIP_001"]
    assert [x["stimulus_id"] for x in after_decorated] == [
        "MISINFO_MEI_OWNERSHIP_001",
        "CORRECTION_MEI_OWNERSHIP_001",
    ]
    assert after_decorated[1]["source_label"] == "LONGi Green Energy"
    assert after_decorated[1]["source_descriptor"] == "Official company announcement"


def test_misinformation_source_cue_is_invariant_across_visible_horizon():
    material = load_material(FORMAL_STIMULUS, formal=True)
    engine = StimulusEngine(material)

    states = (
        engine.participant_payload(
            0, moment=VisibilityMoment.POST_MISINFORMATION_RELEASE
        ),
        engine.participant_payload(
            7, moment=VisibilityMoment.PRE_CORRECTION_RELEASE
        ),
        engine.participant_payload(
            7, moment=VisibilityMoment.POST_CORRECTION_RELEASE
        ),
        engine.participant_payload(14),
    )

    misinformation_cues = []
    for payloads in states:
        decorated = tuple(decorate_controlled_stimulus_payload(x) for x in payloads)
        misinformation = next(
            x for x in decorated if x["stimulus_id"] == "MISINFO_MEI_OWNERSHIP_001"
        )
        misinformation_cues.append(
            (misinformation["source_label"], misinformation["source_descriptor"])
        )

    assert misinformation_cues == [
        ("Market News Report", "Market media report"),
        ("Market News Report", "Market media report"),
        ("Market News Report", "Market media report"),
        ("Market News Report", "Market media report"),
    ]


def test_unknown_or_overwide_controlled_payload_fails_closed():
    with pytest.raises(SourceCueError):
        decorate_controlled_stimulus_payload(
            {
                "stimulus_id": "UNKNOWN",
                "kind": "misinformation",
                "headline": "x",
                "body": "y",
                "corrects_stimulus_id": None,
            }
        )
    with pytest.raises(SourceCueError):
        decorate_controlled_stimulus_payload(
            {
                "stimulus_id": "MISINFO_MEI_OWNERSHIP_001",
                "kind": "misinformation",
                "headline": "x",
                "body": "y",
                "corrects_stimulus_id": None,
                "internal_truth_label": "false",
            }
        )


def test_adapter_contains_no_timing_graph_or_forum_logic():
    source = inspect.getsource(adapter_module)
    assert "get_top_n_users_by_degree" not in source
    assert "is_top_user" not in source.replace("``is_top_user``", "")
    assert "ForumDB" not in source
    assert "create_post_db" not in source
    assert "experiment_step" not in source
    assert "agent_world_date" not in source
