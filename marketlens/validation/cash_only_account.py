from __future__ import annotations

from dataclasses import dataclass
import json
import math
import random
from pathlib import Path
from statistics import median
from typing import Mapping, Sequence

from marketlens.human.portfolio.models import AccountState
from marketlens.human.portfolio.policy import PortfolioPolicy
from marketlens.human.portfolio.preview import PortfolioAction, PreviewReason, preview_order
from marketlens.human.portfolio.settlement import execute_preview
from marketlens.validation.account_capacity import (
    canonical_price_matrix,
    load_canonical_journey_price_providers,
)


@dataclass(frozen=True)
class CashEndowmentProfile:
    profile_id: str
    initial_cash: float
    transaction_cost_bps: float
    max_position_weight: float | None = None

    def policy(self) -> PortfolioPolicy:
        return PortfolioPolicy(
            transaction_cost_bps=self.transaction_cost_bps,
            max_position_weight=self.max_position_weight,
            whole_units=True,
            allow_short=False,
            allow_leverage=False,
        )


@dataclass(frozen=True)
class CashOnlyValidationConfig:
    family_id: str
    family_description: str
    target_stock_id: str
    asset_ids: tuple[str, ...]
    period_dates: tuple[str, ...]
    critical_periods: frozenset[int]
    order_fraction_probes: tuple[float, ...]
    profiles: tuple[CashEndowmentProfile, ...]


@dataclass(frozen=True)
class TradeIntent:
    period_number: int
    stock_id: str
    action: PortfolioAction
    portfolio_fraction: float
    label: str


def load_cash_only_config(path: Path, *, family_id: str) -> CashOnlyValidationConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    family = raw["families"].get(family_id)
    if family is None:
        raise ValueError(f"unknown family {family_id!r}")

    cap_raw = family.get("max_position_weight")
    cap = None if cap_raw is None else float(cap_raw)
    fee = float(family["transaction_cost_bps"])

    profiles = tuple(
        CashEndowmentProfile(
            profile_id=f"cash-{int(float(value))}",
            initial_cash=float(value),
            transaction_cost_bps=fee,
            max_position_weight=cap,
        )
        for value in family["initial_cash_candidates"]
    )

    return CashOnlyValidationConfig(
        family_id=family_id,
        family_description=str(family["description"]),
        target_stock_id=str(raw["target_stock_id"]),
        asset_ids=tuple(str(x) for x in raw["asset_ids"]),
        period_dates=tuple(str(x) for x in raw["period_dates"]),
        critical_periods=frozenset(int(x) for x in raw["critical_periods"]),
        order_fraction_probes=tuple(float(x) for x in raw["order_fraction_probes"]),
        profiles=profiles,
    )


def build_initial_account(profile: CashEndowmentProfile) -> AccountState:
    """Formal-design candidate: initial cash only, zero initial holdings."""
    return AccountState(cash=float(profile.initial_cash), positions={})


