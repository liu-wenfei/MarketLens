from __future__ import annotations

import pytest

from marketlens.market.asset_catalog import AssetCatalog, AssetNotFoundError


def test_inherited_asset_catalog_loads_ten_sector_instruments():
    catalog = AssetCatalog()

    assert len(catalog) == 10
    assert set(catalog.ids()) == {
        "TLEI",
        "MEI",
        "CPEI",
        "IEEI",
        "REEI",
        "TSEI",
        "CGEI",
        "TTEI",
        "EREI",
        "FSEI",
    }


def test_asset_catalog_preserves_source_meaning_without_confusing_portfolio_weight():
    asset = AssetCatalog().get("TLEI")

    assert asset.name == "交通与运输指数"
    assert asset.industry == "交通与运输"
    assert asset.market_weight == pytest.approx(2.182)
    assert "中远海控" in asset.description
    assert "中国船舶" in asset.description


def test_source_market_weights_are_the_original_approximately_100_percent_universe():
    total = sum(asset.market_weight for asset in AssetCatalog().all())
    assert total == pytest.approx(100.001, abs=0.001)


def test_unknown_asset_is_rejected():
    with pytest.raises(AssetNotFoundError):
        AssetCatalog().get("NOT-A-REAL-ASSET")
