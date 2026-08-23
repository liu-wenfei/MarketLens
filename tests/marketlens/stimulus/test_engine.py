from __future__ import annotations

import pytest

from marketlens.stimulus import StimulusEngine, StimulusVisibilityError, VisibilityMoment, load_material


def engine() -> StimulusEngine:
    return StimulusEngine(load_material())


def ids(items):
    return [item.stimulus_id for item in items]


def test_release_dates_are_derived_from_phase10_protocol_not_material():
    subject = engine()
    assert subject.misinformation_step == 0
    assert subject.correction_step == 7
    assert subject.release_dates() == {
        "misinformation": "2023-06-19",
        "authoritative_correction": "2023-06-30",
    }


def test_same_state_j0_j1_requires_explicit_pre_post_release_moment():
    subject = engine()
    assert ids(subject.visible_stimuli(0, moment=VisibilityMoment.PRE_MISINFORMATION_RELEASE)) == []
    assert ids(subject.visible_stimuli(0, moment=VisibilityMoment.POST_MISINFORMATION_RELEASE)) == ["MISINFO_DEV_001"]
    with pytest.raises(StimulusVisibilityError, match="same-state J0/J1"):
        subject.visible_stimuli(0)


def test_misinformation_persists_on_all_intermediate_decision_steps():
    subject = engine()
    for step in range(1, 7):
        assert ids(subject.visible_stimuli(step)) == ["MISINFO_DEV_001"]


def test_same_state_j2_j3_requires_explicit_pre_post_correction_moment():
    subject = engine()
    assert ids(subject.visible_stimuli(7, moment=VisibilityMoment.PRE_CORRECTION_RELEASE)) == ["MISINFO_DEV_001"]
    assert ids(subject.visible_stimuli(7, moment=VisibilityMoment.POST_CORRECTION_RELEASE)) == [
        "MISINFO_DEV_001",
        "CORRECTION_DEV_001",
    ]
    with pytest.raises(StimulusVisibilityError, match="same-state J2/J3"):
        subject.visible_stimuli(7)


def test_correction_is_added_without_deleting_historical_misinformation_through_j4():
    subject = engine()
    for step in range(8, 15):
        assert ids(subject.visible_stimuli(step)) == ["MISINFO_DEV_001", "CORRECTION_DEV_001"]
    assert subject.checkpoint_date(14) == "2023-07-11"


def test_release_specific_moment_is_invalid_on_behaviour_only_checkpoint():
    subject = engine()
    with pytest.raises(StimulusVisibilityError):
        subject.visible_stimuli(3, moment=VisibilityMoment.POST_MISINFORMATION_RELEASE)


def test_unknown_or_closed_world_position_cannot_be_forged_as_participant_checkpoint():
    subject = engine()
    with pytest.raises(StimulusVisibilityError, match="unknown participant"):
        subject.visible_stimuli(15)


def test_participant_payload_is_allow_list_and_contains_no_internal_hash_or_source_fields():
    payload = engine().participant_payload(7, moment=VisibilityMoment.POST_CORRECTION_RELEASE)
    assert len(payload) == 2
    assert set(payload[0]) == {"stimulus_id", "kind", "headline", "body", "corrects_stimulus_id"}
    flattened = repr(payload)
    assert "sha256" not in flattened
    assert "formal_use_status" not in flattened
    assert "source" not in flattened