def deterministic_stress_paths(
    config: CashOnlyValidationConfig,
) -> dict[str, tuple[TradeIntent, ...]]:
    assets = list(config.asset_ids)
    target = config.target_stock_id

    def intent(period: int, stock: str, action: PortfolioAction, frac: float, label: str):
        return TradeIntent(period, stock, action, frac, label)

    return {
        "hold_all": (),
        "focal_buy5_p1": (
            intent(1, target, PortfolioAction.BUY, 0.05, "P1 focal BUY 5% PV"),
        ),
        "focal_buy10_p1": (
            intent(1, target, PortfolioAction.BUY, 0.10, "P1 focal BUY 10% PV"),
        ),
        "same_period_5asset_buy5": tuple(
            intent(1, a, PortfolioAction.BUY, 0.05, f"P1 BUY 5% #{i}")
            for i, a in enumerate(assets[:5], 1)
        ),
        "same_period_10asset_buy5": tuple(
            intent(1, a, PortfolioAction.BUY, 0.05, f"P1 BUY 5% #{i}")
            for i, a in enumerate(assets, 1)
        ),
        "same_period_5asset_buy10": tuple(
            intent(1, a, PortfolioAction.BUY, 0.10, f"P1 BUY 10% #{i}")
            for i, a in enumerate(assets[:5], 1)
        ),
        "distributed_build_then_partial_unwind": (
            intent(1, assets[0], PortfolioAction.BUY, 0.10, "P1 BUY 10%"),
            intent(2, assets[1], PortfolioAction.BUY, 0.10, "P2 BUY 10%"),
            intent(3, assets[2], PortfolioAction.BUY, 0.10, "P3 BUY 10%"),
            intent(4, assets[3], PortfolioAction.BUY, 0.10, "P4 BUY 10%"),
            intent(8, assets[0], PortfolioAction.SELL, 0.05, "P8 SELL 5%"),
            intent(8, assets[1], PortfolioAction.SELL, 0.05, "P8 SELL 5%"),
        ),
        "focal_build_then_correction_unwind": (
            intent(1, target, PortfolioAction.BUY, 0.10, "P1 focal BUY 10%"),
            intent(4, target, PortfolioAction.BUY, 0.10, "P4 focal BUY 10%"),
            intent(8, target, PortfolioAction.SELL, 0.10, "P8 focal SELL 10%"),
            intent(15, target, PortfolioAction.SELL, 0.05, "P15 focal SELL 5%"),
        ),
        "late_same_period_5asset_buy5": tuple(
            intent(15, a, PortfolioAction.BUY, 0.05, f"P15 BUY 5% #{i}")
            for i, a in enumerate(assets[5:], 1)
        ),
        "boundary_full_deployment_10asset_buy10": tuple(
            intent(1, a, PortfolioAction.BUY, 0.10, f"P1 boundary BUY 10% #{i}")
            for i, a in enumerate(assets, 1)
        ),
    }


def _path_class(path_id: str) -> str:
    return "boundary" if path_id.startswith("boundary_") else "research_relevant"


