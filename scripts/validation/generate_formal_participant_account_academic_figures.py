#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd


FORMAL_CASH = 10_000.0

DEFAULT_SOURCE_DIR = Path(
    "artifacts/formal_participant_account_experiment_report_v1"
)

DEFAULT_OUTPUT_DIR = Path(
    "artifacts/formal_participant_account_academic_figures_v1"
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
    if path.exists() and not overwrite:
        raise SystemExit(
            f"FAIL: output directory already exists: {path}\n"
            "Re-run with --overwrite."
        )

    path.mkdir(parents=True, exist_ok=True)


def load_inputs(
    source_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cash_path = source_dir / "cash_endowment_summary.csv"
    fee_path = source_dir / "fee_sensitivity_summary.csv"
    cap_path = source_dir / "position_cap_summary.csv"

    for path in (cash_path, fee_path, cap_path):
        require_file(path)

    cash = pd.read_csv(cash_path)
    fee = pd.read_csv(fee_path)
    cap = pd.read_csv(cap_path, keep_default_na=False)
    cap["cap"] = cap["cap"].replace({"None": "No cap"})

    require_columns(
        cash,
        {
            "initial_cash",
            "research_cases",
            "orders_requested",
            "orders_executed",
            "invalid_orders",
            "below_one_unit_count",
            "max_one_unit_pp",
            "worst_relative_execution_error",
        },
        "cash_endowment_summary.csv",
    )

    require_columns(
        fee,
        {
            "fee_label",
            "research_cases",
            "orders_requested",
            "orders_executed",
            "invalid_orders",
        },
        "fee_sensitivity_summary.csv",
    )

    require_columns(
        cap,
        {
            "cap",
            "orders_requested",
            "orders_executed",
            "execution_rate_pct",
            "position_limit_events",
        },
        "position_cap_summary.csv",
    )

    cash = cash.sort_values("initial_cash").reset_index(drop=True)
    return cash, fee, cap


def save_figure_cash_granularity(
    cash: pd.DataFrame,
    out_dir: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.8))

    x = cash["initial_cash"]
    y = cash["max_one_unit_pp"]

    ax.plot(x, y, marker="o", linewidth=1.4)

    formal = cash[cash["initial_cash"] == FORMAL_CASH]
    if not formal.empty:
        fx = float(formal.iloc[0]["initial_cash"])
        fy = float(formal.iloc[0]["max_one_unit_pp"])

        ax.scatter(
            [fx],
            [fy],
            marker="s",
            s=70,
            zorder=3,
        )

        ax.annotate(
            "Formal choice\n10,000",
            xy=(fx, fy),
            xytext=(22, -8),
            textcoords="offset points",
            ha="left",
            va="top",
            arrowprops=dict(
                arrowstyle="->",
                linewidth=0.8,
            ),
        )

    ax.set_xscale("log")

    ax.set_xlabel("Initial cash endowment (simulated units)")
    ax.set_ylabel(
        "Maximum one-unit portfolio share (percentage points)"
    )

    ax.grid(
        True,
        which="major",
        axis="both",
        linewidth=0.5,
        alpha=0.3,
    )

    ax.set_axisbelow(True)

    fig.tight_layout()

    fig.savefig(
        out_dir / "fig_main_cash_granularity_sensitivity.png",
        dpi=300,
        bbox_inches="tight",
    )
    fig.savefig(
        out_dir / "fig_main_cash_granularity_sensitivity.pdf",
        bbox_inches="tight",
    )

    plt.close(fig)


def save_figure_cap_execution(
    cap: pd.DataFrame,
    out_dir: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 4.6))

    x = list(range(len(cap)))
    y = cap["execution_rate_pct"].astype(float)

    ax.axhline(
        100.0,
        linewidth=1.0,
        linestyle="--",
        alpha=0.7,
    )

    ax.scatter(
        x,
        y,
        s=60,
        zorder=3,
    )

    for i, row in cap.iterrows():
        ax.annotate(
            f"{float(row['execution_rate_pct']):.1f}%",
            xy=(i, float(row["execution_rate_pct"])),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    ax.set_xticks(
        x,
        cap["cap"].astype(str),
    )

    ax.set_ylim(92, 101.5)

    ax.set_xlabel("Position cap")
    ax.set_ylabel("Executed requested orders (%)")

    ax.yaxis.set_major_formatter(
        PercentFormatter(xmax=100)
    )

    ax.grid(
        True,
        axis="y",
        linewidth=0.5,
        alpha=0.3,
    )

    ax.set_axisbelow(True)

    fig.tight_layout()

    fig.savefig(
        out_dir / "fig_main_position_cap_execution_sensitivity.png",
        dpi=300,
        bbox_inches="tight",
    )
    fig.savefig(
        out_dir / "fig_main_position_cap_execution_sensitivity.pdf",
        bbox_inches="tight",
    )

    plt.close(fig)


def save_figure_cash_execution_error(
    cash: pd.DataFrame,
    out_dir: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.8))

    x = cash["initial_cash"]
    y = 100.0 * cash["worst_relative_execution_error"]

    ax.plot(
        x,
        y,
        marker="o",
        linewidth=1.4,
    )

    formal = cash[cash["initial_cash"] == FORMAL_CASH]

    if not formal.empty:
        fx = float(formal.iloc[0]["initial_cash"])
        fy = 100.0 * float(
            formal.iloc[0]["worst_relative_execution_error"]
        )

        ax.scatter(
            [fx],
            [fy],
            marker="s",
            s=70,
            zorder=3,
        )

        ax.annotate(
            f"Formal choice\n{fy:.2f}%",
            xy=(fx, fy),
            xytext=(22, -8),
            textcoords="offset points",
            ha="left",
            va="top",
            arrowprops=dict(
                arrowstyle="->",
                linewidth=0.8,
            ),
        )

    ax.set_xscale("log")

    ax.set_xlabel("Initial cash endowment (simulated units)")
    ax.set_ylabel("Worst relative execution error (%)")

    ax.grid(
        True,
        which="major",
        linewidth=0.5,
        alpha=0.3,
    )

    ax.set_axisbelow(True)

    fig.tight_layout()

    fig.savefig(
        out_dir / "fig_appendix_cash_execution_error.png",
        dpi=300,
        bbox_inches="tight",
    )
    fig.savefig(
        out_dir / "fig_appendix_cash_execution_error.pdf",
        bbox_inches="tight",
    )

    plt.close(fig)


