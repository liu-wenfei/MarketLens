#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd


FORMAL_CASH = 10_000.0
FEE10_FAMILY = "cash_only_endowment_fee10_nocap_v1"
FEE0_FAMILY = "cash_only_endowment_fee0_nocap_v1"

DEFAULT_OUTPUT_DIR = Path(
    "artifacts/formal_participant_account_experiment_report_v1"
)


def run_cmd(root: Path, cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def require_file(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"FAIL: required file missing: {path}")


def require_columns(
    df: pd.DataFrame,
    required: set[str],
    label: str,
) -> None:
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(
            f"FAIL: {label} missing columns: {sorted(missing)}\n"
            f"Available columns: {list(df.columns)}"
        )


def prepare_output_dir(path: Path, overwrite: bool) -> None:
    if path.exists():
        if not overwrite:
            raise SystemExit(
                f"FAIL: output directory already exists: {path}\n"
                "Re-run with --overwrite."
            )
        shutil.rmtree(path)

    path.mkdir(parents=True, exist_ok=False)


def rerun_family(
    *,
    root: Path,
    family: str,
    output_dir: Path,
    monte_carlo: int,
    seed: int,
    log_path: Path,
) -> None:
    cmd = [
        sys.executable,
        "scripts/validation/run_cash_only_account_validation.py",
        "--family",
        family,
        "--output-dir",
        str(output_dir.relative_to(root)),
        "--monte-carlo",
        str(monte_carlo),
        "--seed",
        str(seed),
    ]

    proc = run_cmd(root, cmd)
    log_path.write_text(proc.stdout, encoding="utf-8")

    if proc.returncode != 0:
        raise SystemExit(
            f"FAIL: validation family {family} failed.\n"
            f"See {log_path}\n\n{proc.stdout}"
        )


def aggregate_cash_endowment(validation_dir: Path) -> pd.DataFrame:
    summary_path = validation_dir / "deterministic_summary.csv"
    orders_path = validation_dir / "deterministic_orders.csv"
    gran_path = validation_dir / "granularity_summary.csv"

    require_file(summary_path)
    require_file(orders_path)
    require_file(gran_path)

    summary = pd.read_csv(summary_path)
    orders = pd.read_csv(orders_path)
    gran = pd.read_csv(gran_path)

    require_columns(
        summary,
        {
            "initial_cash",
            "path_class",
            "path_id",
            "orders_requested",
            "orders_executed",
            "invalid_orders",
            "critical_invalid_orders",
            "invalid_cash",
            "invalid_holdings",
            "invalid_position_limit",
            "invalid_below_one_unit",
            "min_cash_ratio",
        },
        "deterministic_summary.csv",
    )

    require_columns(
        orders,
        {
            "initial_cash",
            "path_class",
            "relative_execution_error",
            "execution_error_fraction_of_pv",
        },
        "deterministic_orders.csv",
    )

    require_columns(
        gran,
        {
            "initial_cash",
            "episode_id",
            "probe_count",
            "below_one_unit_count",
            "max_one_unit_fraction_pp",
            "max_relative_shortfall_of_requested_order",
            "max_shortfall_fraction_of_initial_wealth",
        },
        "granularity_summary.csv",
    )

    research = summary[
        summary["path_class"] == "research_relevant"
    ].copy()

    research_orders = orders[
        orders["path_class"] == "research_relevant"
    ].copy()

    if research.empty:
        raise SystemExit(
            "FAIL: no research_relevant deterministic summary rows"
        )

    if research_orders.empty:
        raise SystemExit(
            "FAIL: no research_relevant deterministic order rows"
        )

    counts = (
        research.groupby("initial_cash", as_index=False)
        .agg(
            research_cases=("path_id", "count"),
            orders_requested=("orders_requested", "sum"),
            orders_executed=("orders_executed", "sum"),
            invalid_orders=("invalid_orders", "sum"),
            critical_invalid_orders=(
                "critical_invalid_orders",
                "sum",
            ),
            invalid_cash=("invalid_cash", "sum"),
            invalid_holdings=("invalid_holdings", "sum"),
            invalid_position_limit=(
                "invalid_position_limit",
                "sum",
            ),
            invalid_below_one_unit=(
                "invalid_below_one_unit",
                "sum",
            ),
            min_cash_ratio=("min_cash_ratio", "min"),
        )
    )

    errors = (
        research_orders.groupby("initial_cash", as_index=False)
        .agg(
            worst_relative_execution_error=(
                "relative_execution_error",
                "max",
            ),
            worst_weight_execution_error=(
                "execution_error_fraction_of_pv",
                "max",
            ),
        )
    )

    granularity = (
        gran.groupby("initial_cash", as_index=False)
        .agg(
            granularity_probe_count=("probe_count", "sum"),
            below_one_unit_count=(
                "below_one_unit_count",
                "sum",
            ),
            max_one_unit_pp=(
                "max_one_unit_fraction_pp",
                "max",
            ),
            max_relative_order_error=(
                "max_relative_shortfall_of_requested_order",
                "max",
            ),
            max_portfolio_weight_error=(
                "max_shortfall_fraction_of_initial_wealth",
                "max",
            ),
        )
    )

    out = (
        counts.merge(
            errors,
            on="initial_cash",
            how="left",
        )
        .merge(
            granularity,
            on="initial_cash",
            how="left",
        )
        .sort_values("initial_cash")
        .reset_index(drop=True)
    )

    out["cash_label"] = out["initial_cash"].map(
        lambda x: (
            f"{int(x/1000)}k"
            if x < 1_000_000
            else "1m"
        )
    )
    out["worst_relative_execution_error_pct"] = (
        100.0 * out["worst_relative_execution_error"]
    )

    return out


def aggregate_fee(
    validation_dir: Path,
    label: str,
) -> dict[str, Any]:
    summary_path = validation_dir / "deterministic_summary.csv"
    orders_path = validation_dir / "deterministic_orders.csv"

    require_file(summary_path)
    require_file(orders_path)

    summary = pd.read_csv(summary_path)
    orders = pd.read_csv(orders_path)

    require_columns(
        summary,
        {
            "initial_cash",
            "path_class",
            "orders_requested",
            "orders_executed",
            "invalid_orders",
            "critical_invalid_orders",
            "invalid_cash",
            "invalid_holdings",
            "invalid_position_limit",
            "invalid_below_one_unit",
            "min_cash_ratio",
        },
        "deterministic_summary.csv",
    )

    require_columns(
        orders,
        {
            "initial_cash",
            "path_class",
            "relative_execution_error",
            "execution_error_fraction_of_pv",
        },
        "deterministic_orders.csv",
    )

    x = summary[
        (summary["initial_cash"] == FORMAL_CASH)
        & (summary["path_class"] == "research_relevant")
    ].copy()

    xo = orders[
        (orders["initial_cash"] == FORMAL_CASH)
        & (orders["path_class"] == "research_relevant")
    ].copy()

    if x.empty:
        raise SystemExit(
            f"FAIL: no formal-cash research summary rows in {summary_path}"
        )

    if xo.empty:
        raise SystemExit(
            f"FAIL: no formal-cash research order rows in {orders_path}"
        )

    orders_requested = int(x["orders_requested"].sum())
    orders_executed = int(x["orders_executed"].sum())

    return {
        "fee_label": label,
        "initial_cash": FORMAL_CASH,
        "research_cases": int(len(x)),
        "orders_requested": orders_requested,
        "orders_executed": orders_executed,
        "execution_rate_pct": (
            100.0 * orders_executed / orders_requested
            if orders_requested else 0.0
        ),
        "invalid_orders": int(x["invalid_orders"].sum()),
        "critical_invalid_orders": int(
            x["critical_invalid_orders"].sum()
        ),
        "invalid_cash": int(x["invalid_cash"].sum()),
        "invalid_holdings": int(x["invalid_holdings"].sum()),
        "invalid_position_limit": int(
            x["invalid_position_limit"].sum()
        ),
        "invalid_below_one_unit": int(
            x["invalid_below_one_unit"].sum()
        ),
        "min_cash_ratio": float(x["min_cash_ratio"].min()),
        "worst_relative_execution_error": float(
            xo["relative_execution_error"].max()
        ),
        "worst_weight_execution_error": float(
            xo["execution_error_fraction_of_pv"].max()
        ),
    }


def run_position_cap_audit(
    *,
    root: Path,
    output_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from marketlens.validation.cash_only_account import (
        CashEndowmentProfile,
        canonical_price_matrix,
        deterministic_stress_paths,
        load_canonical_journey_price_providers,
        load_cash_only_config,
        run_deterministic_path,
    )

    config = load_cash_only_config(
        root / "config/participant_cash_endowment_candidates_v1.json",
        family_id=FEE0_FAMILY,
    )

    providers = load_canonical_journey_price_providers(root)

    all_paths = deterministic_stress_paths(config)

    paths = {
        path_id: intents
        for path_id, intents in all_paths.items()
        if not path_id.startswith("boundary_")
    }

    caps = [
        ("10%", 0.10),
        ("13%", 0.13),
        ("20%", 0.20),
        ("25%", 0.25),
        ("None", None),
    ]

    rows: list[dict[str, Any]] = []

    for cap_label, cap in caps:
        profile = CashEndowmentProfile(
            profile_id=f"cash10000-fee0-cap-{cap_label}",
            initial_cash=FORMAL_CASH,
            transaction_cost_bps=0.0,
            max_position_weight=cap,
        )

        for episode_id in sorted(providers):
            matrix = canonical_price_matrix(
                providers[episode_id],
                asset_ids=config.asset_ids,
                period_dates=config.period_dates,
            )

            for path_id, intents in paths.items():
                path_summary, _ = run_deterministic_path(
                    profile=profile,
                    episode_id=episode_id,
                    price_matrix=matrix,
                    config=config,
                    path_id=path_id,
                    intents=intents,
                )

                rows.append(
                    {
                        "cap": cap_label,
                        "episode_id": episode_id,
                        "path_id": path_id,
                        "orders_requested": path_summary[
                            "orders_requested"
                        ],
                        "orders_executed": path_summary[
                            "orders_executed"
                        ],
                        "invalid_orders": path_summary[
                            "invalid_orders"
                        ],
                        "position_limit_events": path_summary[
                            "invalid_position_limit"
                        ],
                        "cash_invalid": path_summary[
                            "invalid_cash"
                        ],
                        "holdings_invalid": path_summary[
                            "invalid_holdings"
                        ],
                    }
                )

    detail = pd.DataFrame(rows)

    detail.to_csv(
        output_dir / "position_cap_audit_detail.csv",
        index=False,
    )

    summary = (
        detail.groupby("cap", sort=False)
        .agg(
            cases=("path_id", "count"),
            orders_requested=("orders_requested", "sum"),
            orders_executed=("orders_executed", "sum"),
            invalid_orders=("invalid_orders", "sum"),
            position_limit_events=(
                "position_limit_events",
                "sum",
            ),
            cash_invalid=("cash_invalid", "sum"),
            holdings_invalid=("holdings_invalid", "sum"),
        )
        .reset_index()
    )

    summary["execution_rate_pct"] = (
        100.0
        * summary["orders_executed"]
        / summary["orders_requested"]
    )

    summary.to_csv(
        output_dir / "position_cap_summary.csv",
        index=False,
    )

    binding = detail[
        detail["position_limit_events"] > 0
    ].copy()

    binding.to_csv(
        output_dir / "position_cap_binding_detail.csv",
        index=False,
    )

    return summary, binding


def _annotate_bar_values(ax, values, fmt: str, vertical_offset: float = 0.0) -> None:
    for i, value in enumerate(values):
        ax.text(
            i,
            float(value) + vertical_offset,
            fmt.format(value),
            ha="center",
            va="bottom",
        )


def chart_cash_granularity(
    df: pd.DataFrame,
    out: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 4.8))

    ax.bar(
        df["cash_label"],
        df["max_one_unit_pp"],
    )

    _annotate_bar_values(
        ax,
        df["max_one_unit_pp"],
        "{:.3f}",
        vertical_offset=max(df["max_one_unit_pp"]) * 0.02,
    )

    formal_idx = df.index[df["initial_cash"] == FORMAL_CASH][0]
    ax.annotate(
        "Formal choice: 10,000",
        xy=(formal_idx, float(df.loc[formal_idx, "max_one_unit_pp"])),
        xytext=(formal_idx, float(df["max_one_unit_pp"].max()) * 1.12),
        ha="center",
        arrowprops=dict(arrowstyle="->"),
    )

    ax.set_xlabel("Initial cash endowment")
    ax.set_ylabel("Maximum one-unit portfolio share (pp)")
    ax.set_title("Whole-unit granularity by cash endowment")
    ax.set_ylim(0, float(df["max_one_unit_pp"].max()) * 1.25)
    ax.grid(True, axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(
        out / "fig1_cash_granularity.png",
        dpi=240,
        bbox_inches="tight",
    )
    plt.close(fig)


def chart_cash_execution_error(
    df: pd.DataFrame,
    out: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 4.8))

    ax.bar(
        df["cash_label"],
        df["worst_relative_execution_error_pct"],
    )

    _annotate_bar_values(
        ax,
        df["worst_relative_execution_error_pct"],
        "{:.2f}%",
        vertical_offset=max(df["worst_relative_execution_error_pct"]) * 0.02,
    )

    formal_idx = df.index[df["initial_cash"] == FORMAL_CASH][0]
    ax.annotate(
        "Formal choice",
        xy=(formal_idx, float(df.loc[formal_idx, "worst_relative_execution_error_pct"])),
        xytext=(formal_idx, float(df["worst_relative_execution_error_pct"].max()) * 1.12),
        ha="center",
        arrowprops=dict(arrowstyle="->"),
    )

    ax.set_xlabel("Initial cash endowment")
    ax.set_ylabel("Worst relative execution error (%)")
    ax.set_title("Worst whole-unit execution error by cash endowment")
    ax.set_ylim(0, float(df["worst_relative_execution_error_pct"].max()) * 1.25)
    ax.grid(True, axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(
        out / "fig2_cash_execution_error.png",
        dpi=240,
        bbox_inches="tight",
    )
    plt.close(fig)


def chart_fee(
    df: pd.DataFrame,
    out: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(6.8, 4.8))

    ax.bar(
        df["fee_label"],
        df["execution_rate_pct"],
    )

    _annotate_bar_values(
        ax,
        df["execution_rate_pct"],
        "{:.1f}%",
        vertical_offset=0.3,
    )

    for i, row in enumerate(df.itertuples()):
        ax.text(
            i,
            max(0.5, float(row.execution_rate_pct) * 0.05),
            f"invalid={int(row.invalid_orders)}\nexecuted={int(row.orders_executed)}/{int(row.orders_requested)}",
            ha="center",
            va="bottom",
        )

    ax.set_xlabel("Transaction fee")
    ax.set_ylabel("Executed requested orders (%)")
    ax.set_title("Fee sensitivity at initial cash = 10,000")
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
    ax.grid(True, axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(
        out / "fig3_fee_sensitivity.png",
        dpi=240,
        bbox_inches="tight",
    )
    plt.close(fig)


def chart_cap_execution(
    df: pd.DataFrame,
    out: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7.4, 4.8))

    ax.bar(
        df["cap"],
        df["execution_rate_pct"],
    )

    _annotate_bar_values(
        ax,
        df["execution_rate_pct"],
        "{:.1f}%",
        vertical_offset=0.3,
    )

    ax.set_xlabel("Position cap")
    ax.set_ylabel("Executed requested orders (%)")
    ax.set_title("Execution rate under alternative position caps")
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
    ax.grid(True, axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(
        out / "fig4_position_cap_execution.png",
        dpi=240,
        bbox_inches="tight",
    )
    plt.close(fig)


def chart_cap_binding(
    df: pd.DataFrame,
    out: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7.4, 4.8))

    ax.bar(
        df["cap"],
        df["position_limit_events"],
    )

    _annotate_bar_values(
        ax,
        df["position_limit_events"],
        "{:.0f}",
        vertical_offset=0.05,
    )

    ax.set_xlabel("Position cap")
    ax.set_ylabel("Position-limit events")
    ax.set_title("Direct cap-binding events")
    ax.set_ylim(
        0,
        max(
            1.0,
            float(df["position_limit_events"].max()) + 0.8,
        ),
    )
    ax.grid(True, axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(
        out / "fig5_position_cap_bindings.png",
        dpi=240,
        bbox_inches="tight",
    )
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reproduce MarketLens participant-account validation "
            "and generate tables and figures."
        )
    )

    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )

    parser.add_argument(
        "--rerun-validation",
        action="store_true",
    )

    parser.add_argument(
        "--monte-carlo",
        type=int,
        default=1000,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=20260907,
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    args = parser.parse_args()

    root = args.repo_root.resolve()

    output_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else root / args.output_dir
    )

    prepare_output_dir(
        output_dir,
        args.overwrite,
    )

    if args.rerun_validation:
        fee10_dir = output_dir / "rerun_fee10"
        fee0_dir = output_dir / "rerun_fee0"

        rerun_family(
            root=root,
            family=FEE10_FAMILY,
            output_dir=fee10_dir,
            monte_carlo=args.monte_carlo,
            seed=args.seed,
            log_path=output_dir / "fee10_run.log",
        )

        rerun_family(
            root=root,
            family=FEE0_FAMILY,
            output_dir=fee0_dir,
            monte_carlo=args.monte_carlo,
            seed=args.seed,
            log_path=output_dir / "fee0_run.log",
        )

        source_mode = "fresh rerun"

    else:
        fee10_dir = (
            root
            / "artifacts/participant_cash_endowment_validation_v1"
        )

        fee0_dir = (
            root
            / "artifacts/participant_cash_endowment_validation_v1_fee0"
        )

        source_mode = "committed frozen artifacts"

    cash_df = aggregate_cash_endowment(fee0_dir)

    cash_df.to_csv(
        output_dir / "cash_endowment_summary.csv",
        index=False,
    )

    fee_df = pd.DataFrame(
        [
            aggregate_fee(
                fee10_dir,
                "10 bps",
            ),
            aggregate_fee(
                fee0_dir,
                "0 bps",
            ),
        ]
    )

    fee_df.to_csv(
        output_dir / "fee_sensitivity_summary.csv",
        index=False,
    )

    cap_df, binding_df = run_position_cap_audit(
        root=root,
        output_dir=output_dir,
    )

    chart_cash_granularity(
        cash_df,
        output_dir,
    )

    chart_cash_execution_error(
        cash_df,
        output_dir,
    )

    chart_fee(
        fee_df,
        output_dir,
    )

    chart_cap_execution(
        cap_df,
        output_dir,
    )

    chart_cap_binding(
        cap_df,
        output_dir,
    )

    formal_rows = cash_df[
        cash_df["initial_cash"] == FORMAL_CASH
    ]

    if formal_rows.empty:
        raise SystemExit(
            "FAIL: formal 10,000 cash profile missing"
        )

    formal_cash = formal_rows.iloc[0]

    experiment_summary = {
        "schema_version": "1.3",
        "experiment_id": (
            "marketlens-formal-participant-account-report-v1"
        ),
        "source_mode": source_mode,
        "seed": args.seed,
        "monte_carlo_paths": args.monte_carlo,
        "formal_account": {
            "initial_cash": 10000.0,
            "initial_holdings": {},
            "transaction_cost_bps": 0.0,
            "max_position_weight": None,
            "whole_units": True,
            "allow_short": False,
            "allow_leverage": False,
        },
        "cash_10000": {
            "research_cases": int(
                formal_cash["research_cases"]
            ),
            "orders_requested": int(
                formal_cash["orders_requested"]
            ),
            "orders_executed": int(
                formal_cash["orders_executed"]
            ),
            "invalid_orders": int(
                formal_cash["invalid_orders"]
            ),
            "below_one_unit_count": int(
                formal_cash["below_one_unit_count"]
            ),
            "max_one_unit_pp": float(
                formal_cash["max_one_unit_pp"]
            ),
            "worst_relative_execution_error": float(
                formal_cash[
                    "worst_relative_execution_error"
                ]
            ),
            "worst_weight_execution_error": float(
                formal_cash[
                    "worst_weight_execution_error"
                ]
            ),
        },
        "fee_sensitivity": fee_df.to_dict(
            orient="records"
        ),
        "position_cap": cap_df.to_dict(
            orient="records"
        ),
        "position_cap_binding_cases": binding_df.to_dict(
            orient="records"
        ),
    }

    (
        output_dir
        / "experiment_summary.json"
    ).write_text(
        json.dumps(
            experiment_summary,
            indent=2,
        ),
        encoding="utf-8",
    )

    readme = (
        "# MarketLens Participant Account Experiment Report\n\n"
        f"Source mode: `{source_mode}`\n\n"
        "## Generated figures\n\n"
        "- `fig1_cash_granularity.png`\n"
        "- `fig2_cash_execution_error.png`\n"
        "- `fig3_fee_sensitivity.png`\n"
        "- `fig4_position_cap_execution.png`\n"
        "- `fig5_position_cap_bindings.png`\n\n"
        "## Generated summaries\n\n"
        "- `cash_endowment_summary.csv`\n"
        "- `fee_sensitivity_summary.csv`\n"
        "- `position_cap_summary.csv`\n"
        "- `position_cap_audit_detail.csv`\n"
        "- `position_cap_binding_detail.csv`\n"
        "- `experiment_summary.json`\n"
    )

    (
        output_dir / "README.md"
    ).write_text(
        readme,
        encoding="utf-8",
    )

    print("=" * 72)
    print(
        "PASS: participant-account experiment report generated"
    )
    print("=" * 72)
    print(f"source_mode={source_mode}")
    print(f"output_dir={output_dir}")
    print()

    print("FORMAL CASH = 10,000")
    print(
        f"  research_cases="
        f"{int(formal_cash['research_cases'])}"
    )
    print(
        "  orders_executed="
        f"{int(formal_cash['orders_executed'])}/"
        f"{int(formal_cash['orders_requested'])}"
    )
    print(
        f"  invalid_orders="
        f"{int(formal_cash['invalid_orders'])}"
    )
    print(
        f"  below_one_unit_count="
        f"{int(formal_cash['below_one_unit_count'])}"
    )
    print(
        f"  max_one_unit_pp="
        f"{float(formal_cash['max_one_unit_pp']):.6f}"
    )
    print(
        "  worst_relative_execution_error="
        f"{float(formal_cash['worst_relative_execution_error']):.6f}"
    )
    print()

    print("FEE SENSITIVITY")
    print(
        fee_df[
            [
                "fee_label",
                "research_cases",
                "orders_requested",
                "orders_executed",
                "invalid_orders",
                "execution_rate_pct",
            ]
        ].to_string(
            index=False
        )
    )
    print()

    print("POSITION CAP")
    print(
        cap_df[
            [
                "cap",
                "orders_requested",
                "orders_executed",
                "execution_rate_pct",
                "position_limit_events",
            ]
        ].to_string(
            index=False
        )
    )
    print()

    print("FIGURES")
    for name in [
        "fig1_cash_granularity.png",
        "fig2_cash_execution_error.png",
        "fig3_fee_sensitivity.png",
        "fig4_position_cap_execution.png",
        "fig5_position_cap_bindings.png",
    ]:
        print(
            f"  {output_dir / name}"
        )

    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
