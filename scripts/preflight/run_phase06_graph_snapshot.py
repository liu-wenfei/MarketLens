#!/usr/bin/env python3
"""Run a no-LLM Phase 6 engineering snapshot on a bounded Agent runtime DB."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.agents.social import (
    DEFAULT_GRAPH_START_DATE,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TIME_DECAY_FACTOR,
    DEFAULT_TOP_FRACTION,
    build_bounded_social_graph,
    make_prominence_snapshot,
)


BANNER = "NON-FORMAL / PHASE 6 GRAPH-PROMINENCE PREFLIGHT / NOT FORMAL EVIDENCE"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_value(*args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runtime-db", required=True, type=Path)
    ap.add_argument("--population-manifest", type=Path)
    ap.add_argument("--history-cutoff", required=True)
    ap.add_argument("--graph-start-date", default=DEFAULT_GRAPH_START_DATE)
    ap.add_argument("--similarity-threshold", type=float, default=DEFAULT_SIMILARITY_THRESHOLD)
    ap.add_argument("--time-decay-factor", type=float, default=DEFAULT_TIME_DECAY_FACTOR)
    ap.add_argument("--top-fraction", type=float, default=DEFAULT_TOP_FRACTION)
    ap.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/preflight/phase06"),
    )
    args = ap.parse_args()

    started = datetime.now(timezone.utc)
    commit = _git_value("rev-parse", "HEAD")
    short = commit[:8] if commit else "nogit"
    run_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}_{short}_graph"
    out = args.artifact_root / run_id
    out.mkdir(parents=True, exist_ok=False)

    built = build_bounded_social_graph(
        runtime_db=args.runtime_db,
        history_cutoff=args.history_cutoff,
        graph_start_date=args.graph_start_date,
        similarity_threshold=args.similarity_threshold,
        time_decay_factor=args.time_decay_factor,
    )
    doc = make_prominence_snapshot(built, top_fraction=args.top_fraction)

    manifest_record = None
    if args.population_manifest:
        manifest = args.population_manifest.expanduser().resolve()
        if not manifest.is_file():
            raise FileNotFoundError(f"population manifest not found: {manifest}")

        manifest_doc = json.loads(manifest.read_text(encoding="utf-8"))
        selection = manifest_doc.get("selection") or {}
        runtime_fixture = manifest_doc.get("runtime_fixture") or {}

        raw_selected_ids = selection.get("selected_agent_ids")
        if not isinstance(raw_selected_ids, list) or not raw_selected_ids:
            raise ValueError(
                "population manifest must contain non-empty selection.selected_agent_ids"
            )

        normalised_selected_ids = [str(uid) for uid in raw_selected_ids]
        if len(normalised_selected_ids) != len(set(normalised_selected_ids)):
            raise ValueError(
                "population manifest selection.selected_agent_ids contains duplicates"
            )

        manifest_population_ids = tuple(sorted(normalised_selected_ids))
        if manifest_population_ids != built.population_ids:
            missing = sorted(set(built.population_ids) - set(manifest_population_ids))
            unexpected = sorted(
                set(manifest_population_ids) - set(built.population_ids)
            )
            raise ValueError(
                "population manifest membership does not match bounded runtime/graph; "
                f"missing_from_manifest={missing}, unexpected_in_manifest={unexpected}"
            )

        manifest_population_size = selection.get("population_size")
        if manifest_population_size != built.n_nodes:
            raise ValueError(
                "population manifest size does not match actual graph size; "
                f"manifest={manifest_population_size}, graph={built.n_nodes}"
            )

        fixture_sha256 = runtime_fixture.get("fixture_sha256")
        if not fixture_sha256:
            raise ValueError(
                "population manifest must contain runtime_fixture.fixture_sha256"
            )

        if fixture_sha256 != built.runtime_db_sha256_before:
            raise ValueError(
                "population manifest runtime fixture SHA256 does not match "
                "the runtime database supplied to Phase 6"
            )

        manifest_record = {
            "path": str(manifest),
            "sha256": _sha256(manifest),
            "manifest_schema_version": manifest_doc.get("manifest_schema_version"),
            "status": manifest_doc.get("status"),
            "selection_algorithm": selection.get("algorithm"),
            "selection_seed": selection.get("seed"),
            "population_size": manifest_population_size,
            "selected_agent_ids_sha256": selection.get(
                "selected_agent_ids_sha256"
            ),
            "selected_agent_ids_match_graph": True,
            "runtime_fixture_sha256": fixture_sha256,
            "runtime_fixture_matches_runtime_db": True,
        }

    finished = datetime.now(timezone.utc)
    doc.update(
        {
            "banner": BANNER,
            "run_id": run_id,
            "generated_at_utc": finished.isoformat(),
            "duration_seconds": round((finished - started).total_seconds(), 3),
            "git": {
                "commit": commit,
                "clean_at_start": not bool(_git_value("status", "--porcelain")),
            },
            "population_manifest": manifest_record,
        }
    )

    summary = out / "summary.json"
    summary.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(BANNER)
    print(json.dumps(doc, ensure_ascii=False, indent=2))
    print(f"Artifacts: {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
