"""Canonical-price helpers for MarketLens validation tools.

The helper implementations were recovered from the archived superseded
account-capacity diagnostic and moved into this tracked module so that
formal cash-only validation no longer depends on the archived c35 code.
"""
from __future__ import annotations
from pathlib import Path
from typing import Mapping
from typing import Sequence
import importlib
import inspect
import math

def _extract_close(value: object) -> float:
    if hasattr(value, "close"):
        value = getattr(value, "close")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"Invalid canonical close price: {result}")
    return result

def canonical_price_matrix(
    provider: object,
    *,
    asset_ids: Sequence[str],
    period_dates: Sequence[str],
) -> dict[str, dict[str, float]]:
    matrix: dict[str, dict[str, float]] = {}
    for date in period_dates:
        matrix[date] = {
            stock_id: _extract_close(provider.get_close(stock_id, date))
            for stock_id in asset_ids
        }
    return matrix

def load_canonical_journey_price_providers(repo_root: Path) -> Mapping[str, object]:
    """Load the same canonical journey price-provider factory used by participant runtime.

    The current MarketLens test suite has used a one-root-argument factory. A few
    conservative invocation forms are supported here so that this offline tool does
    not force a runtime refactor if the parameter name changes.
    """
    module = importlib.import_module("marketlens.human.services.journey_provider_factory")
    factory = getattr(module, "build_canonical_journey_price_providers")
    signature = inspect.signature(factory)

    attempts: list[tuple[str, callable]] = [
        ("positional repo_root", lambda: factory(repo_root)),
        ("repo_root keyword", lambda: factory(repo_root=repo_root)),
        ("project_root keyword", lambda: factory(project_root=repo_root)),
        ("root keyword", lambda: factory(root=repo_root)),
    ]
    if not signature.parameters:
        attempts.append(("no arguments", lambda: factory()))

    errors: list[str] = []
    for label, attempt in attempts:
        try:
            providers = attempt()
        except TypeError as exc:
            errors.append(f"{label}: {exc}")
            continue
        if not isinstance(providers, Mapping) or not providers:
            raise RuntimeError("Canonical journey price-provider factory returned no episode providers")
        return providers

    raise RuntimeError(
        "Unable to call build_canonical_journey_price_providers with the supported root forms. "
        f"Signature={signature}; attempts={' | '.join(errors)}"
    )
