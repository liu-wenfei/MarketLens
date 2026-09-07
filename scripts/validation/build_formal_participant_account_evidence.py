#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd


FORMAL_PROFILE_ID = "marketlens-participant-cash-only-v1"
FORMAL_INITIAL_CASH = 10_000.0
FORMAL_FEE_BPS = 0.0
FORMAL_CAP = None

FEE10_DIR = Path("artifacts/participant_cash_endowment_validation_v1")
FEE0_DIR = Path("artifacts/participant_cash_endowment_validation_v1_fee0")
DEFAULT_OUTPUT = Path("artifacts/formal_participant_account_validation_v1")

KEY_SOURCE_FILES = (
    Path("config/formal_participant_account_v1.json"),
    Path("config/participant_cash_endowment_candidates_v1.json"),
    Path("marketlens/human/portfolio/formal_account.py"),
    Path("marketlens/validation/cash_only_account.py"),
    Path("scripts/validation/run_cash_only_account_validation.py"),
    Path("scripts/validation/build_formal_participant_account_evidence.py"),
    Path("tests/marketlens/human/test_formal_participant_account_freeze.py"),
    Path("tests/marketlens/validation/test_cash_only_account_validation.py"),
    Path("marketlens/participant_server.py"),
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(root: Path, *cmd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def require_file(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"FAIL: required evidence file missing: {path}")


def require_dir(path: Path) -> None:
    if not path.is_dir():
        raise SystemExit(f"FAIL: required evidence directory missing: {path}")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def source_hashes(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in KEY_SOURCE_FILES:
        path = root / rel
        require_file(path)
        out[str(rel)] = sha256_file(path)
    return out


def directory_hashes(root: Path, rel_dir: Path) -> dict[str, str]:
    base = root / rel_dir
    require_dir(base)
    out: dict[str, str] = {}
    for path in sorted(p for p in base.rglob("*") if p.is_file()):
        out[str(path.relative_to(root))] = sha256_file(path)
    return out


def validate_formal_config(root: Path) -> dict[str, Any]:
    path = root / "config/formal_participant_account_v1.json"
    require_file(path)
    raw = json.loads(path.read_text(encoding="utf-8"))

    expected = {
        "profile_id": FORMAL_PROFILE_ID,
        "status": "formal_frozen",
        "initial_cash": FORMAL_INITIAL_CASH,
        "initial_holdings": {},
        "transaction_cost_bps": FORMAL_FEE_BPS,
        "max_position_weight": FORMAL_CAP,
        "whole_units": True,
        "allow_short": False,
        "allow_leverage": False,
    }
    for key, value in expected.items():
        if raw.get(key) != value:
            raise SystemExit(
                f"FAIL: formal config drift for {key}: "
                f"expected={value!r}, actual={raw.get(key)!r}"
            )
    return raw


def cash_resolution_summary(root: Path) -> dict[str, Any]:
    path = root / FEE10_DIR / "granularity_probes.csv"
    require_file(path)
    df = pd.read_csv(path)
    x = df[df["initial_cash"] == FORMAL_INITIAL_CASH]
    if x.empty:
        raise SystemExit("FAIL: no 10,000 cash rows in granularity_probes.csv")
    return {
        "initial_cash": FORMAL_INITIAL_CASH,
        "canonical_price_min": float(x["unit_price"].min()),
        "canonical_price_max": float(x["unit_price"].max()),
        "below_one_unit": int(x["below_one_unit"].sum()),
        "max_one_unit_fraction_pp": float(x["one_unit_fraction_pp"].max()),
        "max_relative_order_error": float(
            x["relative_shortfall_of_requested_order"].max()
        ),
        "max_portfolio_weight_error": float(
            x["shortfall_fraction_of_initial_wealth"].max()
        ),
        "probe_order_fractions": sorted(
            float(v) for v in x["target_order_fraction"].unique()
        ),
        "interpretation": (
            "Standardised engineering resolution probes; these fractions are "
            "not participant-facing selectable order increments."
        ),
    }


def deterministic_summary(root: Path, rel_dir: Path) -> dict[str, Any]:
    path = root / rel_dir / "deterministic_summary.csv"
    require_file(path)
    df = pd.read_csv(path)
    x = df[
        (df["initial_cash"] == FORMAL_INITIAL_CASH)
        & (df["path_class"] == "research_relevant")
    ]
    if x.empty:
        raise SystemExit(f"FAIL: no formal-cash research paths in {path}")
    return {
        "cases": int(len(x)),
        "orders_requested": int(x["orders_requested"].sum()),
        "orders_executed": int(x["orders_executed"].sum()),
        "invalid_orders": int(x["invalid_orders"].sum()),
        "critical_invalid_orders": int(x["critical_invalid_orders"].sum()),
        "invalid_cash": int(x["invalid_cash"].sum()),
        "invalid_holdings": int(x["invalid_holdings"].sum()),
        "invalid_position_limit": int(x["invalid_position_limit"].sum()),
        "invalid_below_one_unit": int(x["invalid_below_one_unit"].sum()),
        "min_cash_ratio": float(x["min_cash_ratio"].min()),
    }


def run_position_cap_audit(root: Path, out_dir: Path) -> dict[str, Any]:
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
        family_id="cash_only_endowment_fee0_nocap_v1",
    )
    providers = load_canonical_journey_price_providers(root)

    paths = {
        k: v
        for k, v in deterministic_stress_paths(config).items()
        if not k.startswith("boundary_")
    }

    caps = [
        ("10%", 0.10),
        ("13%", 0.13),
        ("20%", 0.20),
        ("25%", 0.25),
        ("None", None),
    ]

    rows: list[dict[str, Any]] = []
    for cap_name, cap in caps:
        profile = CashEndowmentProfile(
            profile_id=f"cash10000-fee0-cap-{cap_name}",
            initial_cash=FORMAL_INITIAL_CASH,
            transaction_cost_bps=FORMAL_FEE_BPS,
            max_position_weight=cap,
        )
        for episode_id in sorted(providers):
            matrix = canonical_price_matrix(
                providers[episode_id],
                asset_ids=config.asset_ids,
                period_dates=config.period_dates,
            )
            for path_id, intents in paths.items():
                summary, _ = run_deterministic_path(
                    profile=profile,
                    episode_id=episode_id,
                    price_matrix=matrix,
                    config=config,
                    path_id=path_id,
                    intents=intents,
                )
                rows.append(
                    {
                        "cap": cap_name,
                        "episode_id": episode_id,
                        "path_id": path_id,
                        "orders_requested": summary["orders_requested"],
                        "orders_executed": summary["orders_executed"],
                        "invalid_orders": summary["invalid_orders"],
                        "position_limit": summary["invalid_position_limit"],
                        "cash_invalid": summary["invalid_cash"],
                        "holdings_invalid": summary["invalid_holdings"],
                    }
                )

    detail = pd.DataFrame(rows)
    detail_path = out_dir / "position_cap_audit_detail.csv"
    detail.to_csv(detail_path, index=False)

    summary_df = (
        detail.groupby("cap", sort=False)
        .agg(
            cases=("path_id", "count"),
            orders_requested=("orders_requested", "sum"),
            orders_executed=("orders_executed", "sum"),
            invalid_orders=("invalid_orders", "sum"),
            position_limit=("position_limit", "sum"),
            cash_invalid=("cash_invalid", "sum"),
            holdings_invalid=("holdings_invalid", "sum"),
        )
        .reset_index()
    )
    summary_path = out_dir / "position_cap_audit_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    binding = detail[detail["position_limit"] > 0]
    binding_path = out_dir / "position_cap_binding_detail.csv"
    binding.to_csv(binding_path, index=False)

    by_cap = {
        str(row["cap"]): {
            "cases": int(row["cases"]),
            "orders_requested": int(row["orders_requested"]),
            "orders_executed": int(row["orders_executed"]),
            "invalid_orders": int(row["invalid_orders"]),
            "position_limit": int(row["position_limit"]),
            "cash_invalid": int(row["cash_invalid"]),
            "holdings_invalid": int(row["holdings_invalid"]),
        }
        for _, row in summary_df.iterrows()
    }

    return {
        "by_cap": by_cap,
        "binding_cases": binding[
            ["cap", "episode_id", "path_id", "position_limit"]
        ].to_dict(orient="records"),
        "decision": "None",
        "decision_basis": (
            "10% and 13% caps mechanically constrained the focal "
            "build-then-correction-unwind path. 20%, 25%, and None did not "
            "bind in the predefined research-relevant paths. None was selected "
            "to avoid unnecessary censoring because the participant is "
            "price-taking and cannot affect the canonical market."
        ),
    }


def run_regressions(root: Path, out_dir: Path) -> dict[str, Any]:
    checks: list[tuple[str, tuple[str, ...]]] = [
        ("git_diff_check", ("git", "diff", "--check")),
        (
            "targeted_tests",
            (
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/marketlens/human/test_formal_participant_account_freeze.py",
                "tests/marketlens/human/test_phase14b3c1_runtime_wiring.py",
            ),
        ),
        (
            "human_backend_tests",
            (
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/marketlens/human",
            ),
        ),
        (
            "cash_validation_tests",
            (
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/marketlens/validation/test_cash_only_account_validation.py",
            ),
        ),
    ]

    results: dict[str, Any] = {}
    for name, cmd in checks:
        proc = run_cmd(root, *cmd)
        write_text(out_dir / f"{name}.txt", proc.stdout)
        results[name] = {
            "command": list(cmd),
            "returncode": proc.returncode,
            "passed": proc.returncode == 0,
            "output_file": f"{name}.txt",
        }
        if proc.returncode != 0:
            raise SystemExit(
                f"FAIL: regression command failed: {name}\n{proc.stdout}"
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    root = args.repo_root.resolve()
    out_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else root / args.output_dir
    )

    require_dir(root / FEE10_DIR)
    require_dir(root / FEE0_DIR)

    if out_dir.exists():
        if not args.overwrite:
            raise SystemExit(
                f"FAIL: output directory already exists: {out_dir}\n"
                "Use --overwrite only if intentionally rebuilding the evidence."
            )
    else:
        out_dir.mkdir(parents=True, exist_ok=False)

    formal_config = validate_formal_config(root)

    git_branch = run_cmd(root, "git", "branch", "--show-current").stdout.strip()
    git_head = run_cmd(root, "git", "rev-parse", "HEAD").stdout.strip()
    git_status_before = run_cmd(root, "git", "status", "--short").stdout
    write_text(out_dir / "git_status_before.txt", git_status_before)

    cash_summary = cash_resolution_summary(root)
    fee10_summary = deterministic_summary(root, FEE10_DIR)
    fee0_summary = deterministic_summary(root, FEE0_DIR)
    cap_summary = run_position_cap_audit(root, out_dir)
    regressions = run_regressions(root, out_dir)

    evidence = {
        "schema_version": "1.0",
        "evidence_id": "marketlens-formal-participant-account-validation-v1",
        "formal_profile_id": FORMAL_PROFILE_ID,
        "formal_account": {
            "initial_cash": FORMAL_INITIAL_CASH,
            "initial_holdings": {},
            "transaction_cost_bps": FORMAL_FEE_BPS,
            "max_position_weight": FORMAL_CAP,
            "whole_units": True,
            "allow_short": False,
            "allow_leverage": False,
        },
        "git": {
            "branch": git_branch,
            "head": git_head,
            "status_file": "git_status_before.txt",
        },
        "cash_endowment": {
            "decision": 10_000.0,
            "resolution_summary": cash_summary,
            "research_relevant_fee10_summary": fee10_summary,
            "decision_basis": (
                "10,000 was the smallest already-implemented simple cash "
                "endowment shown adequate for all predefined research-relevant "
                "deterministic paths; larger endowments improved whole-unit "
                "resolution but did not add behavioural feasibility."
            ),
        },
        "transaction_fee": {
            "decision_bps": 0.0,
            "fee10_research_relevant_summary": fee10_summary,
            "fee0_research_relevant_summary": fee0_summary,
            "decision_basis": (
                "Both 10 bps and 0 bps preserved research-relevant execution "
                "feasibility. Because transaction cost was not part of the "
                "experimental construct, 0 bps was selected to avoid an "
                "unnecessary behavioural friction."
            ),
        },
        "position_cap": cap_summary,
        "runtime_formalisation": {
            "behaviour_change_intended": False,
            "startup_assertion": True,
            "manifest_status": formal_config["status"],
        },
        "regressions": regressions,
        "superseded_development_diagnostics": {
            "status": "not formal participant-account evidence",
            "paths": [
                "artifacts/account_capacity_validation/",
                "artifacts/account_capacity_validation_v2/",
                "artifacts/account_capacity_validation_v2_fee0/",
                "config/account_capacity_candidates_v1.json",
            ],
            "note": (
                "Historical c35 evidence assumed non-zero initial risky "
                "holdings and is retained only as superseded development "
                "diagnostic material."
            ),
        },
    }

    summary_path = out_dir / "formal_account_validation_summary.json"
    summary_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    hashes: dict[str, str] = {}
    hashes.update(source_hashes(root))
    hashes.update(directory_hashes(root, FEE10_DIR))
    hashes.update(directory_hashes(root, FEE0_DIR))

    # Hash generated bundle files except manifest itself.
    for path in sorted(p for p in out_dir.iterdir() if p.is_file()):
        hashes[str(path.relative_to(root))] = sha256_file(path)

    manifest = {
        "schema_version": "1.0",
        "evidence_id": "marketlens-formal-participant-account-validation-v1",
        "formal_profile_id": FORMAL_PROFILE_ID,
        "git_branch": git_branch,
        "git_head": git_head,
        "sha256": dict(sorted(hashes.items())),
        "summary_file": str(summary_path.relative_to(root)),
        "reproducibility_note": (
            "Hashes identify the formal account configuration, validation "
            "implementation, source validation artifacts, generated cap audit, "
            "and regression evidence used for the formal participant-account "
            "freeze."
        ),
    }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("=" * 72)
    print("PASS: formal participant-account evidence bundle created")
    print("=" * 72)
    print(f"output_dir={out_dir}")
    print(f"profile_id={FORMAL_PROFILE_ID}")
    print(f"git_branch={git_branch}")
    print(f"git_head={git_head}")
    print()
    print("FORMAL ACCOUNT")
    print("  initial_cash=10000")
    print("  initial_holdings=none")
    print("  fee=0bps")
    print("  position_cap=none")
    print("  whole_units=yes")
    print("  short=no")
    print("  leverage=no")
    print()
    print("KEY EVIDENCE")
    print(
        f"  cash research cases={fee0_summary['cases']} "
        f"invalid={fee0_summary['invalid_orders']}"
    )
    for cap, row in cap_summary["by_cap"].items():
        print(
            f"  cap={cap}: executed={row['orders_executed']}/"
            f"{row['orders_requested']} "
            f"position_limit={row['position_limit']}"
        )
    print()
    for name, result in regressions.items():
        print(f"  {name}: {'PASS' if result['passed'] else 'FAIL'}")
    print()
    print(f"summary={summary_path}")
    print(f"manifest={manifest_path}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
