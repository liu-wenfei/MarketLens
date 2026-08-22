"""Delegate Agent-world market state transitions to inherited TwinMarket code.

This module intentionally contains no price-formation, order-matching, Agent
portfolio, or database-update mathematics.
"""

from __future__ import annotations

from datetime import date
import hashlib
from pathlib import Path
from typing import Iterable

import pandas as pd

from trader.matching_engine import (
    test_matching_system as _twinmarket_test_matching_system,
    update_profiles_table_holiday as _twinmarket_update_profiles_table_holiday,
)
from trader.utility import init_system as _twinmarket_init_system

from .models import InheritedMarketCallResult


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"current_date must be YYYY-MM-DD: {value!r}") from exc


def _existing_file(value: str | Path, *, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    return path


def _ensure_runtime_is_not_protected(
    runtime_db: Path,
    protected_paths: Iterable[str | Path],
) -> None:
    protected = {Path(p).expanduser().resolve() for p in protected_paths}
    if runtime_db in protected:
        raise ValueError(
            "refusing inherited TwinMarket mutation on a protected/frozen database: "
            f"{runtime_db}"
        )


def _result(
    *,
    inherited_function: str,
    current_date: str,
    runtime_db: Path,
    before: str,
) -> InheritedMarketCallResult:
    after = _sha256(runtime_db)
    return InheritedMarketCallResult(
        inherited_function=inherited_function,
        current_date=current_date,
        runtime_db=str(runtime_db),
        runtime_db_sha256_before=before,
        runtime_db_sha256_after=after,
        runtime_db_changed=(before != after),
    )


def reset_agent_world(
    *,
    current_date: str,
    runtime_db: str | Path,
    forum_db: str | Path,
    protected_paths: Iterable[str | Path] = (),
) -> InheritedMarketCallResult:
    """Call TwinMarket `init_system()` on an isolated writable Agent-world copy."""
    current_date = _iso_date(current_date)
    runtime = _existing_file(runtime_db, label="runtime database")
    forum = _existing_file(forum_db, label="forum database")
    _ensure_runtime_is_not_protected(runtime, protected_paths)

    before = _sha256(runtime)

    # Preserve the inherited call boundary used by simulation.py:
    # init_system(current_date, user_db, forum_db)
    _twinmarket_init_system(pd.Timestamp(current_date), str(runtime), str(forum))

    return _result(
        inherited_function="trader.utility.init_system",
        current_date=current_date,
        runtime_db=runtime,
        before=before,
    )


def advance_trading_day(
    *,
    current_date: str,
    runtime_db: str | Path,
    decision_json: str | Path,
    log_dir: str | Path,
    protected_paths: Iterable[str | Path] = (),
) -> InheritedMarketCallResult:
    """Call TwinMarket `test_matching_system()` exactly as the inherited loop does."""
    current_date = _iso_date(current_date)
    runtime = _existing_file(runtime_db, label="runtime database")
    decisions = _existing_file(decision_json, label="inherited decision JSON")
    output = Path(log_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    _ensure_runtime_is_not_protected(runtime, protected_paths)

    before = _sha256(runtime)

    _twinmarket_test_matching_system(
        current_date=current_date,
        base_path=str(output),
        db_path=str(runtime),
        json_file_path=str(decisions),
    )

    return _result(
        inherited_function="trader.matching_engine.test_matching_system",
        current_date=current_date,
        runtime_db=runtime,
        before=before,
    )


def advance_non_trading_day(
    *,
    current_date: str,
    runtime_db: str | Path,
    protected_paths: Iterable[str | Path] = (),
) -> InheritedMarketCallResult:
    """Call TwinMarket's inherited non-trading-day Profiles update."""
    current_date = _iso_date(current_date)
    runtime = _existing_file(runtime_db, label="runtime database")
    _ensure_runtime_is_not_protected(runtime, protected_paths)

    before = _sha256(runtime)

    _twinmarket_update_profiles_table_holiday(
        current_date=current_date,
        db_path=str(runtime),
    )

    return _result(
        inherited_function="trader.matching_engine.update_profiles_table_holiday",
        current_date=current_date,
        runtime_db=runtime,
        before=before,
    )
