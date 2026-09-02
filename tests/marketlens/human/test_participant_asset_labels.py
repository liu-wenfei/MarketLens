from __future__ import annotations

from pathlib import Path

import pytest

from marketlens.human.participant_asset_labels import (
    PARTICIPANT_ASSET_LABEL_STATUS,
    PARTICIPANT_ASSET_LABEL_VERSION,
    PARTICIPANT_ASSET_LABELS,
    ParticipantAssetLabelError,
    participant_asset_display_name,
    validate_participant_asset_labels,
)
from marketlens.market.asset_catalog import AssetCatalog


ROOT = Path(__file__).resolve().parents[3]


EXPECTED_LABELS = {
    "TLEI": "Transportation & Logistics Index",
    "MEI": "Manufacturing Index",
    "CPEI": "Chemicals & Pharmaceuticals Index",
    "IEEI": "Infrastructure & Engineering Index",
    "REEI": "Real Estate Index",
    "TSEI": "Tourism & Services Index",
    "CGEI": "Consumer Goods Index",
    "TTEI": "Technology & Telecommunications Index",
    "EREI": "Energy & Resources Index",
    "FSEI": "Financial Services Index",
}


def test_frozen_participant_asset_labels_match_inherited_universe_exactly():
    catalog = AssetCatalog(
        ROOT / "data" / "stock_profile.csv"
    )

    assert PARTICIPANT_ASSET_LABEL_VERSION == (
        "marketlens-participant-asset-labels-v1"
    )

    assert PARTICIPANT_ASSET_LABEL_STATUS == (
        "FORMAL_FROZEN"
    )

    assert dict(
        PARTICIPANT_ASSET_LABELS
    ) == EXPECTED_LABELS

    assert catalog.ids() == tuple(
        EXPECTED_LABELS
    )

    assert validate_participant_asset_labels(
        catalog.ids()
    ) == catalog.ids()


def test_participant_asset_labels_are_english_display_text():
    for stock_id, label in (
        PARTICIPANT_ASSET_LABELS.items()
    ):
        assert stock_id
        assert label
        assert label.isascii()
        assert label.endswith("Index")


def test_unknown_or_drifted_asset_identity_fails_closed():
    with pytest.raises(
        ParticipantAssetLabelError
    ):
        participant_asset_display_name(
            "UNKNOWN"
        )

    with pytest.raises(
        ParticipantAssetLabelError
    ):
        validate_participant_asset_labels(
            (
                "MEI",
                "TLEI",
            )
        )