def run_deterministic_path(
    *,
    profile: CashEndowmentProfile,
    episode_id: str,
    price_matrix: Mapping[str, Mapping[str, float]],
    config: CashOnlyValidationConfig,
    path_id: str,
    intents: Sequence[TradeIntent],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    account = build_initial_account(profile)
    policy = profile.policy()
    rows: list[dict[str, object]] = []
    min_cash_ratio = 1.0

    by_period: dict[int, list[TradeIntent]] = {}
    for item in intents:
        by_period.setdefault(item.period_number, []).append(item)

    for period, date in enumerate(config.period_dates, 1):
        prices = price_matrix[date]
        for order_index, item in enumerate(by_period.get(period, ()), 1):
            pv_before = account.total_value(prices)
            requested = pv_before * item.portfolio_fraction
            price = float(prices[item.stock_id])
            cash_before = float(account.cash)
            holding_before = int(account.positions.get(item.stock_id, 0))

            preview = preview_order(
                account=account,
                stock_id=item.stock_id,
                action=item.action,
                requested_amount=requested,
                price=price,
                prices=prices,
                policy=policy,
            )
            valid = bool(preview.valid)
            executed = float(preview.executed_notional) if valid else 0.0
            fee = float(preview.fee) if valid else 0.0
            if valid:
                account = execute_preview(account, preview)

            pv_after = account.total_value(prices)
            cash_ratio = float(account.cash) / pv_after if pv_after else 0.0
            min_cash_ratio = min(min_cash_ratio, cash_ratio)
            error = abs(requested - executed)

            reason = preview.reason_code.value if preview.reason_code is not None else ""
            max_valid = (
                float(preview.maximum_valid_amount)
                if preview.maximum_valid_amount is not None
                else requested
            )

            rows.append({
                "family_id": config.family_id,
                "profile_id": profile.profile_id,
                "initial_cash": profile.initial_cash,
                "episode_id": episode_id,
                "path_id": path_id,
                "path_class": _path_class(path_id),
                "period_number": period,
                "date": date,
                "critical_period": period in config.critical_periods,
                "order_index": order_index,
                "label": item.label,
                "stock_id": item.stock_id,
                "action": item.action.value,
                "requested_fraction": item.portfolio_fraction,
                "requested_amount": requested,
                "unit_price": price,
                "one_unit_fraction_of_pv": price / pv_before if pv_before else 0.0,
                "valid": valid,
                "reason_code": reason,
                "maximum_valid_amount": max_valid,
                "executed_notional": executed,
                "fee": fee,
                "relative_execution_error": error / requested if requested else 0.0,
                "execution_error_fraction_of_pv": error / pv_before if pv_before else 0.0,
                "cash_before": cash_before,
                "cash_after": float(account.cash),
                "holding_before": holding_before,
                "holding_after": int(account.positions.get(item.stock_id, 0)),
                "portfolio_value_before": pv_before,
                "portfolio_value_after": pv_after,
            })

    invalid = [r for r in rows if not r["valid"]]
    valid_rows = [r for r in rows if r["valid"]]
    reasons = {reason.value: 0 for reason in PreviewReason}
    for row in invalid:
        reasons[str(row["reason_code"])] += 1

    final_prices = price_matrix[config.period_dates[-1]]
    summary = {
        "family_id": config.family_id,
        "profile_id": profile.profile_id,
        "initial_cash": profile.initial_cash,
        "episode_id": episode_id,
        "path_id": path_id,
        "path_class": _path_class(path_id),
        "orders_requested": len(rows),
        "orders_executed": len(valid_rows),
        "invalid_orders": len(invalid),
        "critical_invalid_orders": sum(1 for r in invalid if r["critical_period"]),
        "invalid_cash": reasons[PreviewReason.INSUFFICIENT_CASH.value],
        "invalid_holdings": reasons[PreviewReason.INSUFFICIENT_HOLDINGS.value],
        "invalid_position_limit": reasons[PreviewReason.POSITION_LIMIT.value],
        "invalid_below_one_unit": reasons[PreviewReason.BELOW_ONE_UNIT.value],
        "min_cash_ratio": min_cash_ratio,
        "mean_relative_execution_error": (
            sum(float(r["relative_execution_error"]) for r in valid_rows) / len(valid_rows)
            if valid_rows else 0.0
        ),
        "max_relative_execution_error": (
            max(float(r["relative_execution_error"]) for r in valid_rows)
            if valid_rows else 0.0
        ),
        "max_execution_error_fraction_of_pv": (
            max(float(r["execution_error_fraction_of_pv"]) for r in valid_rows)
            if valid_rows else 0.0
        ),
        "final_cash": float(account.cash),
        "final_portfolio_value": account.total_value(final_prices),
        "final_distinct_holdings": sum(1 for q in account.positions.values() if q > 0),
    }
    return summary, rows


def granularity_probe_rows(
    *,
    profile: CashEndowmentProfile,
    episode_id: str,
    price_matrix: Mapping[str, Mapping[str, float]],
    config: CashOnlyValidationConfig,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for period, date in enumerate(config.period_dates, 1):
        for stock_id in config.asset_ids:
            price = float(price_matrix[date][stock_id])
            for fraction in config.order_fraction_probes:
                requested = profile.initial_cash * fraction
                units = math.floor(requested / price)
                executed = units * price
                shortfall = max(0.0, requested - executed)
                rows.append({
                    "family_id": config.family_id,
                    "profile_id": profile.profile_id,
                    "initial_cash": profile.initial_cash,
                    "episode_id": episode_id,
                    "period_number": period,
                    "date": date,
                    "critical_period": period in config.critical_periods,
                    "stock_id": stock_id,
                    "unit_price": price,
                    "one_unit_fraction_pp": price / profile.initial_cash * 100.0,
                    "target_order_fraction": fraction,
                    "requested_amount": requested,
                    "whole_units": units,
                    "executed_notional_before_fee": executed,
                    "below_one_unit": units < 1,
                    "notional_shortfall": shortfall,
                    "shortfall_fraction_of_initial_wealth": shortfall / profile.initial_cash,
                    "relative_shortfall_of_requested_order": (
                        shortfall / requested if requested else 0.0
                    ),
                })
    return rows


def granularity_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, float], list[Mapping[str, object]]] = {}
    for row in rows:
        key = (str(row["profile_id"]), str(row["episode_id"]), float(row["initial_cash"]))
        groups.setdefault(key, []).append(row)

    output = []
    for (profile_id, episode_id, initial_cash), group in groups.items():
        unit_pp = [float(r["one_unit_fraction_pp"]) for r in group]
        rel = [float(r["relative_shortfall_of_requested_order"]) for r in group]
        wealth = [float(r["shortfall_fraction_of_initial_wealth"]) for r in group]
        output.append({
            "profile_id": profile_id,
            "initial_cash": initial_cash,
            "episode_id": episode_id,
            "probe_count": len(group),
            "below_one_unit_count": sum(1 for r in group if r["below_one_unit"]),
            "max_one_unit_fraction_pp": max(unit_pp),
            "median_one_unit_fraction_pp": median(unit_pp),
            "max_relative_shortfall_of_requested_order": max(rel),
            "median_relative_shortfall_of_requested_order": median(rel),
            "max_shortfall_fraction_of_initial_wealth": max(wealth),
        })
    return output


