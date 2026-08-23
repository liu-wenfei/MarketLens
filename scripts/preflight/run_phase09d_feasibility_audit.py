#!/usr/bin/env python3
"""Generate the zero-LLM Phase 9D feasibility audit."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marketlens.market.feasibility import (  # noqa: E402
    AUDIT_VERSION,
    Phase09DAuditError,
    build_audit,
    discover_latest_summary,
    load_summary,
    render_markdown,
    sha256_file,
)


BANNER = (
    "NON-FORMAL / PHASE 9D ZERO-LLM FEASIBILITY AUDIT / "
    "NOT FORMAL EXPERIMENT EVIDENCE"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact-root",
        default="artifacts/preflight/phase09",
    )
    parser.add_argument("--n10-dry-summary")
    parser.add_argument("--n20-dry-summary")
    parser.add_argument("--n20-real-summary")
    return parser.parse_args()


def resolve(root: Path, value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def main() -> int:
    args = parse_args()
    print(BANNER)

    artifact_root = resolve(REPO_ROOT, args.artifact_root)
    assert artifact_root is not None

    try:
        n10_path = (
            resolve(REPO_ROOT, args.n10_dry_summary)
            or discover_latest_summary(
                artifact_root,
                suffix="_phase09c_n10_dry",
            )
        )
        n20_dry_path = (
            resolve(REPO_ROOT, args.n20_dry_summary)
            or discover_latest_summary(
                artifact_root,
                suffix="_phase09c_n20_dry",
            )
        )
        n20_real_path = (
            resolve(REPO_ROOT, args.n20_real_summary)
            or discover_latest_summary(
                artifact_root,
                suffix="_phase09c_n20_real",
            )
        )

        source_paths = {
            "n10_dry": str(n10_path.resolve()),
            "n20_dry": str(n20_dry_path.resolve()),
            "n20_real": str(n20_real_path.resolve()),
        }
        source_hashes_before = {
            name: sha256_file(path)
            for name, path in (
                ("n10_dry", n10_path),
                ("n20_dry", n20_dry_path),
                ("n20_real", n20_real_path),
            )
        }

        audit = build_audit(
            n10_dry=load_summary(n10_path),
            n20_dry=load_summary(n20_dry_path),
            n20_real=load_summary(n20_real_path),
            source_paths=source_paths,
            source_hashes=source_hashes_before,
        )

        run_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "_phase09d_feasibility_audit"
        )
        run_dir = artifact_root / run_id
        run_dir.mkdir(parents=True, exist_ok=False)

        source_hashes_after = {
            name: sha256_file(path)
            for name, path in (
                ("n10_dry", n10_path),
                ("n20_dry", n20_dry_path),
                ("n20_real", n20_real_path),
            )
        }
        audit["source_artifacts_unchanged"] = (
            source_hashes_before == source_hashes_after
        )
        if not audit["source_artifacts_unchanged"]:
            audit["status"] = "FAIL"
            audit["evidence_validation_failures"].append(
                "source artifact changed during read-only audit"
            )
        audit["run_id"] = run_id

        summary_path = run_dir / "summary.json"
        report_path = run_dir / "report.md"
        summary_path.write_text(
            json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        report_path.write_text(
            render_markdown(audit),
            encoding="utf-8",
        )

        audit["artifact_summary"] = str(summary_path)
        audit["artifact_report"] = str(report_path)

        print(json.dumps(audit, indent=2, ensure_ascii=False))
        print(f"\nPHASE 9D: {audit['status']}")
        print(f"Report: {report_path}")
        print(f"Summary: {summary_path}")
        return 0 if audit["status"] == "PASS" else 2
    except Exception as exc:
        print(
            f"PHASE 9D ERROR: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
