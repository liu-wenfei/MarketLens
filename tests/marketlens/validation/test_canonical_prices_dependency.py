from __future__ import annotations

import importlib
from pathlib import Path


def test_cash_only_validation_has_no_active_c35_dependency() -> None:
    module = importlib.import_module("marketlens.validation.cash_only_account")
    assert callable(module.canonical_price_matrix)
    assert callable(module.load_canonical_journey_price_providers)

    root = Path(__file__).resolve().parents[3]
    source = (
        root / "marketlens/validation/cash_only_account.py"
    ).read_text(encoding="utf-8")

    assert "marketlens.validation.account_capacity" not in source
    assert "marketlens.validation.canonical_prices" in source
    assert not (
        root / "marketlens/validation/account_capacity.py"
    ).exists()


def test_canonical_price_helpers_are_importable() -> None:
    module = importlib.import_module(
        "marketlens.validation.canonical_prices"
    )
    assert callable(module.canonical_price_matrix)
    assert callable(module.load_canonical_journey_price_providers)
