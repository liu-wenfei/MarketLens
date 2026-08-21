from __future__ import annotations

from datetime import date

import pytest

from marketlens.market.price_provider import CsvClosePriceProvider, PriceNotFoundError


def test_price_provider_reads_exact_inherited_close_price():
    price = CsvClosePriceProvider().get_close("TLEI", "2023-06-15")

    assert price.stock_id == "TLEI"
    assert price.date == date(2023, 6, 15)
    assert price.close == pytest.approx(11.34)


def test_price_provider_accepts_date_object():
    price = CsvClosePriceProvider().get_close("FSEI", date(2023, 6, 15))
    assert price.date == date(2023, 6, 15)
    assert price.close > 0


def test_price_provider_does_not_fall_forward_or_return_latest_price():
    provider = CsvClosePriceProvider()

    with pytest.raises(PriceNotFoundError):
        provider.get_close("TLEI", "2099-01-01")
