#!/usr/bin/env python3
"""Prepare the deterministic Phase 10 N30 candidate fixture with zero LLM calls."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.agents.population.fixture import build_population_bundle  # noqa: E402
from marketlens.market.phase10_n30_real_validation import (  # noqa: E402
    DEFAULT_POPULATION_MANIFEST,
    DEFAULT_RUNTIME_DB,
    EXPECTED_ROW_COUNTS,
    EXPECTED_TABLE_DIGESTS_SHA256,
    EXPECTED_SELECTED_IDS_SHA256,
    POPULATION_SEED,
    POPULATION_SIZE,
    _verify_candidate_fixture,
)

BANNER = (
    "NON-FORMAL / PHASE 10 N30 CANDIDATE FIXTURE PREPARATION / "
    "ZERO-LLM / NOT FORMAL EXPERIMENT EVIDENCE"
)


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def main() -> int:
    print(BANNER)
    source_db = REPO_ROOT / "data/sys_1000.db"
    runtime_db = _resolve(DEFAULT_RUNTIME_DB)
    manifest_path = _resolve(DEFAULT_POPULATION_MANIFEST)
    output_dir = runtime_db.parent

    if runtime_db.exists() or manifest_path.exists() or output_dir.exists():
        try:
            runtime_sha, manifest_sha, ids = _verify_candidate_fixture(
                runtime_db=runtime_db,
                population_manifest=manifest_path,
            )
        except Exception as exc:
            print(
                "Existing N30 candidate fixture is incomplete or inconsistent; "
                f"refusing to overwrite it: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 2
        result = {
            "status": "READY_EXISTING_VERIFIED_FIXTURE",
            "llm_api_calls": 0,
            "population_size": POPULATION_SIZE,
            "population_seed": POPULATION_SEED,
            "selected_agent_ids_sha256": EXPECTED_SELECTED_IDS_SHA256,
            "runtime_sha256": runtime_sha,
            "manifest_sha256": manifest_sha,
            "population_ids": list(ids),
            "output_dir": str(output_dir),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="marketlens_phase10_n30_fixture_", dir=str(output_dir.parent)
    ) as temp_root:
        temp_output = Path(temp_root) / "n30_candidate_fixture"
        manifest = build_population_bundle(
            source_db=source_db,
            population_size=POPULATION_SIZE,
            seed=POPULATION_SEED,
            output_dir=temp_output,
        )
        runtime_sha = str(manifest["runtime_fixture"]["fixture_sha256"])
        selected_sha = str(manifest["selection"]["selected_agent_ids_sha256"])
        row_counts = dict(manifest["runtime_fixture"]["row_counts"])
        table_digests = dict(manifest["runtime_fixture"]["table_digests_sha256"])
        if selected_sha != EXPECTED_SELECTED_IDS_SHA256:
            raise RuntimeError(
                "generated N30 membership drifted from Phase 9E reference: "
                f"{selected_sha}"
            )
        if row_counts != EXPECTED_ROW_COUNTS:
            raise RuntimeError(f"generated N30 row counts drifted: {row_counts}")
        if table_digests != EXPECTED_TABLE_DIGESTS_SHA256:
            raise RuntimeError("generated N30 semantic table digests drifted")
        shutil.move(str(temp_output), str(output_dir))

    runtime_sha, manifest_sha, ids = _verify_candidate_fixture(
        runtime_db=runtime_db,
        population_manifest=manifest_path,
    )
    result = {
        "status": "CREATED_AND_VERIFIED",
        "llm_api_calls": 0,
        "population_size": POPULATION_SIZE,
        "population_seed": POPULATION_SEED,
        "selected_agent_ids_sha256": EXPECTED_SELECTED_IDS_SHA256,
        "runtime_sha256": runtime_sha,
        "manifest_sha256": manifest_sha,
        "population_ids": list(ids),
        "output_dir": str(output_dir),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
