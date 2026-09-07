#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.validation.cash_only_account import (
    canonical_price_matrix,
    deterministic_stress_paths,
    generate_resolution_probes,
    granularity_probe_rows,
    granularity_summary,
    load_cash_only_config,
    load_canonical_journey_price_providers,
    monte_carlo_resolution_summary,
    run_deterministic_path,
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=root, text=True, stderr=subprocess.STDOUT
        ).strip()
    except Exception as exc:
        return f"UNAVAILABLE: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/participant_cash_endowment_candidates_v1.json"),
    )
    parser.add_argument(
        "--family",
        default="cash_only_endowment_fee10_nocap_v1",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/participant_cash_endowment_validation_v1"),
    )
    parser.add_argument("--monte-carlo", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260907)
    args = parser.parse_args()

    root = args.repo_root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir

    config = load_cash_only_config(config_path, family_id=args.family)
    providers = load_canonical_journey_price_providers(root)
    paths = deterministic_stress_paths(config)
    random_probes = generate_resolution_probes(
        config=config, n=args.monte_carlo, seed=args.seed
    )

    det_summary = []
    det_orders = []
    granularity = []
    mc = []

    for episode_id in sorted(providers):
        matrix = canonical_price_matrix(
            providers[episode_id],
            asset_ids=config.asset_ids,
            period_dates=config.period_dates,
        )
        for profile in config.profiles:
            for path_id, intents in paths.items():
                summary, orders = run_deterministic_path(
                    profile=profile,
                    episode_id=episode_id,
                    price_matrix=matrix,
                    config=config,
                    path_id=path_id,
                    intents=intents,
                )
                det_summary.append(summary)
                det_orders.extend(orders)

            granularity.extend(
                granularity_probe_rows(
                    profile=profile,
                    episode_id=episode_id,
                    price_matrix=matrix,
                    config=config,
                )
            )
            mc.append(
                monte_carlo_resolution_summary(
                    profile=profile,
                    episode_id=episode_id,
                    price_matrix=matrix,
                    config=config,
                    probes=random_probes,
                )
            )

    gran_summary = granularity_summary(granularity)

    outputs = {
        "deterministic_summary.csv": det_summary,
        "deterministic_orders.csv": det_orders,
        "granularity_probes.csv": granularity,
        "granularity_summary.csv": gran_summary,
        "monte_carlo_resolution.csv": mc,
    }
    for name, rows in outputs.items():
        _write_csv(output_dir / name, rows)

    runner_path = Path(__file__).resolve()
    manifest = {
        "schema_version": "1.0",
        "validation_method_version": "marketlens-cash-only-endowment-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "family_id": config.family_id,
        "family_description": config.family_description,
        "design_contract": {
            "initial_holdings": "none",
            "initial_cash_fraction": 1.0,
            "whole_units": True,
            "short_selling": False,
            "leverage": False,
            "position_cap_in_endowment_sweep": None,
            "position_cap_note": "Position-cap sensitivity is deferred until initial cash endowment is selected."
        },
        "config_path": str(config_path.relative_to(root)),
        "config_sha256": _sha256(config_path),
        "runner_sha256": _sha256(runner_path),
        "git_branch": _git(root, "branch", "--show-current"),
        "git_head": _git(root, "rev-parse", "HEAD"),
        "git_status": _git(root, "status", "--short"),
        "episode_ids": sorted(providers),
        "asset_ids": list(config.asset_ids),
        "period_dates": list(config.period_dates),
        "critical_periods": sorted(config.critical_periods),
        "candidate_initial_cash": [p.initial_cash for p in config.profiles],
        "order_fraction_probes": list(config.order_fraction_probes),
        "deterministic_path_ids": sorted(paths),
        "monte_carlo_probe_count": args.monte_carlo,
        "monte_carlo_seed": args.seed,
        "interpretation_note": (
            "Random resolution probes are not a participant-behaviour model. "
            "They test whole-unit execution resolution across the frozen canonical "
            "price/date/asset space. Position-cap effects are intentionally excluded."
        ),
        "superseded_evidence_note": (
            "Earlier c25-c40/c35 artifacts assumed non-zero initial holdings and "
            "remain development diagnostics only."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(f"PASS: cash-only participant endowment validation completed for family={config.family_id}")
    print(
        f"episodes={len(providers)} profiles={len(config.profiles)} "
        f"deterministic_paths={len(paths)} resolution_probes={len(random_probes)}"
    )
    print(f"output_dir={output_dir}")
    print("files:")
    for name in [*outputs, "manifest.json"]:
        print(f"  {output_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