def save_tables(
    cash: pd.DataFrame,
    fee: pd.DataFrame,
    cap: pd.DataFrame,
    out_dir: Path,
) -> None:
    formal = cash[
        cash["initial_cash"] == FORMAL_CASH
    ]

    if formal.empty:
        raise SystemExit(
            "FAIL: formal 10,000 cash row missing"
        )

    row = formal.iloc[0]

    account_table = pd.DataFrame(
        [
            {
                "Design element": "Initial cash",
                "Formal setting": "10,000 simulated units",
                "Validation evidence": (
                    f"{int(row['research_cases'])} research-relevant cases; "
                    f"{int(row['orders_executed'])}/"
                    f"{int(row['orders_requested'])} orders executed; "
                    f"{int(row['invalid_orders'])} invalid orders"
                ),
            },
            {
                "Design element": "Initial holdings",
                "Formal setting": "None",
                "Validation evidence": (
                    "Cash-only start; no inherited risky exposure"
                ),
            },
            {
                "Design element": "Transaction fee",
                "Formal setting": "0 bps",
                "Validation evidence": (
                    "0 bps and 10 bps both preserved "
                    "research-relevant executability"
                ),
            },
            {
                "Design element": "Position cap",
                "Formal setting": "None",
                "Validation evidence": (
                    "10% and 13% bound predefined paths; "
                    "20%, 25% and None did not"
                ),
            },
            {
                "Design element": "Whole-unit settlement",
                "Formal setting": "Enabled",
                "Validation evidence": (
                    f"0 below-one-unit failures; "
                    f"max one-unit share "
                    f"{float(row['max_one_unit_pp']):.4f} pp"
                ),
            },
            {
                "Design element": "Short selling",
                "Formal setting": "Disabled",
                "Validation evidence": "Frozen long-only account contract",
            },
            {
                "Design element": "Leverage",
                "Formal setting": "Disabled",
                "Validation evidence": "Frozen unlevered account contract",
            },
        ]
    )

    account_table.to_csv(
        out_dir / "table_main_account_configuration_evidence.csv",
        index=False,
    )

    fee_table = fee[
        [
            "fee_label",
            "research_cases",
            "orders_requested",
            "orders_executed",
            "invalid_orders",
        ]
    ].copy()

    fee_table.columns = [
        "Fee",
        "Research-relevant cases",
        "Orders requested",
        "Orders executed",
        "Invalid orders",
    ]

    fee_table.to_csv(
        out_dir / "table_appendix_fee_sensitivity.csv",
        index=False,
    )

    cap_table = cap[
        [
            "cap",
            "orders_requested",
            "orders_executed",
            "execution_rate_pct",
            "position_limit_events",
        ]
    ].copy()

    cap_table.columns = [
        "Position cap",
        "Orders requested",
        "Orders executed",
        "Execution rate (%)",
        "Position-limit events",
    ]

    cap_table.to_csv(
        out_dir / "table_appendix_position_cap_audit.csv",
        index=False,
    )


