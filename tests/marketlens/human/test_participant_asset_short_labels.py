from __future__ import annotations

from pathlib import Path

import pytest

from marketlens.human.participant_asset_labels import (
    PARTICIPANT_ASSET_LABELS,
    PARTICIPANT_ASSET_SHORT_LABEL_STATUS,
    PARTICIPANT_ASSET_SHORT_LABEL_VERSION,
    PARTICIPANT_ASSET_SHORT_LABELS,
    ParticipantAssetLabelError,
    participant_asset_short_name,
    validate_participant_asset_labels,
)
from marketlens.market.asset_catalog import AssetCatalog


ROOT = Path(__file__).resolve().parents[3]


EXPECTED = {
    "TLEI": "Transp. & Logistics",
    "MEI": "Manufacturing",
    "CPEI": "Chem. & Pharma",
    "IEEI": "Infra. & Eng.",
    "REEI": "Real Estate",
    "TSEI": "Tourism & Svcs.",
    "CGEI": "Consumer Goods",
    "TTEI": "Tech & Telecom",
    "EREI": "Energy & Resources",
    "FSEI": "Fin. Services",
}


def test_short_labels_are_frozen_and_universe_aligned():
    catalog = AssetCatalog(
        ROOT / "data" / "stock_profile.csv"
    )

    assert PARTICIPANT_ASSET_SHORT_LABEL_VERSION == (
        "marketlens-participant-asset-short-labels-v1"
    )

    assert PARTICIPANT_ASSET_SHORT_LABEL_STATUS == (
        "FORMAL_FROZEN"
    )

    assert dict(
        PARTICIPANT_ASSET_SHORT_LABELS
    ) == EXPECTED

    assert tuple(
        PARTICIPANT_ASSET_LABELS
    ) == tuple(
        PARTICIPANT_ASSET_SHORT_LABELS
    )

    assert validate_participant_asset_labels(
        catalog.ids()
    ) == catalog.ids()


def test_short_labels_are_compact_ascii():
    for label in (
        PARTICIPANT_ASSET_SHORT_LABELS.values()
    ):
        assert label
        assert label.isascii()
        assert len(label) <= 20


def test_unknown_short_label_fails_closed():
    with pytest.raises(
        ParticipantAssetLabelError
    ):
        participant_asset_short_name(
            "UNKNOWN"
        )
