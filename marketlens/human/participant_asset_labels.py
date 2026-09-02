"""Frozen participant-facing English labels for MarketLens assets.

The inherited TwinMarket asset universe remains authoritative for
stock identity, ordering, pricing and market semantics. This module
controls only the English display labels exposed through the
MarketLens participant interface.

No live translation or fallback to inherited Chinese labels is
permitted in participant-facing projections.
"""
from __future__ import annotations

from collections.abc import Iterable
from types import MappingProxyType
from typing import Mapping


PARTICIPANT_ASSET_LABEL_VERSION = (
    "marketlens-participant-asset-labels-v1"
)

PARTICIPANT_ASSET_LABEL_STATUS = "FORMAL_FROZEN"

PARTICIPANT_ASSET_LABELS: Mapping[str, str] = MappingProxyType(
    {
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
)


PARTICIPANT_ASSET_SHORT_LABEL_VERSION = (
    "marketlens-participant-asset-short-labels-v1"
)

PARTICIPANT_ASSET_SHORT_LABEL_STATUS = "FORMAL_FROZEN"

PARTICIPANT_ASSET_SHORT_LABELS: Mapping[str, str] = MappingProxyType(
    {
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
)


class ParticipantAssetLabelError(ValueError):
    """Participant-facing asset labels are missing or drifted."""


def validate_participant_asset_labels(
    asset_ids: Iterable[str],
) -> tuple[str, ...]:
    resolved = tuple(
        str(stock_id).strip()
        for stock_id in asset_ids
    )

    expected = tuple(
        PARTICIPANT_ASSET_LABELS.keys()
    )

    short_expected = tuple(
        PARTICIPANT_ASSET_SHORT_LABELS.keys()
    )

    if short_expected != expected:
        raise ParticipantAssetLabelError(
            "full and short participant-facing asset "
            "label universes disagree"
        )

    if resolved != expected:
        raise ParticipantAssetLabelError(
            "participant-facing asset label universe "
            "disagrees with the inherited AssetCatalog "
            f"(expected={expected!r}, actual={resolved!r})"
        )

    return resolved


def participant_asset_display_name(
    stock_id: str,
) -> str:
    resolved = str(stock_id).strip()

    try:
        return PARTICIPANT_ASSET_LABELS[
            resolved
        ]
    except KeyError as exc:
        raise ParticipantAssetLabelError(
            "no frozen participant-facing English "
            f"label exists for asset {resolved!r}"
        ) from exc


def participant_asset_short_name(
    stock_id: str,
) -> str:
    resolved = str(stock_id).strip()

    try:
        return PARTICIPANT_ASSET_SHORT_LABELS[
            resolved
        ]
    except KeyError as exc:
        raise ParticipantAssetLabelError(
            "no frozen participant-facing short "
            f"label exists for asset {resolved!r}"
        ) from exc