def save_captions(
    out_dir: Path,
) -> None:
    text = """# Suggested dissertation captions

## Main-text figure 1

**Figure X. Pre-study sensitivity of whole-unit execution granularity to initial cash endowment.** The maximum value represented by a single tradable unit decreases as the simulated endowment increases. The formal 10,000-unit account is highlighted; this setting produced no below-one-unit failures in the predefined validation probes while preserving a maximum one-unit portfolio share of 0.1492 percentage points.

## Main-text figure 2

**Figure X. Order execution rate under alternative participant position caps.** Lower caps of 10% and 13% mechanically constrained predefined research-relevant allocation paths, reducing the execution rate to 94.6% (105/111 orders). Caps of 20% and 25%, and no position cap, allowed all 111 requested orders to execute. The no-cap configuration was retained to avoid unnecessary behavioural censoring in the price-taking participant account.

## Appendix figure

**Figure AX. Worst relative whole-unit execution error across initial cash endowments.** Larger endowments reduce the relative effect of integer-unit rounding. The 10,000-unit formal account remained fully executable across the predefined research-relevant paths despite a larger rounding error than higher-endowment candidates.

## Main-text table

**Table X. Final participant-account configuration and supporting pre-study validation evidence.**

## Appendix fee table

**Table AX. Transaction-fee sensitivity at the formal 10,000-unit endowment.** Both 0 bps and 10 bps preserved complete research-relevant executability, so the formal protocol omitted transaction costs to avoid adding construct-irrelevant behavioural friction.

## Appendix position-cap table

**Table AX. Deterministic position-cap behavioural-censoring audit.**
"""

    (
        out_dir / "suggested_captions.md"
    ).write_text(
        text,
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate dissertation-oriented academic figures and tables "
            "from the MarketLens participant-account experiment report."
        )
    )

    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
    )

    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    args = parser.parse_args()

    root = args.repo_root.resolve()

    source_dir = (
        args.source_dir
        if args.source_dir.is_absolute()
        else root / args.source_dir
    )

    output_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else root / args.output_dir
    )

    prepare_output_dir(
        output_dir,
        args.overwrite,
    )

    cash, fee, cap = load_inputs(
        source_dir
    )

    save_figure_cash_granularity(
        cash,
        output_dir,
    )

    save_figure_cap_execution(
        cap,
        output_dir,
    )

    save_figure_cash_execution_error(
        cash,
        output_dir,
    )

    save_tables(
        cash,
        fee,
        cap,
        output_dir,
    )

    save_captions(
        output_dir
    )

    print("=" * 72)
    print("PASS: academic participant-account figures generated")
    print("=" * 72)
    print(f"source_dir={source_dir}")
    print(f"output_dir={output_dir}")
    print()
    print("MAIN-TEXT FIGURES")
    print("  fig_main_cash_granularity_sensitivity.png / .pdf")
    print("  fig_main_position_cap_execution_sensitivity.png / .pdf")
    print()
    print("APPENDIX FIGURE")
    print("  fig_appendix_cash_execution_error.png / .pdf")
    print()
    print("TABLES")
    print("  table_main_account_configuration_evidence.csv")
    print("  table_appendix_fee_sensitivity.csv")
    print("  table_appendix_position_cap_audit.csv")
    print()
    print("CAPTIONS")
    print("  suggested_captions.md")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