def generate_resolution_probes(
    *, config: CashOnlyValidationConfig, n: int, seed: int
) -> list[tuple[int, str, float]]:
    """Random order-resolution probes, not a participant-behaviour model."""
    rng = random.Random(seed)
    return [
        (
            rng.randint(1, len(config.period_dates)),
            rng.choice(config.asset_ids),
            rng.choice(config.order_fraction_probes),
        )
        for _ in range(n)
    ]


def monte_carlo_resolution_summary(
    *,
    profile: CashEndowmentProfile,
    episode_id: str,
    price_matrix: Mapping[str, Mapping[str, float]],
    config: CashOnlyValidationConfig,
    probes: Sequence[tuple[int, str, float]],
) -> dict[str, object]:
    relative_errors = []
    wealth_errors = []
    below = 0

    for period, stock_id, fraction in probes:
        date = config.period_dates[period - 1]
        price = float(price_matrix[date][stock_id])
        requested = profile.initial_cash * fraction
        units = math.floor(requested / price)
        if units < 1:
            below += 1
            relative_errors.append(1.0)
            wealth_errors.append(fraction)
        else:
            error = max(0.0, requested - units * price)
            relative_errors.append(error / requested)
            wealth_errors.append(error / profile.initial_cash)

    def q(values, p):
        ordered = sorted(values)
        if not ordered:
            return 0.0
        return ordered[int(round((len(ordered) - 1) * p))]

    return {
        "family_id": config.family_id,
        "profile_id": profile.profile_id,
        "initial_cash": profile.initial_cash,
        "episode_id": episode_id,
        "probe_count": len(probes),
        "below_one_unit_rate": below / len(probes) if probes else 0.0,
        "mean_relative_order_shortfall": (
            sum(relative_errors) / len(relative_errors) if relative_errors else 0.0
        ),
        "p95_relative_order_shortfall": q(relative_errors, 0.95),
        "p99_relative_order_shortfall": q(relative_errors, 0.99),
        "mean_shortfall_fraction_of_initial_wealth": (
            sum(wealth_errors) / len(wealth_errors) if wealth_errors else 0.0
        ),
        "p95_shortfall_fraction_of_initial_wealth": q(wealth_errors, 0.95),
    }
