"""Phase 9E zero-LLM population structural + activation sensitivity.

Fixed comparison:
- N10 / N20 / N30 / N40
- common Phase 3 selection seed: marketlens-dev-population-01
- 100 predeclared Phase 4 activation seeds, all retained
- fixed calendar: 2023-06-15 .. 2023-06-17 (OPEN / OPEN / CLOSED)
- common Phase 6 baseline graph cutoff: 2023-06-14

No Agent reasoning, LLM/API calls, market execution, forum mutation, or
participant data is used.  This produces decision inputs only; it does not
freeze the final formal population size.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PHASE09E_VERSION = "marketlens_phase09e_zero_llm_population_sensitivity/1.0"
BANNER = (
    "NON-FORMAL / PHASE 9E N10-N20-N30-N40 ZERO-LLM "
    "POPULATION SENSITIVITY / NOT FORMAL EXPERIMENT EVIDENCE"
)

POPULATION_SIZES = (10, 20, 30, 40)
POPULATION_SEED = "marketlens-dev-population-01"
REFERENCE_ACTIVATION_SEED = "marketlens-phase09b-activation-01"
ACTIVATION_GRID_SIZE = 100
ACTIVATION_GRID_SEEDS = tuple(
    f"marketlens-phase09e-activation-{i:03d}"
    for i in range(ACTIVATION_GRID_SIZE)
)

START_DATE = "2023-06-15"
END_DATE = "2023-06-17"
EXPECTED_DATES = ("2023-06-15", "2023-06-16", "2023-06-17")
EXPECTED_MARKET_OPEN = (True, True, False)

GRAPH_START_DATE = "2023-01-01"
GRAPH_HISTORY_CUTOFF = "2023-06-14"
SIMILARITY_THRESHOLD = 0.1
TIME_DECAY_FACTOR = 0.05
TOP_FRACTION = 0.10

EXPECTED_SOURCE_SHA256 = (
    "90b19c5cb9dac6708dff06fe4def5205cecef1a90da0f74eec449dab5a6769c3"
)
EXPECTED_N20_SELECTED_IDS_SHA256 = (
    "aef5f41ef8c2ef7883ae5167dee697766fe020c4d6f180ae086ada911329d740"
)
EXPECTED_N20_RUNTIME_SHA256 = (
    "b617769f590cadb00b0db28f80ec78bfd3b620f0f06bbc0bb254030ea3cb2d9c"
)
EXPECTED_N20_GRAPH_SHA256 = (
    "592293a45c7cfa066302272d2a378e2e9be0f6a66c7aa593030d451fabbab4f2"
)


class Phase09EError(RuntimeError):
    pass


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state(repo_root: str | Path) -> dict[str, str]:
    root = Path(repo_root)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root, text=True
    ).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=root, text=True
    ).strip()
    return {"commit": commit, "branch": branch, "status_porcelain": status}


def require_clean_git(repo_root: str | Path) -> dict[str, str]:
    state = git_state(repo_root)
    if state["status_porcelain"]:
        raise Phase09EError(
            "Phase 9E requires a clean Git working tree for reproducible evidence"
        )
    return state


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise Phase09EError(f"JSON root is not an object: {path}")
    return data


def _generate_fixture(
    *,
    repo_root: Path,
    source_db: Path,
    n: int,
    output_dir: Path,
) -> tuple[Path, Path, dict[str, Any]]:
    if n not in POPULATION_SIZES:
        raise Phase09EError(f"N outside fixed Phase 9E grid: {n}")
    if output_dir.exists():
        raise Phase09EError(f"fixture output already exists: {output_dir}")

    command = [
        sys.executable,
        "-m",
        "marketlens.agents.population.runtime_cli",
        "--source-db",
        str(source_db),
        "--population-size",
        str(n),
        "--seed",
        POPULATION_SEED,
        "--output-dir",
        str(output_dir),
    ]
    try:
        subprocess.run(
            command,
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        details = "\n".join(
            x for x in ((exc.stdout or "").strip(), (exc.stderr or "").strip())
            if x
        )
        raise Phase09EError(
            f"Phase 3 runtime_cli failed for N{n}"
            + (f":\n{details}" if details else "")
        ) from exc

    runtime_db = output_dir / "population_runtime.db"
    manifest_path = output_dir / "population_manifest.json"
    if not runtime_db.is_file() or not manifest_path.is_file():
        raise Phase09EError(f"incomplete Phase 3 fixture for N{n}")
    return runtime_db, manifest_path, _load_json(manifest_path)


def _population_summary(
    *, manifest: Mapping[str, Any], runtime_db: Path, n: int
) -> dict[str, Any]:
    source = manifest.get("source", {})
    selection = manifest.get("selection", {})
    selected = manifest.get("selected_population", {})
    fixture = manifest.get("runtime_fixture", {})

    if source.get("sha256") != EXPECTED_SOURCE_SHA256:
        raise Phase09EError(f"N{n} source hash drifted")
    if selection.get("seed") != POPULATION_SEED:
        raise Phase09EError(f"N{n} population seed drifted")
    if selection.get("population_size") != n:
        raise Phase09EError(f"N{n} population size drifted")

    ids = tuple(map(str, selection.get("selected_agent_ids", ())))
    if len(ids) != n or len(set(ids)) != n:
        raise Phase09EError(f"N{n} membership is incomplete or duplicated")

    runtime_sha = sha256_file(runtime_db)
    if fixture.get("fixture_sha256") != runtime_sha:
        raise Phase09EError(f"N{n} runtime hash does not match manifest")

    if n == 20:
        if selection.get("selected_agent_ids_sha256") != EXPECTED_N20_SELECTED_IDS_SHA256:
            raise Phase09EError("N20 membership drifted from verified Phase 3/5 fixture")
        if runtime_sha != EXPECTED_N20_RUNTIME_SHA256:
            raise Phase09EError("N20 runtime drifted from verified Phase 3/5 fixture")

    return {
        "size": n,
        "selection_seed": POPULATION_SEED,
        "selected_agent_ids": list(ids),
        "selected_agent_ids_sha256": selection.get("selected_agent_ids_sha256"),
        "runtime_sha256": runtime_sha,
        "strategy_counts": dict(selected.get("strategy_counts", {})),
        "user_type_counts": dict(selected.get("user_type_counts", {})),
        "joint_strategy_user_type_counts": dict(
            selected.get("joint_strategy_user_type_counts", {})
        ),
        "user_type_coverage": dict(selected.get("user_type_coverage", {})),
        "coverage_warnings": list(selected.get("coverage_warnings", ())),
        "n_user_types_observed": len(dict(selected.get("user_type_counts", {}))),
    }


def nested_membership_report(
    population_rows: Mapping[int, Mapping[str, Any]]
) -> dict[str, Any]:
    pairwise = []
    all_nested = True
    for smaller, larger in zip(POPULATION_SIZES, POPULATION_SIZES[1:]):
        small = set(map(str, population_rows[smaller]["selected_agent_ids"]))
        large = set(map(str, population_rows[larger]["selected_agent_ids"]))
        nested = small.issubset(large)
        all_nested = all_nested and nested
        pairwise.append(
            {
                "smaller_n": smaller,
                "larger_n": larger,
                "smaller_subset_of_larger": nested,
                "shared_ids": len(small & large),
            }
        )
    return {
        "same_selection_seed_all_n": True,
        "pairwise": pairwise,
        "strict_nested_family": all_nested,
        "interpretation": (
            "strict expanding same-seed population family"
            if all_nested
            else "not strictly nested; N differences also include membership variation"
        ),
    }


def _prominence_summary(
    snapshot: Mapping[str, Any], expected_top_n: int
) -> dict[str, Any]:
    prominence = snapshot.get("prominence")
    if not isinstance(prominence, Mapping):
        raise Phase09EError("Phase 6 prominence snapshot shape drifted")
    ids = tuple(map(str, prominence.get("top_user_ids", ())))
    if prominence.get("top_n") != expected_top_n or len(ids) != expected_top_n:
        raise Phase09EError("Phase 6 top-user count drifted")
    return {
        "top_n": expected_top_n,
        "top_user_ids": list(ids),
        "cutoff_degree": prominence.get("cutoff_degree"),
        "cutoff_tie_count": prominence.get("cutoff_tie_count"),
    }


def graph_metrics(runtime_db: Path, n: int) -> dict[str, Any]:
    import networkx as nx
    from marketlens.agents.social.graph import build_bounded_social_graph
    from marketlens.agents.social.prominence import make_prominence_snapshot

    before = sha256_file(runtime_db)
    built = build_bounded_social_graph(
        runtime_db=runtime_db,
        history_cutoff=GRAPH_HISTORY_CUTOFF,
        graph_start_date=GRAPH_START_DATE,
        similarity_threshold=SIMILARITY_THRESHOLD,
        time_decay_factor=TIME_DECAY_FACTOR,
    )
    after = sha256_file(runtime_db)
    if before != after:
        raise Phase09EError(f"N{n} graph build mutated runtime fixture")
    if built.n_nodes != n:
        raise Phase09EError(f"N{n} graph has {built.n_nodes} nodes")
    if n == 20 and built.graph_sha256 != EXPECTED_N20_GRAPH_SHA256:
        raise Phase09EError("N20 baseline graph drifted from verified Phase 6")

    degrees = [int(degree) for _, degree in built.graph.degree()]
    possible = n * (n - 1) / 2
    snapshot = make_prominence_snapshot(built, top_fraction=TOP_FRACTION)

    return {
        "n_nodes": n,
        "n_edges": built.n_edges,
        "density": built.n_edges / possible if possible else 0.0,
        "graph_sha256": built.graph_sha256,
        "degree_mean": statistics.fmean(degrees) if degrees else 0.0,
        "degree_median": statistics.median(degrees) if degrees else 0.0,
        "degree_min": min(degrees) if degrees else 0,
        "degree_max": max(degrees) if degrees else 0,
        "isolated_nodes": sum(1 for d in degrees if d == 0),
        "connected_components": nx.number_connected_components(built.graph),
        "prominence": _prominence_summary(
            snapshot, expected_top_n=int(n * TOP_FRACTION)
        ),
        "runtime_fixture_unchanged": True,
    }


def summarize_activation_windows(
    *, population_size: int, windows: Sequence[Sequence[int]]
) -> dict[str, Any]:
    rows = [tuple(map(int, row)) for row in windows]
    if not rows or any(len(row) != 3 for row in rows):
        raise Phase09EError("activation windows must be non-empty 3-day rows")

    flat = [value for row in rows for value in row]
    per_day = [[row[i] for row in rows] for i in range(3)]
    possible = len(rows) * 3 * population_size

    return {
        "population_size": population_size,
        "n_seeds": len(rows),
        "n_calendar_day_observations": len(flat),
        "activation_density": sum(flat) / possible,
        "mean_active_agents_per_day": statistics.fmean(flat),
        "median_active_agents_per_day": statistics.median(flat),
        "min_active_agents_per_day": min(flat),
        "max_active_agents_per_day": max(flat),
        "mean_active_agent_days_per_3day_window": statistics.fmean(
            sum(row) for row in rows
        ),
        "zero_active_day_frequency": sum(v == 0 for v in flat) / len(flat),
        "window_with_any_zero_active_day_frequency": (
            sum(any(v == 0 for v in row) for row in rows) / len(rows)
        ),
        "window_with_all_days_active_frequency": (
            sum(all(v > 0 for v in row) for row in rows) / len(rows)
        ),
        "closed_day_active_frequency": (
            sum(row[2] > 0 for row in rows) / len(rows)
        ),
        "day_specific": [
            {
                "step": i,
                "agent_world_date": EXPECTED_DATES[i],
                "market_open": EXPECTED_MARKET_OPEN[i],
                "mean_active": statistics.fmean(values),
                "median_active": statistics.median(values),
                "zero_active_frequency": sum(v == 0 for v in values) / len(values),
                "min_active": min(values),
                "max_active": max(values),
            }
            for i, values in enumerate(per_day)
        ],
    }


def activation_sensitivity(
    *, runtime_db: Path, n: int, trading_calendar: Path
) -> dict[str, Any]:
    from marketlens.agents.activation.policy import ActivationPolicy
    from marketlens.agents.activation.profiles import load_activation_profiles
    from marketlens.market.multiday import (
        build_calendar_day_plan,
        sample_activation_sequence,
    )
    from marketlens.market.runtime.news import load_trading_day_set

    profiles = tuple(load_activation_profiles(runtime_db))
    if len(profiles) != n:
        raise Phase09EError(f"N{n} activation profile count drifted")

    plan = build_calendar_day_plan(
        start_date=START_DATE,
        end_date=END_DATE,
        trading_days=load_trading_day_set(trading_calendar),
    )
    if tuple(day.current_date for day in plan) != EXPECTED_DATES:
        raise Phase09EError("Phase 9E calendar dates drifted")
    if tuple(day.market_open for day in plan) != EXPECTED_MARKET_OPEN:
        raise Phase09EError("Phase 9E calendar is not OPEN / OPEN / CLOSED")

    policy = ActivationPolicy()

    def counts(seed: str) -> tuple[int, int, int]:
        sequence = sample_activation_sequence(
            profiles, plan=plan, seed=seed, policy=policy
        )
        values = tuple(len(item.batch.active_agent_ids) for item in sequence)
        if len(values) != 3:
            raise Phase09EError("activation sequence length drifted")
        return values  # type: ignore[return-value]

    reference = counts(REFERENCE_ACTIVATION_SEED)
    if n == 20 and reference != (5, 3, 3):
        raise Phase09EError("N20 Phase 9B reference drifted from 5 / 3 / 3")

    windows = [counts(seed) for seed in ACTIVATION_GRID_SEEDS]
    return {
        "policy": "frozen Phase 4",
        "reference_seed": REFERENCE_ACTIVATION_SEED,
        "reference_active_counts": list(reference),
        "grid_definition": {
            "n_seeds": ACTIVATION_GRID_SIZE,
            "first_seed": ACTIVATION_GRID_SEEDS[0],
            "last_seed": ACTIVATION_GRID_SEEDS[-1],
            "all_predeclared_seeds_included": True,
            "seed_fishing": False,
        },
        "aggregate": summarize_activation_windows(
            population_size=n, windows=windows
        ),
        "windows": [
            {"seed": seed, "active_counts": list(window)}
            for seed, window in zip(ACTIVATION_GRID_SEEDS, windows)
        ],
    }


def marginal_comparison(
    rows: Mapping[int, Mapping[str, Any]], smaller_n: int, larger_n: int
) -> dict[str, Any]:
    s = rows[smaller_n]
    l = rows[larger_n]
    sa = s["activation"]["aggregate"]
    la = l["activation"]["aggregate"]
    sg = s["graph"]
    lg = l["graph"]

    s_work = sa["mean_active_agent_days_per_3day_window"]
    l_work = la["mean_active_agent_days_per_3day_window"]
    return {
        "from_n": smaller_n,
        "to_n": larger_n,
        "population_increase_fraction": (larger_n - smaller_n) / smaller_n,
        "mean_active_agent_days_per_window": {
            "from": s_work,
            "to": l_work,
            "increase_fraction": (
                (l_work - s_work) / s_work if s_work > 0 else None
            ),
        },
        "zero_active_window_frequency": {
            "from": sa["window_with_any_zero_active_day_frequency"],
            "to": la["window_with_any_zero_active_day_frequency"],
            "absolute_change": (
                la["window_with_any_zero_active_day_frequency"]
                - sa["window_with_any_zero_active_day_frequency"]
            ),
        },
        "closed_day_active_frequency": {
            "from": sa["closed_day_active_frequency"],
            "to": la["closed_day_active_frequency"],
            "absolute_change": (
                la["closed_day_active_frequency"]
                - sa["closed_day_active_frequency"]
            ),
        },
        "graph_edges": {
            "from": sg["n_edges"],
            "to": lg["n_edges"],
            "increase": lg["n_edges"] - sg["n_edges"],
        },
        "graph_density": {
            "from": sg["density"],
            "to": lg["density"],
            "absolute_change": lg["density"] - sg["density"],
        },
        "natural_user_type_count": {
            "from": s["population"]["n_user_types_observed"],
            "to": l["population"]["n_user_types_observed"],
        },
        "note": (
            "active-Agent-days are a zero-LLM workload proxy only; "
            "they are not an HTTP/backend-call count"
        ),
    }


def render_report(summary: Mapping[str, Any]) -> str:
    rows = summary["candidates"]

    def pct(x: float) -> str:
        return f"{100*x:.1f}%"

    lines = [
        "# Phase 9E — N10 / N20 / N30 / N40 Zero-LLM Population Sensitivity",
        "",
        f"**Status:** {summary['status']}",
        "",
        "**Evidence class:** NON-FORMAL ENGINEERING FEASIBILITY",
        "",
        "**LLM calls:** 0  ",
        "**Market execution:** NO  ",
        "**Forum mutation:** NO  ",
        "**Participant data:** NO",
        "",
        "## Fixed design",
        "",
        f"- Population sizes: `{list(POPULATION_SIZES)}`.",
        f"- Common Phase 3 selection seed: `{POPULATION_SEED}`.",
        f"- Activation sensitivity: {ACTIVATION_GRID_SIZE} predeclared seeds; all included.",
        f"- Calendar: `{START_DATE}` → `{END_DATE}` (OPEN / OPEN / CLOSED).",
        f"- Baseline graph cutoff: `{GRAPH_HISTORY_CUTOFF}`.",
        "",
        "## Comparison",
        "",
        "| Metric | N10 | N20 | N30 | N40 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]

    def get(n: int, *keys):
        value = rows[str(n)]
        for key in keys:
            value = value[key]
        return value

    table = [
        (
            "Strategy counts",
            [get(n, "population", "strategy_counts") for n in POPULATION_SIZES],
        ),
        (
            "Natural user_type counts",
            [get(n, "population", "user_type_counts") for n in POPULATION_SIZES],
        ),
        ("Graph edges", [get(n, "graph", "n_edges") for n in POPULATION_SIZES]),
        (
            "Graph density",
            [f"{get(n, 'graph', 'density'):.3f}" for n in POPULATION_SIZES],
        ),
        (
            "Mean degree",
            [f"{get(n, 'graph', 'degree_mean'):.2f}" for n in POPULATION_SIZES],
        ),
        (
            "Isolated nodes",
            [get(n, "graph", "isolated_nodes") for n in POPULATION_SIZES],
        ),
        (
            "Connected components",
            [get(n, "graph", "connected_components") for n in POPULATION_SIZES],
        ),
        (
            "Dynamic top-user count",
            [get(n, "graph", "prominence", "top_n") for n in POPULATION_SIZES],
        ),
        (
            "Reference activation counts",
            [get(n, "activation", "reference_active_counts") for n in POPULATION_SIZES],
        ),
        (
            "Mean active Agents/day (100 seeds)",
            [
                f"{get(n, 'activation', 'aggregate', 'mean_active_agents_per_day'):.2f}"
                for n in POPULATION_SIZES
            ],
        ),
        (
            "Mean active Agent-days/3-day window",
            [
                f"{get(n, 'activation', 'aggregate', 'mean_active_agent_days_per_3day_window'):.2f}"
                for n in POPULATION_SIZES
            ],
        ),
        (
            "Zero-active day frequency",
            [
                pct(get(n, "activation", "aggregate", "zero_active_day_frequency"))
                for n in POPULATION_SIZES
            ],
        ),
        (
            "Window with any zero-active day",
            [
                pct(
                    get(
                        n,
                        "activation",
                        "aggregate",
                        "window_with_any_zero_active_day_frequency",
                    )
                )
                for n in POPULATION_SIZES
            ],
        ),
        (
            "Closed-day active frequency",
            [
                pct(get(n, "activation", "aggregate", "closed_day_active_frequency"))
                for n in POPULATION_SIZES
            ],
        ),
    ]
    for label, values in table:
        lines.append("| " + label + " | " + " | ".join(map(str, values)) + " |")

    lines.extend(
        [
            "",
            "## Same-seed membership family",
            "",
            f"- Strictly nested: **{summary['membership']['strict_nested_family']}**.",
            f"- {summary['membership']['interpretation']}.",
            "",
            "## Marginal comparisons",
            "",
        ]
    )
    for item in summary["marginal_comparisons"]:
        lines.extend(
            [
                f"### N{item['from_n']} → N{item['to_n']}",
                "",
                f"- Population increase: **{pct(item['population_increase_fraction'])}**.",
                "- Mean active Agent-days/window: "
                f"**{item['mean_active_agent_days_per_window']['from']:.2f} → "
                f"{item['mean_active_agent_days_per_window']['to']:.2f}**.",
                "- Any-zero 3-day window frequency: "
                f"**{pct(item['zero_active_window_frequency']['from'])} → "
                f"{pct(item['zero_active_window_frequency']['to'])}**.",
                "- Closed-day active frequency: "
                f"**{pct(item['closed_day_active_frequency']['from'])} → "
                f"{pct(item['closed_day_active_frequency']['to'])}**.",
                "- Baseline graph edges: "
                f"**{item['graph_edges']['from']} → {item['graph_edges']['to']}**.",
                "- Baseline graph density: "
                f"**{item['graph_density']['from']:.3f} → "
                f"{item['graph_density']['to']:.3f}**.",
                "",
            ]
        )

    lines.extend(
        [
            "## Decision boundary",
            "",
            "- This analysis does **not** automatically select or freeze a final N.",
            "- N20 remains the candidate with existing real-backend three-day PASS; Phase 9E does not transfer that PASS to N30/N40.",
            "- A paid N30/N40 run is only justified if the zero-LLM comparison reveals a decision-relevant benefit that existing N20 evidence cannot resolve.",
            "- Active-Agent-days are not converted into an invented backend-request count.",
            "",
            "## Known limitations",
            "",
            "- The 100-seed analysis is sensitivity of the frozen Phase 4 policy over this fixed three-day horizon, not participant evidence.",
            "- Population sampling uses one predeclared Phase 3 selection seed; it is not a Monte Carlo population-sampling study.",
            "- Graphs are baseline structural snapshots only; Phase 9E does not advance market/forum state.",
            "- Stable `user_type` remains separate from dynamic graph prominence.",
            "",
        ]
    )
    return "\n".join(lines)


def run_phase09e(
    *,
    repo_root: str | Path,
    source_db: str | Path = "data/sys_1000.db",
    trading_calendar: str | Path = "data/trading_days.csv",
    artifact_root: str | Path = "artifacts/preflight/phase09",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    source = Path(source_db)
    if not source.is_absolute():
        source = root / source
    source = source.resolve()
    calendar = Path(trading_calendar)
    if not calendar.is_absolute():
        calendar = root / calendar
    calendar = calendar.resolve()
    artifacts = Path(artifact_root)
    if not artifacts.is_absolute():
        artifacts = root / artifacts
    artifacts = artifacts.resolve()

    git = require_clean_git(root)
    source_before = sha256_file(source)
    calendar_before = sha256_file(calendar)
    if source_before != EXPECTED_SOURCE_SHA256:
        raise Phase09EError("canonical source DB hash differs from frozen Phase 3 source")

    started = time.perf_counter()
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + f"_{git['commit'][:8]}_phase09e_population_sensitivity"
    )
    run_dir = artifacts / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    fixture_root = run_dir / "population_fixtures"
    fixture_root.mkdir()

    candidates: dict[int, dict[str, Any]] = {}
    for n in POPULATION_SIZES:
        runtime_db, manifest_path, manifest = _generate_fixture(
            repo_root=root,
            source_db=source,
            n=n,
            output_dir=fixture_root / f"n{n}",
        )
        candidates[n] = {
            "population": _population_summary(
                manifest=manifest, runtime_db=runtime_db, n=n
            ),
            "graph": graph_metrics(runtime_db, n),
            "activation": activation_sensitivity(
                runtime_db=runtime_db, n=n, trading_calendar=calendar
            ),
            "fixture": {
                "runtime_db": str(runtime_db),
                "manifest": str(manifest_path),
            },
        }

    membership = nested_membership_report(
        {n: row["population"] for n, row in candidates.items()}
    )
    source_after = sha256_file(source)
    calendar_after = sha256_file(calendar)

    failures = []
    if source_before != source_after or calendar_before != calendar_after:
        failures.append("protected source/calendar changed")
    if candidates[20]["population"]["runtime_sha256"] != EXPECTED_N20_RUNTIME_SHA256:
        failures.append("N20 runtime does not match verified real-backend reference")
    if candidates[20]["graph"]["graph_sha256"] != EXPECTED_N20_GRAPH_SHA256:
        failures.append("N20 graph does not match verified Phase 6 reference")
    if candidates[20]["activation"]["reference_active_counts"] != [5, 3, 3]:
        failures.append("N20 reference activation does not match Phase 9B")

    summary = {
        "banner": BANNER,
        "phase": "9E",
        "version": PHASE09E_VERSION,
        "status": "PASS" if not failures else "FAIL",
        "formal_experiment_evidence": False,
        "final_population_size_frozen": False,
        "llm_calls": 0,
        "market_execution": False,
        "forum_mutation": False,
        "participant_data_used": False,
        "population_sizes": list(POPULATION_SIZES),
        "population_selection_seed": POPULATION_SEED,
        "activation_grid": {
            "n_seeds": ACTIVATION_GRID_SIZE,
            "first_seed": ACTIVATION_GRID_SEEDS[0],
            "last_seed": ACTIVATION_GRID_SEEDS[-1],
            "all_predeclared_seeds_included": True,
            "seed_fishing": False,
        },
        "calendar": {
            "dates": list(EXPECTED_DATES),
            "market_open": list(EXPECTED_MARKET_OPEN),
        },
        "graph_contract": {
            "graph_start_date": GRAPH_START_DATE,
            "history_cutoff": GRAPH_HISTORY_CUTOFF,
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "time_decay_factor": TIME_DECAY_FACTOR,
            "top_fraction": TOP_FRACTION,
            "prominence_interpretation": (
                "dynamic graph prominence; not credibility/correctness"
            ),
        },
        "git": git,
        "protected_inputs": {
            "source_db": str(source),
            "source_sha256_before": source_before,
            "source_sha256_after": source_after,
            "trading_calendar": str(calendar),
            "trading_calendar_sha256_before": calendar_before,
            "trading_calendar_sha256_after": calendar_after,
            "unchanged": (
                source_before == source_after
                and calendar_before == calendar_after
            ),
        },
        "membership": membership,
        "candidates": {str(n): candidates[n] for n in POPULATION_SIZES},
        "marginal_comparisons": [
            marginal_comparison(candidates, 10, 20),
            marginal_comparison(candidates, 20, 30),
            marginal_comparison(candidates, 30, 40),
        ],
        "decision": {
            "automatic_final_n_selection": False,
            "current_real_backend_reference": "N20",
            "n20_real_backend_pass_available": True,
            "n30_paid_run_required_by_phase09e": False,
            "n40_paid_run_required_by_phase09e": False,
            "next_decision": (
                "review N20→N30 and N30→N40 marginal benefits against "
                "existing N20 real-backend feasibility before final N freeze"
            ),
        },
        "validation_failures": failures,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "run_id": run_id,
    }

    summary_path = run_dir / "summary.json"
    report_path = run_dir / "report.md"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(render_report(summary), encoding="utf-8")
    summary["artifact_summary"] = str(summary_path)
    summary["artifact_report"] = str(report_path)
    return summary
